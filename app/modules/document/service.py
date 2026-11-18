import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.document.models import Document, DocumentKind
from app.modules.document.schemas import DocumentCreate, DocumentUpdate


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class DocumentService:
    async def list_documents(
        self,
        db: AsyncSession,
        *,
        kind: Optional[DocumentKind] = None,
        search: Optional[str] = None,
        only_active: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        conditions = []
        if kind is not None:
            conditions.append(Document.kind == kind.value)
        if only_active:
            conditions.append(Document.is_active.is_(True))
        if search and search.strip():
            pattern = f"%{_escape_like(search.strip())}%"
            conditions.append(
                or_(
                    Document.title_vi.ilike(pattern, escape="\\"),
                    Document.title_en.ilike(pattern, escape="\\"),
                    Document.file_name.ilike(pattern, escape="\\"),
                )
            )

        total = (
            await db.execute(select(func.count()).select_from(Document).where(*conditions))
        ).scalar_one()
        stmt = (
            select(Document)
            .where(*conditions)
            .order_by(Document.sort_order.asc(), Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await db.execute(stmt)).scalars().all())
        return items, int(total)

    async def get_document(self, db: AsyncSession, doc_id: uuid.UUID) -> Document:
        doc = await db.get(Document, doc_id)
        if doc is None:
            raise NotFoundException(
                message="Không tìm thấy tài liệu", error_code="DOCUMENT_NOT_FOUND"
            )
        return doc

    async def create_document(self, db: AsyncSession, payload: DocumentCreate) -> Document:
        data = payload.model_dump()
        data["kind"] = payload.kind.value
        doc = Document(**data)
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        return doc

    async def update_document(
        self, db: AsyncSession, doc_id: uuid.UUID, payload: DocumentUpdate
    ) -> Document:
        doc = await self.get_document(db, doc_id)
        data = payload.model_dump()
        data["kind"] = payload.kind.value
        for field, value in data.items():
            setattr(doc, field, value)
        await db.flush()
        await db.refresh(doc)
        return doc

    async def delete_document(self, db: AsyncSession, doc_id: uuid.UUID) -> None:
        doc = await self.get_document(db, doc_id)
        await db.delete(doc)
        await db.flush()


document_service = DocumentService()
