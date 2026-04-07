"""Tests for backend.auth.webhooks — SSO webhook handler."""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.webhooks import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _sign(payload: bytes, secret: str) -> str:
    return hmac.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_webhook_password_reset(client):
    """Webhook accepts user.password_reset event and returns {"status": "ok"}."""
    payload = {"event": "user.password_reset", "data": {"email": "a@b.com"}}
    with patch("backend.auth.webhooks.settings") as s:
        s.sso_webhook_secret = ""
        resp = client.post("/api/webhooks/sso", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_user_verified(client):
    """Webhook accepts user.verified event and returns {"status": "ok"}."""
    payload = {"event": "user.verified", "data": {"email": "a@b.com"}}
    with patch("backend.auth.webhooks.settings") as s:
        s.sso_webhook_secret = ""
        resp = client.post("/api/webhooks/sso", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_skip_signature_community(client):
    """Webhook skips signature verification when sso_webhook_secret is empty (community)."""
    payload = {"event": "user.verified", "data": {}}
    with patch("backend.auth.webhooks.settings") as s:
        s.sso_webhook_secret = ""
        resp = client.post("/api/webhooks/sso", json=payload)
    assert resp.status_code == 200


def test_webhook_reject_invalid_signature(client):
    """Webhook rejects request with invalid signature when sso_webhook_secret is set (enterprise)."""
    payload = json.dumps({"event": "user.verified", "data": {}}).encode()
    with patch("backend.auth.webhooks.settings") as s:
        s.sso_webhook_secret = "my_secret"
        resp = client.post(
            "/api/webhooks/sso",
            content=payload,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": "bad_sig"},
        )
    assert resp.status_code == 401


def test_webhook_accept_valid_signature(client):
    """Webhook accepts request with valid HMAC-SHA256 signature (enterprise)."""
    payload = json.dumps({"event": "user.verified", "data": {}}).encode()
    secret = "my_secret"
    sig = _sign(payload, secret)
    with patch("backend.auth.webhooks.settings") as s:
        s.sso_webhook_secret = secret
        resp = client.post(
            "/api/webhooks/sso",
            content=payload,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": sig},
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_malformed_json(client):
    """Webhook returns 400 on malformed JSON."""
    with patch("backend.auth.webhooks.settings") as s:
        s.sso_webhook_secret = ""
        resp = client.post(
            "/api/webhooks/sso",
            content=b"not json{{{",
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 400
