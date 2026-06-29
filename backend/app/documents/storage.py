"""Object storage abstraction — MinIO / S3 / local filesystem."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.core.config import get_settings


class ObjectStorage:
    """Store raw PDFs/DOCX. Metadata + pointers in Postgres document_artifacts."""

    def __init__(self) -> None:
        settings = get_settings()
        self.backend = settings.object_storage_backend
        self.bucket = settings.object_storage_bucket
        self.local_root = Path(settings.upload_dir) / "documents"

    def store(self, document_id: UUID, filename: str, content: bytes) -> str:
        if self.backend == "local":
            return self._store_local(document_id, filename, content)
        if self.backend in ("s3", "minio"):
            return self._store_s3(document_id, filename, content)
        raise ValueError(f"Unknown object storage backend: {self.backend}")

    def _store_local(self, document_id: UUID, filename: str, content: bytes) -> str:
        dest_dir = self.local_root / str(document_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        dest.write_bytes(content)
        return f"file://{dest.resolve()}"

    def _store_s3(self, document_id: UUID, filename: str, content: bytes) -> str:
        settings = get_settings()
        key = f"documents/{document_id}/{filename}"
        try:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.object_storage_endpoint or None,
                aws_access_key_id=settings.object_storage_access_key or None,
                aws_secret_access_key=settings.object_storage_secret_key or None,
            )
            client.put_object(Bucket=self.bucket, Key=key, Body=content)
            return f"s3://{self.bucket}/{key}"
        except ImportError:
            return self._store_local(document_id, filename, content)


def get_object_storage() -> ObjectStorage:
    return ObjectStorage()
