"""
Backblaze B2 service — stores raw resume files (S3-compatible API).
Falls back to local disk storage (./local_storage/) when LOCAL_MODE=true,
so you can test the full pipeline before wiring up real B2 credentials.
"""
import os
import uuid

from app.config import settings

LOCAL_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "local_storage")


def _get_b2_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=settings.B2_ENDPOINT,
        aws_access_key_id=settings.B2_KEY_ID,
        aws_secret_access_key=settings.B2_APPLICATION_KEY,
    )


def upload_resume(file_bytes: bytes, filename: str) -> str:
    """
    Uploads a resume file and returns a reference key that MongoDB will store.
    """
    key = f"resumes/{uuid.uuid4()}_{filename}"

    if settings.LOCAL_MODE:
        os.makedirs(os.path.join(LOCAL_STORAGE_DIR, "resumes"), exist_ok=True)
        local_path = os.path.join(LOCAL_STORAGE_DIR, key)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return key

    client = _get_b2_client()
    client.put_object(Bucket=settings.B2_BUCKET_NAME, Key=key, Body=file_bytes)
    return key


def download_resume(key: str) -> bytes:
    if settings.LOCAL_MODE:
        local_path = os.path.join(LOCAL_STORAGE_DIR, key)
        with open(local_path, "rb") as f:
            return f.read()

    client = _get_b2_client()
    obj = client.get_object(Bucket=settings.B2_BUCKET_NAME, Key=key)
    return obj["Body"].read()
