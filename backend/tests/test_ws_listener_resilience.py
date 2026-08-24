"""The WebSocket Redis listener must survive a Redis blip, and chat.send tasks
must be tracked.

Before this, `listen_redis` wrapped only `json.loads` + `send_text` in a
try/except — a `ConnectionError` from `pubsub.listen()` itself killed the task
permanently. The task is created fire-and-forget and never awaited, so the
exception was swallowed while the socket stayed open answering pings. One Redis
restart deafened every socket open at that instant with no log line: chat still
streamed, but query result tables, briefings, skill detections and file-ready
events (all published on this channel) silently stopped.

`chat.send` tasks were likewise discarded — asyncio holds only a weak reference,
so a handle nobody keeps can be collected mid-run, and nothing capped how many
one socket could start.

These tests use no pytest-asyncio (it is not installed; `@pytest.mark.asyncio`
tests fail on this repo) — coroutines are driven with `asyncio.run`.
"""

import asyncio
import json
import threading
from typing import NamedTuple, Optional

import pytest

from backend.services import ws_connection_manager as wsm

# Captured before any test patches asyncio.sleep, so the poll helper below is
# never itself recorded as a backoff.
_real_sleep = asyncio.sleep

BLOCK = object()  # park in listen() until the task is cancelled


class _Attempt(NamedTuple):
    """One connect attempt: what `subscribe` does, then what `listen` produces.

    Items in `listen`: a dict is yielded, an exception is raised, BLOCK parks.
    """

    subscribe_error: Optional[BaseException] = None
    listen: tuple = ()


class _FakePubSub:
    def __init__(self, rec, attempt):
        self._rec = rec
        self._attempt = attempt

    async def subscribe(self, channel):
        self._rec.subscribes.append(channel)
        if self._attempt.subscribe_error is not None:
            raise self._attempt.subscribe_error

    async def aclose(self):
        self._rec.pubsub_closes += 1

    def listen(self):
        items = self._attempt.listen

        async def _gen():
            for item in items:
                if item is BLOCK:
                    await asyncio.Event().wait()
                elif isinstance(item, BaseException):
                    raise item
                else:
                    yield item

        return _gen()


class _FakeRedis:
    def __init__(self, rec, attempt):
        self._rec = rec
        self._pubsub = _FakePubSub(rec, attempt)

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        self._rec.client_closes += 1


class _Recorder:
    def __init__(self, attempts):
        self._attempts = list(attempts)
        self.subscribes = []
        self.sleeps = []
        self.pubsub_closes = 0
        self.client_closes = 0

    def from_url(self, _url, **_kwargs):
        # Attempts past the script park, so the listener waits to be cancelled
        # instead of spinning.
        attempt = self._attempts.pop(0) if self._attempts else _Attempt(listen=(BLOCK,))
        return _FakeRedis(self, attempt)


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed_with = []

    async def send_text(self, data):
        self.sent.append(data)

    async def close(self, code=1000):
        self.closed_with.append(code)


def _install(monkeypatch, attempts):
    """Point listen_redis at the fake Redis and make its backoff instant."""
    import redis.asyncio as aioredis

    rec = _Recorder(attempts)
    monkeypatch.setattr(aioredis, "from_url", rec.from_url)

    async def _instant_sleep(delay):
        rec.sleeps.append(delay)
        await _real_sleep(0)

    # listen_redis calls asyncio.sleep through the module's own global.
    monkeypatch.setattr(wsm.asyncio, "sleep", _instant_sleep)
    return rec


async def _until(predicate, timeout=2.0):
    """Poll until predicate() is truthy. Fails the test on timeout."""
    waited = 0.0
    while waited < timeout:
        if predicate():
            return
        await _real_sleep(0.01)
        waited += 0.01
    raise AssertionError("condition never became true")


async def _run_listener(rec_ws, until, user_id="u1"):
    """Run listen_redis until `until()` holds, then cancel it cleanly."""
    manager = wsm.ConnectionManager()
    task = asyncio.create_task(manager.listen_redis(user_id, rec_ws))
    try:
        await _until(until)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    return task


# ---------------------------------------------------------------------------
# listen_redis
# ---------------------------------------------------------------------------


def test_listener_resubscribes_after_the_connection_drops(monkeypatch):
    """The regression: an error from listen() itself must not end the task."""
    rec = _install(monkeypatch, [
        _Attempt(listen=(ConnectionError("Connection closed by server"),)),
        _Attempt(listen=({"type": "message", "data": json.dumps({"type": "briefing"})}, BLOCK)),
    ])
    ws = _FakeWS()

    asyncio.run(_run_listener(ws, lambda: ws.sent))

    assert rec.subscribes == ["ws:user:u1", "ws:user:u1"], (
        "the listener must resubscribe after a dropped connection"
    )
    assert json.loads(ws.sent[0]) == {"type": "briefing"}, (
        "messages published after the reconnect must still reach the socket"
    )


def test_listener_retries_when_subscribe_itself_fails(monkeypatch):
    """Redis down at connect time is the failover case; back off, don't spin."""
    rec = _install(monkeypatch, [
        _Attempt(subscribe_error=ConnectionError("Error 111 connecting")),
        _Attempt(subscribe_error=ConnectionError("Error 111 connecting")),
        _Attempt(subscribe_error=ConnectionError("Error 111 connecting")),
    ])

    asyncio.run(_run_listener(_FakeWS(), lambda: len(rec.subscribes) >= 4))

    assert rec.sleeps[:3] == [1.0, 2.0, 4.0], (
        f"backoff must grow while Redis stays down, got {rec.sleeps[:3]}"
    )


def test_backoff_resets_after_a_successful_subscribe(monkeypatch):
    """A later blip must not inherit the previous outage's long delay."""
    rec = _install(monkeypatch, [
        _Attempt(subscribe_error=ConnectionError("down")),
        _Attempt(subscribe_error=ConnectionError("down")),
        _Attempt(listen=(ConnectionError("dropped again"),)),
        _Attempt(listen=(BLOCK,)),
    ])

    asyncio.run(_run_listener(_FakeWS(), lambda: len(rec.subscribes) >= 4))

    assert rec.sleeps[:3] == [1.0, 2.0, 1.0], (
        f"the third delay must be back at the floor, got {rec.sleeps[:3]}"
    )


def test_cancelling_the_listener_stops_it(monkeypatch):
    """The endpoint's finally cancels this task; it must not resubscribe."""
    rec = _install(monkeypatch, [_Attempt(listen=(BLOCK,))])

    async def _scenario():
        manager = wsm.ConnectionManager()
        task = asyncio.create_task(manager.listen_redis("u1", _FakeWS()))
        await _until(lambda: rec.subscribes)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await _real_sleep(0.05)
        return task

    task = asyncio.run(_scenario())

    assert task.cancelled()
    assert len(rec.subscribes) == 1, "cancellation must not trigger a reconnect"
    assert rec.sleeps == [], "cancellation must not go through the backoff"


def test_a_bad_payload_does_not_kill_the_listener(monkeypatch):
    """One unparseable message must not cost the socket every later one."""
    rec = _install(monkeypatch, [
        _Attempt(listen=(
            {"type": "message", "data": "{not json"},
            {"type": "message", "data": json.dumps({"type": "chat.stream_complete"})},
            BLOCK,
        )),
    ])
    ws = _FakeWS()

    asyncio.run(_run_listener(ws, lambda: ws.sent))

    assert json.loads(ws.sent[0]) == {"type": "chat.stream_complete"}
    assert len(rec.subscribes) == 1, "a decode error must not force a reconnect"


def test_both_redis_handles_are_released_on_each_retry(monkeypatch):
    """Each attempt builds a fresh client; the old one must not be leaked."""
    rec = _install(monkeypatch, [
        _Attempt(listen=(ConnectionError("dropped"),)),
        _Attempt(listen=(ConnectionError("dropped"),)),
        _Attempt(listen=(BLOCK,)),
    ])

    asyncio.run(_run_listener(_FakeWS(), lambda: len(rec.subscribes) >= 3))

    assert rec.pubsub_closes >= 2 and rec.client_closes >= 2, (
        f"leaked handles: pubsub={rec.pubsub_closes} client={rec.client_closes}"
    )


# ---------------------------------------------------------------------------
# _on_listener_done — the socket must not be left silently deaf
# ---------------------------------------------------------------------------


def test_a_dead_listener_closes_the_socket(monkeypatch):
    """listen_redis retries forever, so finishing means it raised out of the
    retry loop. Close so the frontend's reconnect (any code but 4001/4003)
    takes over instead of the user sitting on a socket that receives nothing."""
    from backend.api import websocket as ws_api

    ws = _FakeWS()

    async def _scenario():
        async def _boom():
            raise RuntimeError("retry loop itself failed")

        task = asyncio.create_task(_boom())
        task.add_done_callback(lambda t: ws_api._on_listener_done(t, ws, "u1"))
        await asyncio.gather(task, return_exceptions=True)
        await _real_sleep(0.05)  # let the close task run

    asyncio.run(_scenario())

    assert ws.closed_with == [1011]


def test_a_cancelled_listener_does_not_close_the_socket():
    """Cancellation is the endpoint's own teardown — the socket is already going."""
    from backend.api import websocket as ws_api

    ws = _FakeWS()

    async def _scenario():
        task = asyncio.create_task(asyncio.Event().wait())
        task.add_done_callback(lambda t: ws_api._on_listener_done(t, ws, "u1"))
        await _real_sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await _real_sleep(0.05)

    asyncio.run(_scenario())

    assert ws.closed_with == []


# ---------------------------------------------------------------------------
# chat.send task tracking
# ---------------------------------------------------------------------------


class _FakeUser:
    id = "user-1"


@pytest.fixture
def ws_client(monkeypatch):
    """A minimal app mounting just the websocket router, with auth and the
    Redis listener stubbed out."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api import websocket as ws_api

    async def _fake_user(_token):
        return _FakeUser()

    async def _park(*_a, **_kw):
        await asyncio.Event().wait()

    monkeypatch.setattr(ws_api, "_get_user_from_token", _fake_user)
    monkeypatch.setattr(ws_api.manager, "listen_redis", _park)

    app = FastAPI()
    app.include_router(ws_api.router)
    with TestClient(app) as client:
        yield client, ws_api


def test_a_second_send_on_one_socket_is_rejected(ws_client, monkeypatch):
    """One turn per socket: the composer is disabled while streaming, so a
    second send is a duplicate or a scripted client fanning out runs."""
    client, ws_api = ws_client
    started = threading.Event()

    async def _slow_handler(*_a, **_kw):
        started.set()
        await asyncio.sleep(1.0)

    monkeypatch.setattr(ws_api, "_handle_chat_send", _slow_handler)

    with client.websocket_connect("/ws?token=t") as sock:
        sock.send_json({"type": "chat.send", "request_id": "r1", "message": "first"})
        assert started.wait(2.0), "the first turn never started"

        sock.send_json({"type": "chat.send", "request_id": "r2", "message": "second"})
        # The ping is answered from the same sequential receive loop, so the
        # rejection must arrive first. Asking for one message rather than
        # blocking on the rejection alone means a lost cap fails this test
        # instead of hanging it.
        sock.send_json({"type": "ping"})
        reply = sock.receive_json()

    assert reply["type"] == "chat.error", (
        f"the second send must be rejected before the ping is answered, got {reply}"
    )
    assert reply["error_code"] == "busy"
    assert reply["request_id"] == "r2"


def test_the_slot_frees_when_done_reaches_the_client(ws_client, monkeypatch):
    """The gate opens on `done`, not when the task ends.

    `_complete_turn` forwards `done` and *then* spends two LLM calls generating
    a title and a summary. The client re-enables its composer on `done`, so
    gating on task liveness left a multi-second window where the composer was
    live and the server still answered "busy" — which is exactly where a user
    answering a scoping question lands, since that reply is short and fast.
    """
    client, ws_api = ws_client
    in_post_process = threading.Event()

    async def _handler(_ws, _user, _request_id, *_a, on_gate_open=None, **_kw):
        on_gate_open()  # `done` has reached the client
        in_post_process.set()
        await asyncio.sleep(1.0)  # stand-in for title + summary generation

    monkeypatch.setattr(ws_api, "_handle_chat_send", _handler)

    with client.websocket_connect("/ws?token=t") as sock:
        sock.send_json({"type": "chat.send", "request_id": "r1", "message": "first"})
        assert in_post_process.wait(2.0), "the first turn never reached post-process"

        sock.send_json({"type": "chat.send", "request_id": "r2", "message": "second"})
        # Same sequential-receive-loop trick as the rejection test above: if r2
        # were rejected, chat.error would arrive ahead of the pong.
        sock.send_json({"type": "ping"})
        reply = sock.receive_json()

    assert reply["type"] == "pong", (
        f"a send after `done` must be accepted while post-process still runs, got {reply}"
    )


def test_the_slot_frees_once_the_turn_finishes(ws_client, monkeypatch):
    """Backstop for every path that ends without ever reaching `done` — an early
    return, a raise, cancellation. This handler ignores `on_turn_visible`
    entirely, so only the done-callback can open the gate; without it the socket
    is stuck rejecting everything for the rest of its life."""
    client, ws_api = ws_client
    calls = []
    finished = threading.Event()

    async def _quick_handler(_ws, _user, request_id, *_a, **_kw):
        calls.append(request_id)

    # Synchronise on the task's own done-callback chain, not on a ping
    # round-trip. A pong only proves the receive loop got that far; the turn task
    # may not have been scheduled yet, and the callback that opens the gate runs
    # later still. Racing that failed ~16% of runs — on `dev` exactly as much as
    # here, so it was never a signal about this change.
    #
    # `_log_task_exception` is registered immediately before the gate-releasing
    # callback, and callbacks queued on one task drain together, so seeing this
    # fire means the release is queued ahead of anything the socket sends next.
    monkeypatch.setattr(ws_api, "_handle_chat_send", _quick_handler)
    monkeypatch.setattr(ws_api, "_log_task_exception", lambda _t: finished.set())

    with client.websocket_connect("/ws?token=t") as sock:
        sock.send_json({"type": "chat.send", "request_id": "r1", "message": "first"})
        assert finished.wait(2.0), "the first turn never completed"

        finished.clear()
        sock.send_json({"type": "chat.send", "request_id": "r2", "message": "second"})
        sock.send_json({"type": "ping"})
        assert sock.receive_json()["type"] == "pong", (
            "a second turn after the first finished must be accepted, not rejected"
        )
        # r2 is dispatched fire-and-forget, so the pong says it was *accepted*,
        # not that it has run. Asserting on `calls` without waiting for it is
        # what the remaining flake was.
        assert finished.wait(2.0), "the second turn was accepted but never ran"

    assert calls == ["r1", "r2"]


def test_a_dead_listener_closes_the_socket_end_to_end(ws_client, monkeypatch):
    """Covers the add_done_callback wiring, not just the callback body."""
    from starlette.websockets import WebSocketDisconnect

    client, ws_api = ws_client

    async def _boom(*_a, **_kw):
        raise ConnectionError("redis gone")

    monkeypatch.setattr(ws_api.manager, "listen_redis", _boom)

    # Ping in a bounded loop rather than blocking on the close: without the
    # done-callback the socket stays open answering pings forever, and this
    # test must fail then, not hang.
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?token=t") as sock:
            for _ in range(5):
                sock.send_json({"type": "ping"})
                sock.receive_json()


def test_disconnecting_does_not_cancel_a_running_turn(ws_client, monkeypatch):
    """Deliberate: surviving the socket is the designed behaviour.

    The run persists the answer and publishes chat.stream_complete over Redis,
    which the reconnected socket picks up (frontend
    useChatConversations.checkStreamingViaWs sends stream.check and waits for
    it). Cancelling on disconnect would discard a completed, already-charged
    turn on every wifi blip.
    """
    client, ws_api = ws_client
    started = threading.Event()
    outcome = []

    async def _handler(*_a, **_kw):
        started.set()
        try:
            await asyncio.sleep(0.2)
            outcome.append("completed")
        except asyncio.CancelledError:
            outcome.append("cancelled")
            raise

    monkeypatch.setattr(ws_api, "_handle_chat_send", _handler)

    with client.websocket_connect("/ws?token=t") as sock:
        sock.send_json({"type": "chat.send", "request_id": "r1", "message": "hi"})
        assert started.wait(2.0), "the turn never started"
    # socket closed — the endpoint's finally has run

    deadline = threading.Event()
    deadline.wait(1.0)

    assert outcome == ["completed"], (
        f"the turn must outlive the socket, got {outcome}"
    )


# ---------------------------------------------------------------------------
# chat.send payload validation (shared with the REST path)
# ---------------------------------------------------------------------------


def test_an_oversized_message_is_rejected(ws_client, monkeypatch):
    """REST caps a message at ChatRequest's max_length; the socket used to read
    the field raw, so a frame ran to the websockets default of 16 MiB."""
    from backend.schemas.chat import ChatRequest

    client, ws_api = ws_client
    calls = []

    async def _handler(*_a, **_kw):
        calls.append(1)

    monkeypatch.setattr(ws_api, "_handle_chat_send", _handler)

    cap = next(
        m.max_length
        for m in ChatRequest.model_fields["message"].metadata
        if hasattr(m, "max_length")
    )

    with client.websocket_connect("/ws?token=t") as sock:
        sock.send_json({
            "type": "chat.send", "request_id": "r1", "message": "x" * (cap + 1),
        })
        # Trailing ping so a *missing* rejection fails this test instead of
        # hanging it — the receive loop is sequential, so a real rejection
        # always arrives before the pong.
        sock.send_json({"type": "ping"})
        reply = sock.receive_json()

    assert reply["type"] == "chat.error", f"oversized message was accepted, got {reply}"
    assert reply["request_id"] == "r1"
    assert not calls, "an oversized message must not reach the orchestrator"


def test_non_integer_connection_ids_are_rejected(ws_client, monkeypatch):
    """connection_ids reaches a SQL IN () clause — the socket used to forward it
    unvalidated."""
    client, ws_api = ws_client
    calls = []

    async def _handler(*_a, **_kw):
        calls.append(1)

    monkeypatch.setattr(ws_api, "_handle_chat_send", _handler)

    with client.websocket_connect("/ws?token=t") as sock:
        sock.send_json({
            "type": "chat.send", "request_id": "r1", "message": "hi",
            "connection_ids": ["not-an-int"],
        })
        sock.send_json({"type": "ping"})  # see the note above — fail, don't hang
        reply = sock.receive_json()

    assert reply["type"] == "chat.error", f"bad connection_ids accepted, got {reply}"
    assert not calls


def test_a_normal_message_still_passes(ws_client, monkeypatch):
    """Guard against the validation rejecting valid traffic."""
    client, ws_api = ws_client
    seen = []
    dispatched = threading.Event()

    async def _handler(_ws, _user, request_id, thread_id, message, connection_ids, **_kw):
        seen.append((request_id, thread_id, message, connection_ids))
        dispatched.set()

    monkeypatch.setattr(ws_api, "_handle_chat_send", _handler)

    with client.websocket_connect("/ws?token=t") as sock:
        sock.send_json({
            "type": "chat.send", "request_id": "r1", "message": "  hi  ",
            "thread_id": "t-1", "connection_ids": [1, "2"],
        })
        # The turn is dispatched fire-and-forget, so the pong can beat it —
        # wait on the handler itself rather than racing it.
        assert dispatched.wait(2.0), "a valid message was rejected"

    assert seen == [("r1", "t-1", "hi", [1, 2])], (
        "message must still be stripped and connection_ids coerced to ints"
    )
