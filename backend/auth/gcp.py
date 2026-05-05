"""Shared GCP credential helper.

Both BigQueryGCSPlane and the bingo-bigquery-connector import from here.
Callers pass the service-account JSON string (decrypted by the Fernet hybrid
property on DatabaseConnection or data_planes.credentials_encrypted).
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_BIGQUERY_SCOPES = ["https://www.googleapis.com/auth/bigquery"]
_GCS_SCOPES = ["https://www.googleapis.com/auth/devstorage.read_write"]
_FULL_SCOPES = _BIGQUERY_SCOPES + _GCS_SCOPES


def credentials_from_service_account_json(
    service_account_json: str,
    scopes: Optional[list[str]] = None,
):
    """Return google.oauth2.service_account.Credentials from a JSON string.

    Args:
        service_account_json: Decrypted service-account JSON (str).
        scopes: OAuth scopes to request. Defaults to BigQuery + GCS read/write.

    Raises:
        ValueError: If the JSON is missing or malformed.
    """
    from google.oauth2 import service_account

    if not service_account_json:
        raise ValueError("service_account_json is empty")

    try:
        sa_info = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid service account JSON: {exc}") from exc

    return service_account.Credentials.from_service_account_info(
        sa_info, scopes=scopes or _FULL_SCOPES
    )


def bigquery_client_from_json(service_account_json: str, project_id: str):
    """Return an authenticated google.cloud.bigquery.Client."""
    from google.cloud import bigquery

    credentials = credentials_from_service_account_json(
        service_account_json, scopes=_BIGQUERY_SCOPES
    )
    return bigquery.Client(project=project_id, credentials=credentials)


def gcs_client_from_json(service_account_json: str):
    """Return an authenticated google.cloud.storage.Client."""
    from google.cloud import storage

    credentials = credentials_from_service_account_json(
        service_account_json, scopes=_GCS_SCOPES
    )
    return storage.Client(
        project=credentials.service_account_email.split("@")[0],
        credentials=credentials,
    )
