import json
import secrets
from typing import Annotated, Any

from pydantic import BeforeValidator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
                return [str(parsed)]
            except Exception:
                return [v]
        return [str(x) for x in v]
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    PROJECT_NAME: str = "University Portal Backend"
    ENV: str = "production"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    BACKEND_CORS_ORIGINS: Annotated[list[str], BeforeValidator(parse_cors)] = []
    ALLOWED_HOSTS: Annotated[list[str], BeforeValidator(parse_cors)] = [
        "localhost",
        "127.0.0.1",
        "testserver",
    ]

    # Security Configuration
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 10MB limit
    RATE_LIMIT_GLOBAL: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_AI: str = "10/minute"
    RATE_LIMIT_MEDIA: str = "600/minute"

    # Only these peers may set CF-Connecting-IP / X-Real-IP / X-Forwarded-For.
    # Defaults cover loopback and private (Docker / LAN) reverse proxies.
    TRUSTED_PROXIES: Annotated[list[str], BeforeValidator(parse_cors)] = [
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    ]
    # Optional: pin the single header your edge proxy sets (e.g. "cf-connecting-ip").
    CLIENT_IP_HEADER: str = ""

    # Các site frontend cần làm mới cache sau khi admin đổi nội dung, dạng JSON:
    # [{"url": "http://frontend:3000/api/revalidate", "token": "<REVALIDATION_TOKEN>"}]
    # Để trống nếu không dùng (frontend sẽ tự làm mới theo chu kỳ cache).
    FRONTEND_REVALIDATE_TARGETS: str = ""

    # Postgres
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "university_cms"

    SQLALCHEMY_DATABASE_URI: str = ""

    @model_validator(mode="after")
    def assemble_db_connection(self) -> "Settings":
        if not self.SQLALCHEMY_DATABASE_URI:
            self.SQLALCHEMY_DATABASE_URI = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    REDIS_URL: str = ""

    @model_validator(mode="after")
    def assemble_redis_connection(self) -> "Settings":
        if not self.REDIS_URL:
            auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = (
                f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return self

    # JWT Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    # Access tokens cannot be revoked individually, so keep them short-lived;
    # the HttpOnly refresh token (rotated on use) carries the long session.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 8

    # Cookie Settings
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    @model_validator(mode="after")
    def apply_environment_security_defaults(self) -> "Settings":
        env_lower = self.ENV.lower()
        is_dev_or_test = env_lower in ("development", "dev", "test", "testing")

        if "COOKIE_SECURE" not in self.model_fields_set and is_dev_or_test:
            self.COOKIE_SECURE = False

        # Backward compatible: when ALLOWED_HOSTS is not configured explicitly
        # keep accepting any Host header (previous behaviour) so existing
        # deployments do not break. Set ALLOWED_HOSTS in the environment to
        # restrict it.
        if "ALLOWED_HOSTS" not in self.model_fields_set:
            self.ALLOWED_HOSTS = ["*"]

        if self.ACCESS_TOKEN_EXPIRE_MINUTES > 60:
            self.ACCESS_TOKEN_EXPIRE_MINUTES = 60

        if not self.SECRET_KEY:
            if "ENV" in self.model_fields_set and env_lower == "production":
                raise ValueError(
                    "SECRET_KEY must be set via environment variable in production"
                )
            self.SECRET_KEY = secrets.token_urlsafe(48)

        return self

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    LOG_FILE_PATH: str = "logs/app.log"

    # MinIO / S3 Storage Config
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_INTERNAL_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "university-media"

    @model_validator(mode="after")
    def assemble_minio_internal_endpoint(self) -> "Settings":
        if not self.MINIO_INTERNAL_ENDPOINT:
            self.MINIO_INTERNAL_ENDPOINT = self.MINIO_ENDPOINT
        return self

    # AI Integration
    GEMINI_API_KEY: str = ""
    AI_PROVIDER: str = "omniroute"
    AI_BASE_URL: str = "http://localhost:8090"
    AI_API_KEY: str = ""
    AI_DEFAULT_MODEL: str = "gemini-2.5-flash"
    AI_EMBEDDING_MODEL: str = "embedding-model"

    # Chatbot hỏi đáp thông tin website (Grok qua cổng LiteLLM, dự phòng Groq)
    CHATBOT_MODEL: str = "grok-chat"
    CHATBOT_MAX_MESSAGE_CHARS: int = 500
    CHATBOT_RATE_LIMIT_PER_MIN: int = 8
    CHATBOT_HISTORY_TURNS: int = 10
    CHATBOT_SESSION_TTL_SECONDS: int = 1800
    CHATBOT_KNOWLEDGE_TTL_SECONDS: int = 300
    CHATBOT_MAX_OUTPUT_TOKENS: int = 500

    # Translation Config (NLLB-200)
    TRANSLATION_MODEL_NAME: str = "facebook/nllb-200-distilled-1.3B"
    TRANSLATION_DEVICE: str = "auto"
    TRANSLATION_CACHE_TTL: int = 86400
    TRANSLATION_MAX_INPUT_LENGTH: int = 1000
    TRANSLATION_MAX_BATCH_SIZE: int = 50

    # VAPID Configurations for Web Push
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIM_EMAIL: str = "admin@itup.io.vn"



settings = Settings()


def resolve_html_urls(html_content: Any) -> Any:
    if not html_content or not isinstance(html_content, str):
        return html_content
    protocol = "https" if settings.MINIO_SECURE else "http"
    base_url = f"{protocol}://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}/"
    return html_content.replace('/api/v1/portal/media/file/', base_url)

