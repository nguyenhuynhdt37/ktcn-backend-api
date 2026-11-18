import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.audit.service import log_action
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserResponse
from app.modules.document.models import DocumentKind
from app.modules.document.schemas import (
    DocumentCreate,
    DocumentPagination,
    DocumentResponse,
    DocumentUpdate,
)
from app.modules.document.service import document_service

admin_router = APIRouter()
portal_router = APIRouter()


def _paginate(items, total: int, page: int, page_size: int) -> DocumentPagination:
    return DocumentPagination(
        items=[DocumentResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=(total + page_size - 1) // page_size if total else 0,
    )


@portal_router.get("", response_model=DocumentPagination)
async def list_documents_portal(
    kind: Optional[DocumentKind] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> DocumentPagination:
    """[Portal] Danh sách tài liệu đang hiển thị (Văn bản - Biểu mẫu, Bài giảng - Giáo trình)."""
    items, total = await document_service.list_documents(
        db, kind=kind, search=search, only_active=True, page=page, page_size=page_size
    )
    return _paginate(items, total, page, page_size)


@admin_router.get("", response_model=DocumentPagination)
async def list_documents_admin(
    kind: Optional[DocumentKind] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentPagination:
    items, total = await document_service.list_documents(
        db, kind=kind, search=search, only_active=False, page=page, page_size=page_size
    )
    return _paginate(items, total, page, page_size)


@admin_router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    return DocumentResponse.model_validate(await document_service.get_document(db, doc_id))


@admin_router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    request: Request,
    payload: DocumentCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    doc = await document_service.create_document(db, payload)
    await log_action(
        db, current_user, "DOCUMENT_CREATED", "document", doc.id,
        payload.model_dump(mode="json"), request,
    )
    await db.commit()
    return DocumentResponse.model_validate(doc)


@admin_router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    request: Request,
    doc_id: uuid.UUID,
    payload: DocumentUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    doc = await document_service.update_document(db, doc_id, payload)
    await log_action(
        db, current_user, "DOCUMENT_UPDATED", "document", doc.id,
        payload.model_dump(mode="json"), request,
    )
    await db.commit()
    return DocumentResponse.model_validate(doc)


@admin_router.delete("/{doc_id}", status_code=204)
async def delete_document(
    request: Request,
    doc_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await document_service.delete_document(db, doc_id)
    await log_action(
        db, current_user, "DOCUMENT_DELETED", "document", doc_id, None, request
    )
    await db.commit()
