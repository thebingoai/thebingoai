"""One chat turn per thread, enforced in Redis rather than per-socket.

The endpoint's `chat_tasks` set gates duplicate sends on a *socket*, but chat
turns are deliberately built to outlive their socket (the endpoint's `finally`
does not cancel them). So a client that drops mid-stream and resends after
reconnecting arrives on a fresh socket with an empty set and starts a second
turn against a thread the first one is still writing to.

`_handle_chat_send` therefore claims `chat:turn:{thread_id}` in Redis before any
of the expensive setup, and releases it only if it still owns it.

No pytest-asyncio in this repo (`@pytest.mark.asyncio` tests fail) — coroutines
are driven with `asyncio.run`, matching test_ws_listener_resilience.py.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.api import websocket as ws_mod


class _FakeRedis:
    """Records SET NX / GET / DELETE / EVAL against a dict.

    `eval` stands in for `redis_lease._RELEASE_LUA`, which is how the turn lock
    is released — compare-and-delete in one call. It lands in `deleted` like a
    plain DELETE would, so the assertions below read the same either way.
    """

    def __init__(self, initial=None):
        self.store = dict(initial or {})
        self.deleted: list[str] = []
        self.set_calls: list[tuple] = []

    def eval(self, script, numkeys, key, token):
        if self.store.get(key) != token:
            return 0
        self.delete(key)
        return 1

    def set(self, key, value, nx=False, ex=None):
        self.set_calls.append((key, value, nx, ex))
        if nx and key in self.store:
            return None  # redis-py returns None when NX loses
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, *keys):
        for key in keys:
            self.deleted.append(key)
            self.store.pop(key, None)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def exists(self, key):
        return 1 if key in self.store else 0

    def close(self):
        pass


class _FakeWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, raw):
        self.sent.append(json.loads(raw))


class _FakeUser:
    id = "user-1"


class _FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _run(fake_redis, resolve_conversation, *, thread_id="t-1", request_id="req-1"):
    """Drive _handle_chat_send with Redis, the DB session and conversation
    resolution stubbed. Returns (ws, db)."""
    ws = _FakeWS()
    db = _FakeSession()
    with patch("redis.from_url", return_value=fake_redis), \
         patch.object(ws_mod, "DetachedReadSessionLocal", lambda: db), \
         patch.object(ws_mod, "_resolve_conversation", resolve_conversation):
        asyncio.run(ws_mod._handle_chat_send(
            ws, _FakeUser(), request_id, thread_id, "hello", [],
        ))
    return ws, db


async def _never_called(*args, **kwargs):
    raise AssertionError("gate must reject before any conversation work")


async def _resolve_to_none(*args, **kwargs):
    """Conversation resolution bails — the cheapest path that still reaches the
    `finally` where the lock is released."""
    return None, False


# ── the gate ────────────────────────────────────────────────────────────────

def test_second_turn_on_locked_thread_is_rejected():
    redis = _FakeRedis({"chat:turn:t-1": "req-0"})  # a turn already owns it

    ws, db = _run(redis, _never_called, request_id="req-1")

    assert len(ws.sent) == 1
    err = ws.sent[0]
    assert err["type"] == "chat.error"
    assert err["error_code"] == "busy"
    assert err["request_id"] == "req-1"
    assert db.closed, "the rejected path must not leak its session"


def test_lock_is_claimed_before_conversation_work():
    redis = _FakeRedis()
    reached = []

    async def _record(*args, **kwargs):
        # The lock must already be held by the time real work starts.
        reached.append(redis.store.get("chat:turn:t-1"))
        return None, False

    _run(redis, _record, request_id="req-1")

    assert reached and reached[0], "the lock was not held once real work started"
    key, value, nx, ex = redis.set_calls[0]
    assert (key, nx) == ("chat:turn:t-1", True)
    assert ex and ex > 0, "the lock needs a TTL or a crashed turn wedges the thread"


def test_ownership_token_is_not_the_client_supplied_request_id():
    """`request_id` comes straight off the wire (`data.get("request_id", "")`),
    so it is not ours to trust as an ownership token — and it defaults to the
    empty string, which means two clients that simply omit the field share a
    token and can release each other's lock. Not adversarial; the default path.
    """
    redis = _FakeRedis()

    _run(redis, _resolve_to_none, request_id="")

    _key, token, _nx, _ex = redis.set_calls[0]
    assert token, "an empty token lets any other tokenless turn release this lock"
    assert token != "", "the lock must not inherit the client's blank request_id"


def test_lock_released_when_turn_finishes():
    redis = _FakeRedis()

    _run(redis, _resolve_to_none, request_id="req-1")

    assert "chat:turn:t-1" not in redis.store
    assert "chat:turn:t-1" in redis.deleted


def test_lock_released_when_turn_raises():
    redis = _FakeRedis()

    async def _boom(*args, **kwargs):
        raise RuntimeError("orchestrator exploded")

    ws, _ = _run(redis, _boom, request_id="req-1")

    assert "chat:turn:t-1" not in redis.store, "a failed turn must not wedge the thread"
    assert any(m.get("type") == "chat.error" for m in ws.sent)


def test_lock_owned_by_a_later_turn_is_not_stolen():
    """A turn that outran its TTL must not delete the lock a newer turn claimed."""
    redis = _FakeRedis()

    async def _expire_and_hand_over(*args, **kwargs):
        # Simulate: our lock expired, a second turn claimed the thread.
        redis.store["chat:turn:t-1"] = "req-2"
        return None, False

    _run(redis, _expire_and_hand_over, request_id="req-1")

    assert redis.store["chat:turn:t-1"] == "req-2"
    assert "chat:turn:t-1" not in redis.deleted


def test_new_conversation_is_locked_once_its_thread_exists():
    """A first message arrives with thread_id=None, so there is nothing to claim
    up front — but _resolve_conversation then creates the thread, and a client
    that reconnects and resends comes back carrying *that* id. Claiming only on
    the inbound thread_id lets the resend run a second turn concurrently.
    """
    redis = _FakeRedis()

    async def _creates_thread(*args, **kwargs):
        return SimpleNamespace(id=1, thread_id="t-new"), True

    _run(redis, _creates_thread, thread_id=None, request_id="req-1")

    assert redis.store.get("chat:turn:t-new") is None, "released at the end"
    assert [
        (key, nx, ex) for key, _tok, nx, ex in redis.set_calls
    ] == [("chat:turn:t-new", True, 600)], (
        "the freshly created thread must be locked for the rest of the turn"
    )


# ── the lock is held for as long as the turn runs ───────────────────────────

def test_the_lock_is_renewed_without_any_stream_events():
    """The renewal must not ride the event stream.

    `_run` never reaches the orchestrator — `_resolve_conversation` bails — so
    this turn emits *zero* stream events. A renewal happening anyway is the
    whole point: a tool that runs longer than the TTL emits nothing between
    `on_tool_start` and `on_tool_end` (graph.py discards sub-agent tokens), and
    an event-driven renewal would let the lock lapse mid-turn.
    """
    redis = _FakeRedis()
    renewals = []

    async def _slow_resolve(*args, **kwargs):
        await asyncio.sleep(0.05)
        return None, False

    with patch.object(ws_mod, "_LOCK_RENEW_EVERY_S", 0.005), \
         patch.object(ws_mod, "renew_lease",
                      lambda key, token, ttl: renewals.append(key) or True):
        _run(redis, _slow_resolve, request_id="req-1")

    assert renewals, "the lock was never renewed during a turn with no events"


def _hold_for(states, *, ttl, every, run_for, key="chat:turn:t-1"):
    """Run `_hold_turn_lock` against a scripted `renew_lease`, return lost-ness.

    `states` is what renew_lease reports in order; it repeats the last value
    once exhausted.
    """
    seq = iter(states)
    last = [states[-1]]

    def _renew(*_a):
        try:
            last[0] = next(seq)
        except StopIteration:
            pass
        return last[0]

    async def _drive():
        lost = asyncio.Event()
        task = asyncio.create_task(ws_mod._hold_turn_lock(lambda: key, "tok", lost))
        try:
            await asyncio.sleep(run_for)
        finally:
            task.cancel()
        return lost.is_set()

    with patch.object(ws_mod, "_LOCK_RENEW_EVERY_S", every), \
         patch.object(ws_mod, "_TURN_LOCK_TTL_S", ttl), \
         patch.object(ws_mod, "renew_lease", _renew):
        return asyncio.run(_drive())


def test_an_unreachable_redis_does_not_end_the_turn_immediately():
    """`renew_lease` returning None means *unknown*, not *lost*.

    Failing closed on the first blip would kill live turns over a dropped
    packet. The lease is still good until the TTL runs out measured from the
    last renewal we actually got confirmed.
    """
    # TTL is long relative to the run, so the deadline is nowhere near.
    assert _hold_for([None], ttl=10, every=0.01, run_for=0.06) is False, (
        "a Redis blip must not abandon a live turn"
    )


def test_an_unreachable_redis_ends_the_turn_before_the_lease_expires():
    """The other half, and the finding: we cannot work on an unconfirmed lease
    forever. Redis unreachable *from here* says nothing about the key — another
    replica may be reaching it fine and will acquire the moment our TTL lapses.
    """
    assert _hold_for([None], ttl=0.05, every=0.01, run_for=0.3) is True, (
        "kept working on a lease that had certainly expired"
    )


def test_a_confirmed_renewal_resets_the_deadline():
    """A flaky-but-reachable Redis must not kill long turns: every confirmed
    renewal restarts the clock."""
    assert _hold_for([True, None] * 40, ttl=0.05, every=0.01, run_for=0.3) is False


def test_a_confirmed_loss_ends_the_turn_at_once():
    """No deadline involved — False is Redis telling us the key is someone
    else's now."""
    assert _hold_for([False], ttl=10, every=0.01, run_for=0.05) is True


def test_the_renewal_does_not_outlive_the_turn():
    """Cancelled in the same `finally` that releases the lock — otherwise it
    keeps a thread alive that a *later* turn now owns."""
    redis = _FakeRedis()
    renewals = []

    with patch.object(ws_mod, "_LOCK_RENEW_EVERY_S", 0.005), \
         patch.object(ws_mod, "renew_lease",
                      lambda key, token, ttl: renewals.append(key) or True):
        _run(redis, _resolve_to_none, request_id="req-1")
        after_turn = len(renewals)
        # Give a leaked heartbeat every chance to tick again.
        asyncio.run(asyncio.sleep(0.05))

    assert len(renewals) == after_turn, "the renewal task outlived its turn"


# ── consumption races the loss, it does not poll it ─────────────────────────

def test_a_stalled_stream_still_stops_when_the_lock_is_lost():
    """The finding: checking a flag per event cannot notice a loss *between*
    events, and a long tool is exactly a gap between events — graph.py discards
    sub-agent tokens, so nothing is emitted from `on_tool_start` until
    `on_tool_end`. The wait has to race the stream itself.

    Bounded by wait_for on purpose: a poll-per-event implementation does not
    fail this test, it hangs forever on the stalled tool.
    """
    cancelled = []

    async def _stalls_after_one():
        yield {"type": "token", "content": "hi"}
        try:
            await asyncio.Future()  # a tool that never returns
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    async def _drive():
        lost = asyncio.Event()
        seen = []
        async for event in ws_mod._until_lock_lost(_stalls_after_one(), lost):
            seen.append(event)
            lost.set()  # ownership goes while the next step is stalled
        return seen

    seen = asyncio.run(asyncio.wait_for(_drive(), timeout=2))

    assert seen == [{"type": "token", "content": "hi"}]
    assert cancelled == [True], "the stalled tool was left running"


def test_a_stream_that_ends_normally_is_unaffected():
    async def _three():
        for i in range(3):
            yield {"n": i}

    async def _drive():
        lost = asyncio.Event()
        return [e async for e in ws_mod._until_lock_lost(_three(), lost)]

    assert asyncio.run(asyncio.wait_for(_drive(), timeout=2)) == [
        {"n": 0}, {"n": 1}, {"n": 2},
    ]


def test_resend_after_reconnect_on_a_just_created_thread_is_rejected():
    """The reconnect case that a lock keyed only on the inbound thread_id misses."""
    redis = _FakeRedis({"chat:turn:t-new": "req-1"})  # first turn still running

    async def _creates_thread(*args, **kwargs):
        return SimpleNamespace(id=1, thread_id="t-new"), False

    ws, _ = _run(redis, _creates_thread, thread_id=None, request_id="req-2")

    assert [m["error_code"] for m in ws.sent] == ["busy"]
    assert redis.store["chat:turn:t-new"] == "req-1", (
        "the losing turn must not steal or release the running turn's lock"
    )
    assert "chat:turn:t-new" not in redis.deleted
