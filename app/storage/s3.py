from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3StorageError(Exception):
    """Raised when an S3 storage operation fails."""


def _check_key(key: str) -> None:
    if not key or ".." in key or key.startswith("/"):
        raise S3StorageError("Invalid storage key.")


class S3Storage:
    def __init__(self) -> None:
        self.bucket = settings.AWS_S3_BUCKET

        session = boto3.Session(
            profile_name=settings.AWS_PROFILE or None,
            region_name=settings.AWS_REGION,
        )
        self.client = session.client(
            "s3",
            endpoint_url=getattr(settings, "AWS_ENDPOINT_URL", None) or None,
            config=Config(
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        

    async def upload_file(self, file: BinaryIO, *, key: str, content_type: str) -> None:
        """Upload a file object (pass UploadFile.file, already rewound)."""
        _check_key(key)
        try:

            await asyncio.to_thread(
                self.client.upload_fileobj,
                file,
                self.bucket,
                key,
                ExtraArgs={
                    "ContentType": content_type,
                    "ServerSideEncryption": "AES256",
                },
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("S3 upload failed for key %s", key)
            raise S3StorageError("Failed to upload document to storage.") from exc

    async def download_file(self, *, key: str, destination: Path) -> None:
        """Download an S3 object to a local path chosen by the server."""
        _check_key(key)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(
                self.client.download_file, self.bucket, key, str(destination)
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            logger.exception("S3 download failed for key %s", key)
            raise S3StorageError("Failed to download document from storage.") from exc

    async def delete_file(self, *, key: str) -> None:
        """Delete an object. Succeeds even if the key does not exist."""
        _check_key(key)
        try:
            await asyncio.to_thread(
                self.client.delete_object, Bucket=self.bucket, Key=key
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("S3 deletion failed for key %s", key)
            raise S3StorageError("Failed to delete document from storage.") from exc

    async def presigned_url(
        self, *, key: str, filename: str, expires: int = 300
    ) -> str:
        """Short-lived download link. Sanitize `filename` before calling."""
        _check_key(key)
        try:
            return await asyncio.to_thread(
                self.client.generate_presigned_url,
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "ResponseContentType": "application/pdf",
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=expires,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("S3 presign failed for key %s", key)
            raise S3StorageError("Failed to create download link.") from exc
            