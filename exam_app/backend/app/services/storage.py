import os
import tempfile
import uuid

from app.config import settings


def _r2_enabled() -> bool:
    return all(
        [
            settings.R2_ACCOUNT_ID,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY,
            settings.R2_BUCKET,
        ]
    )


def _s3_client():
    import boto3
    from botocore.config import Config

    endpoint = settings.R2_ENDPOINT_URL or f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def validate_pdf_bytes(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def save_upload(data: bytes, original_name: str) -> str:
    name = f"{uuid.uuid4()}.pdf"
    if _r2_enabled():
        _s3_client().put_object(
            Bucket=settings.R2_BUCKET,
            Key=name,
            Body=data,
            ContentType="application/pdf",
        )
    else:
        os.makedirs(settings.STORAGE_DIR, exist_ok=True)
        path = os.path.join(settings.STORAGE_DIR, name)
        with open(path, "wb") as f:
            f.write(data)
    return name


def get_upload_path(storage_name: str) -> str:
    if not _r2_enabled():
        return os.path.join(settings.STORAGE_DIR, storage_name)

    cache_dir = os.path.join(tempfile.gettempdir(), "pdf2test_uploads")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, storage_name)
    if not os.path.exists(path):
        _s3_client().download_file(settings.R2_BUCKET, storage_name, path)
    return path


def delete_upload(storage_name: str) -> None:
    if _r2_enabled():
        try:
            _s3_client().delete_object(Bucket=settings.R2_BUCKET, Key=storage_name)
        except Exception:
            pass
    else:
        try:
            os.remove(os.path.join(settings.STORAGE_DIR, storage_name))
        except FileNotFoundError:
            pass
