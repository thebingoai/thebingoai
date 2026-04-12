"""Tests for WebSocket authentication close codes.

Verifies that the endpoint accepts the connection before closing with
custom close codes (4001/4003) so the frontend can distinguish auth
failures from network errors.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub heavy optional imports that may not be installed in the test env
for _mod in ("PyPDF2", "PIL", "PIL.Image", "docx", "docx.api"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import backend.models.user_skill  # noqa: F401 — resolves SQLAlchemy mapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ws(token: str | None = None):
    """Return a mock WebSocket whose query_params matches the given token."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.query_params = {"token": token} if token else {}
    return ws


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_token_closes_with_4001():
    """When no ?token= is supplied, the endpoint must accept then close 4001."""
    from backend.api.websocket import websocket_endpoint

    ws = _make_ws(token=None)

    await websocket_endpoint(ws)

    ws.accept.assert_awaited_once()
    ws.close.assert_awaited_once()
    close_kwargs = ws.close.call_args
    assert close_kwargs.kwargs.get("code") == 4001 or close_kwargs.args[0] == 4001, (
        f"Expected close code 4001, got: {close_kwargs}"
    )


@pytest.mark.asyncio
async def test_invalid_token_closes_with_4003():
    """When the token is invalid/expired, the endpoint must accept then close 4003."""
    from backend.api.websocket import websocket_endpoint

    ws = _make_ws(token="bad-token")

    with patch(
        "backend.api.websocket._get_user_from_token",
        new=AsyncMock(return_value=None),
    ):
        await websocket_endpoint(ws)

    ws.accept.assert_awaited_once()
    ws.close.assert_awaited_once()
    close_kwargs = ws.close.call_args
    assert close_kwargs.kwargs.get("code") == 4003 or close_kwargs.args[0] == 4003, (
        f"Expected close code 4003, got: {close_kwargs}"
    )


@pytest.mark.asyncio
async def test_valid_token_connects_and_accepts():
    """A valid token must result in ws.accept() being called and no close()."""
    from backend.api.websocket import websocket_endpoint

    ws = _make_ws(token="valid-token")
    # Simulate a normal session: receive_text raises WebSocketDisconnect immediately
    from fastapi import WebSocketDisconnect
    ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    ws.send_text = AsyncMock()

    stub_user = MagicMock()
    stub_user.id = "user-1"

    with (
        patch(
            "backend.api.websocket._get_user_from_token",
            new=AsyncMock(return_value=stub_user),
        ),
        patch("backend.api.websocket.manager") as mock_manager,
    ):
        mock_manager.connect = MagicMock()
        mock_manager.disconnect = MagicMock()
        # listen_redis must be a coroutine
        async def _fake_listen(*_a, **_kw):
            pass
        mock_manager.listen_redis = _fake_listen

        await websocket_endpoint(ws)

    ws.accept.assert_awaited_once()
    ws.close.assert_not_awaited()
