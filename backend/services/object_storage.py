import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from backend.config import settings

logger = logging.getLogger(__name__)


def _client():
    return boto3.client(
        "s3",
        region_name=settings.do_spaces_region,
        endpoint_url=settings.do_spaces_endpoint,
        aws_access_key_id=settings.do_spaces_key_id,
        aws_secret_access_key=settings.do_spaces_secret_key,
    )


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Upload bytes to DO Spaces at the given key."""
    _client().put_object(
        Bucket=settings.do_spaces_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    logger.debug("Uploaded %d bytes to %s/%s", len(data), settings.do_spaces_bucket, key)


def download_bytes(key: str) -> Optional[bytes]:
    """Download bytes from DO Spaces. Returns None if the key does not exist."""
    client = _client()
    try:
        response = client.get_object(Bucket=settings.do_spaces_bucket, Key=key)
        return response["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise


def delete_object(key: str) -> None:
    """Delete an object from DO Spaces (best-effort; logs on failure)."""
    try:
        _client().delete_object(Bucket=settings.do_spaces_bucket, Key=key)
        logger.debug("Deleted %s/%s", settings.do_spaces_bucket, key)
    except Exception as e:
        logger.error("Failed to delete %s/%s: %s", settings.do_spaces_bucket, key, e)
