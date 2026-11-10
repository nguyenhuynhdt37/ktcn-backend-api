import io
from fastapi import APIRouter, HTTPException, Response
from anyio.to_thread import run_sync

from app.core.config import settings
from app.modules.media.service import MediaService, build_public_media_headers

portal_router = APIRouter()
media_service = MediaService()


@portal_router.get("/file/{object_key:path}")
async def get_media_file(
    object_key: str,
) -> Response:
    """
    Public endpoint to stream media files from MinIO.
    Allows unauthenticated access to files via their object_key.
    """
    try:
        response = await run_sync(
            lambda: media_service.s3_client.get_object(
                Bucket=settings.MINIO_BUCKET,
                Key=object_key,
            )
        )
        body = await run_sync(lambda: response["Body"].read())
        # Không tin Content-Type đã lưu: chỉ ảnh/PDF/media mới được hiển thị inline,
        # mọi loại khác (HTML, JS, ...) bị ép tải xuống để không thể chạy script
        # trên origin của API (nơi có cookie đăng nhập của quản trị viên).
        media_type, headers = build_public_media_headers(response.get("ContentType"))
        return Response(content=body, media_type=media_type, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")
