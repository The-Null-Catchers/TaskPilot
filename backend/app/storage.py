import asyncio
import io
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

Image.MAX_IMAGE_PIXELS = 25_000_000


def _client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.storage_key,
        aws_secret_access_key=settings.storage_secret,
        region_name=settings.storage_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _storage_client():
    return _client(settings.storage_endpoint)


def _public_client():
    return _client(settings.storage_public_endpoint or settings.storage_endpoint)


async def ensure_bucket() -> None:
    def action() -> None:
        client = _storage_client()
        try:
            client.head_bucket(Bucket=settings.storage_bucket)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            client.create_bucket(Bucket=settings.storage_bucket)

    await asyncio.to_thread(action)


async def put_bytes(key: str, data: bytes, mime_type: str) -> None:
    await ensure_bucket()

    def action(use_sse: bool) -> None:
        params = {
            "Bucket": settings.storage_bucket,
            "Key": key,
            "Body": data,
            "ContentType": mime_type,
        }
        if use_sse:
            params["ServerSideEncryption"] = "AES256"
        _storage_client().put_object(**params)

    try:
        await asyncio.to_thread(action, settings.storage_sse)
    except ClientError:
        if not settings.storage_sse:
            raise
        await asyncio.to_thread(action, False)


async def delete_keys(*keys: str | None) -> None:
    real_keys = [key for key in keys if key]
    if not real_keys:
        return

    def action() -> None:
        _storage_client().delete_objects(
            Bucket=settings.storage_bucket,
            Delete={"Objects": [{"Key": key} for key in real_keys], "Quiet": True},
        )

    await asyncio.to_thread(action)


async def presigned_download_url(key: str, filename: str, mime_type: str) -> str:
    def action() -> str:
        disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
        return _public_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.storage_bucket,
                "Key": key,
                "ResponseContentType": mime_type,
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=settings.storage_presign_seconds,
        )

    return await asyncio.to_thread(action)


async def presigned_preview_url(key: str, mime_type: str) -> str:
    def action() -> str:
        return _public_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.storage_bucket,
                "Key": key,
                "ResponseContentType": mime_type,
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=settings.storage_presign_seconds,
        )

    return await asyncio.to_thread(action)


def make_thumbnail(data: bytes, mime_type: str) -> bytes | None:
    if mime_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return None
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((480, 480))
            if image.mode not in {"RGB", "L"}:
                background = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image)
                image = background
            elif image.mode == "L":
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=82, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid or unsafe image") from exc
