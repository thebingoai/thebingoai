"""S3-compatible object storage client (DigitalOcean Spaces).

Each caller creates its own ObjectStorageClient instance so that DataPlane
implementations and other services can bring their own credentials.
The module-level helpers (upload_bytes, download_bytes, …) use a lazy
default instance backed by the global DO Spaces settings — kept for
legacy reads during the Phase 1 → 3 migration window.
"""
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ObjectStorageClient:
    """Per-instance S3-compatible storage client."""

    def __init__(
        self,
        endpoint_url: str,
        region_name: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
    ):
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type,
        )
        logger.debug("Uploaded %d bytes to %s/%s", len(data), self._bucket, key)

    def download_bytes(self, key: str) -> Optional[bytes]:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            logger.debug("Deleted %s/%s", self._bucket, key)
        except Exception as e:
            logger.error("Failed to delete %s/%s: %s", self._bucket, key, e)

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        logger.debug("Generated presigned URL for %s (expires in %ds)", key, expires_in)
        return url

    def list_objects(self, prefix: str = "") -> list[dict]:
        """List all objects under *prefix*. Returns [{key, size, etag, last_modified}, ...]."""
        results = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                results.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "etag": obj.get("ETag", "").strip('"'),
                    "last_modified": obj["LastModified"].isoformat(),
                })
        return results


def _default_client() -> ObjectStorageClient:
    """Lazy default client backed by DO Spaces settings (legacy reads only)."""
    from backend.config import settings
    return ObjectStorageClient(
        endpoint_url=settings.do_spaces_endpoint,
        region_name=settings.do_spaces_region,
        access_key_id=settings.do_spaces_key_id,
        secret_access_key=settings.do_spaces_secret_key,
        bucket=settings.do_spaces_bucket,
    )


# ---------------------------------------------------------------------------
# Module-level helpers — legacy read path (DO Spaces singleton behaviour)
# ---------------------------------------------------------------------------

def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _default_client().upload_bytes(key, data, content_type)


def download_bytes(key: str) -> Optional[bytes]:
    return _default_client().download_bytes(key)


def delete_object(key: str) -> None:
    _default_client().delete_object(key)


def object_exists(key: str) -> bool:
    return _default_client().object_exists(key)


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    return _default_client().generate_presigned_url(key, expires_in)
