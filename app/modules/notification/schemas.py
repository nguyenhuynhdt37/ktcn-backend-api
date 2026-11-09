import uuid
from datetime import datetime

from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.notification.models import NotificationType


class NotificationResponse(BaseModel):
    id: uuid.UUID
    recipient_id: uuid.UUID
    type: NotificationType
    title: str
    message: str | None = None
    related_entity_type: str | None = None
    related_entity_id: uuid.UUID | None = None
    related_url: str | None = None
    read_at: datetime | None = None
    created_at: datetime
    details: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationPaginationResponse(BaseModel):
    items: list[NotificationResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    unread_count: int
    has_next: bool
    has_previous: bool


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated_count: int


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(max_length=2048)
    keys: PushSubscriptionKeys
    user_agent: str | None = None

    @field_validator("endpoint")
    @classmethod
    def validate_push_endpoint(cls, value: str) -> str:
        # Only browser push services may receive server-side webpush requests.
        url = urlsplit(value)
        host = url.hostname or ""
        allowed = host in {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
        allowed = allowed or host.endswith(".notify.windows.com")
        if (
            url.scheme != "https" or not allowed or url.port not in {None, 443}
            or url.username or url.password or url.fragment
        ):
            raise ValueError("Endpoint must use an approved HTTPS browser push service")
        return value


class PushSubscriptionUnsubscribe(BaseModel):
    endpoint: str

