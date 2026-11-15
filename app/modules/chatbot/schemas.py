from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # Chỉ nhận id phiên + câu hỏi: không có trường lịch sử/role nên client không giả được hội thoại.
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")
    message: str = Field(max_length=2000)
    lang: Literal["vi", "en"] = "vi"


class ChatSource(BaseModel):
    title: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    kind: Literal["faq", "refusal", "model", "error"]
    sources: list[ChatSource] = []
