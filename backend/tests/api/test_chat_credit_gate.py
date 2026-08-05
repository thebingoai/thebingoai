"""POST /api/chat credit gate — the REST path must bill like the websocket path.

The endpoint lost its credit wiring when the SSE stream variant was removed
(c1a1c4d), leaving an authenticated orchestrator run that bypassed the org
pool entirely. These tests pin the restored contract:

  - exhausted pool → 402 BEFORE the orchestrator runs,
  - success → persist the answer BEFORE charging (aexit(None) last),
  - orchestrator failure → aexit(exc) so the turn is never billed.

Note how failure arrives: run_orchestrator catches its own exceptions and
reports them in the RETURN VALUE (success=False), only raising for errors above
its internal try (agent construction, context build). Both shapes are pinned
here — billing on "no exception raised" alone charges for error messages.
"""
import asyncio
import types
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import backend.api.chat as chat_mod
from backend.schemas.chat import ChatRequest


class _FakeMgr:
    """Records lifecycle calls; optionally raises on enter."""

    instance = None

    def __init__(self, raise_on_enter=None, order=None, **kwargs):
        self.kwargs = kwargs
        self.calls = order if order is not None else []
        self._raise_on_enter = raise_on_enter
        self.voids = []
        _FakeMgr.instance = self

    def void(self, reason="unresolved"):
        self.voids.append(reason)
        self.calls.append(("void", reason))

    async def __aenter__(self):
        if self._raise_on_enter is not None:
            raise self._raise_on_enter
        self.calls.append("aenter")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.calls.append(("aexit", exc_type))
        return False


def _ctx_stub():
    return types.SimpleNamespace(
        agent_context="", custom_agents=None, memory_context=None,
        user_skills=None, user_memories_context=None, skill_suggestions=None,
        soul_prompt=None, profile=None,
    )


@pytest.fixture
def wired(monkeypatch):
    """Stub every heavy dependency of the chat handler; return the shared
    order log that the fake manager, orchestrator, and persist append to."""
    order = []

    conversation = types.SimpleNamespace(id="c-1", thread_id="t-1")

    def _create_conversation(db, uid, title):
        order.append("create-conversation")
        return conversation

    monkeypatch.setattr(
        chat_mod.ConversationService, "create_conversation",
        staticmethod(_create_conversation),
    )

    def _add_message(db, cid, role, content):
        order.append("persist" if role == "assistant" else "save-user-message")

    monkeypatch.setattr(
        chat_mod.ConversationService, "add_message", staticmethod(_add_message)
    )
    monkeypatch.setattr(
        chat_mod.ConversationService, "get_conversation_history",
        staticmethod(lambda db, tid, uid, limit=None, since_reset=True: []),
    )

    import backend.services.heartbeat_context as hb

    async def _build_ctx(**kw):
        return _ctx_stub()

    monkeypatch.setattr(hb, "build_orchestrator_context", _build_ctx)

    import backend.agents.profile_llm as pl
    monkeypatch.setattr(pl, "resolve_published_llm", lambda profile: (None, None, None))

    import backend.agents as agents

    async def _run_orchestrator(**kw):
        order.append("orchestrate")
        return {"message": "answer", "metadata": {}, "success": True}

    monkeypatch.setattr(agents, "run_orchestrator", _run_orchestrator)

    import backend.plugins.loader as loader
    monkeypatch.setattr(loader, "get_loaded_plugins", lambda: {})

    monkeypatch.setattr(
        chat_mod.TokenTrackingService, "track_usage", staticmethod(lambda **kw: None)
    )

    import backend.services.token_tracking_service as tts
    monkeypatch.setattr(
        tts, "CreditContextManager",
        lambda **kw: _FakeMgr(order=order, **kw),
    )
    return order


def _call(order):
    user = types.SimpleNamespace(id="u-1")
    req = ChatRequest(message="hello")
    return asyncio.run(chat_mod.chat(req, current_user=user, db=MagicMock()))


def test_success_persists_before_charging(wired):
    resp = _call(wired)
    assert resp.message == "answer"
    # Strict order: gate on entry, run, persist the answer, THEN charge.
    assert wired == [
        "aenter", "create-conversation", "save-user-message",
        "orchestrate", "persist", ("aexit", None),
    ]
    assert _FakeMgr.instance.voids == []  # a clean turn is billed


def _orchestrator_returning(wired, monkeypatch, result):
    import backend.agents as agents

    async def _run(**kw):
        wired.append("orchestrate")
        return result

    monkeypatch.setattr(agents, "run_orchestrator", _run)


def test_orchestrator_reporting_failure_is_voided_not_charged(wired, monkeypatch):
    # The common failure shape: run_orchestrator swallows the exception and
    # returns success=False with a friendly error as the "answer". Nothing
    # raises, so only an explicit void keeps the user from paying for it.
    _orchestrator_returning(wired, monkeypatch, {
        "message": "Something went wrong. Please try again.",
        "metadata": {},
        "success": False,
    })
    resp = _call(wired)
    assert resp.success is False
    assert _FakeMgr.instance.voids == ["orchestrator reported failure"]
    assert wired == [
        "aenter", "create-conversation", "save-user-message",
        "orchestrate", "persist",
        ("void", "orchestrator reported failure"), ("aexit", None),
    ]


def test_unresolved_layer4_retry_is_voided(wired, monkeypatch):
    # Same rule the websocket path applies: the judge retry never resolved the
    # question, so the turn is free — REST must not bill what the socket voids.
    _orchestrator_returning(wired, monkeypatch, {
        "message": "answer",
        "metadata": {},
        "success": True,
        "retry_succeeded": False,
    })
    _call(wired)
    assert _FakeMgr.instance.voids == ["layer4_retry_failed"]


def test_successful_retry_is_still_billed(wired, monkeypatch):
    # retry_succeeded=True means the retry fixed it — a resolved turn is billed.
    _orchestrator_returning(wired, monkeypatch, {
        "message": "answer",
        "metadata": {},
        "success": True,
        "retry_succeeded": True,
    })
    _call(wired)
    assert _FakeMgr.instance.voids == []


def test_exhausted_pool_returns_402_before_orchestrator(wired, monkeypatch):
    import backend.services.token_tracking_service as tts
    monkeypatch.setattr(
        tts, "CreditContextManager",
        lambda **kw: _FakeMgr(
            raise_on_enter=tts.InsufficientCreditsError(reason="org_pool"),
            order=wired, **kw,
        ),
    )
    with pytest.raises(HTTPException) as ex:
        _call(wired)
    assert ex.value.status_code == 402
    assert ex.value.detail["cap"] == "org_pool"
    # Nothing ran AND nothing was written: add_message() commits on the spot, so
    # gating after it would leave the rejected prompt in the user's history (fed
    # back as context next turn) plus an orphan "Untitled" conversation.
    assert wired == []


def test_402_into_existing_thread_leaves_no_ghost_message(wired, monkeypatch):
    # Same rule for a thread that already exists: the rejected prompt must not be
    # appended to a real conversation's history.
    import backend.services.token_tracking_service as tts
    monkeypatch.setattr(
        chat_mod.ConversationService, "get_conversation_by_thread",
        staticmethod(lambda db, tid, uid: types.SimpleNamespace(id="c-1", thread_id="t-1")),
    )
    monkeypatch.setattr(
        tts, "CreditContextManager",
        lambda **kw: _FakeMgr(
            raise_on_enter=tts.InsufficientCreditsError(reason="org_pool"),
            order=wired, **kw,
        ),
    )
    user = types.SimpleNamespace(id="u-1")
    with pytest.raises(HTTPException) as ex:
        asyncio.run(chat_mod.chat(
            ChatRequest(message="hello", thread_id="t-1"),
            current_user=user, db=MagicMock(),
        ))
    assert ex.value.status_code == 402
    assert "save-user-message" not in wired


def test_conversation_id_is_attached_to_the_billed_turn(wired):
    # The gate runs before the conversation exists, so the manager starts with
    # conversation_id=None; the usage row still has to name the conversation it
    # belongs to once one is created.
    _call(wired)
    assert _FakeMgr.instance.conversation_id == "c-1"
    # Gate first, then the writes it protects.
    assert wired[:3] == ["aenter", "create-conversation", "save-user-message"]


def test_orchestrator_raising_exits_with_exception_and_reraises(wired, monkeypatch):
    # The rarer shape: run_orchestrator only raises for failures above its own
    # try (agent construction, context build) — those must reach __aexit__.
    import backend.agents as agents

    async def _boom(**kw):
        wired.append("orchestrate")
        raise RuntimeError("agent died")

    monkeypatch.setattr(agents, "run_orchestrator", _boom)
    with pytest.raises(RuntimeError):
        _call(wired)
    # __aexit__ received the exception → the manager skips billing.
    assert wired == [
        "aenter", "create-conversation", "save-user-message",
        "orchestrate", ("aexit", RuntimeError),
    ]


def test_billing_teardown_error_does_not_mask_the_real_failure(wired, monkeypatch):
    # If __aexit__ blows up while unwinding a failed turn, the caller must still
    # see the orchestrator's error, not the billing one.
    import backend.agents as agents
    import backend.services.token_tracking_service as tts

    async def _boom(**kw):
        raise RuntimeError("agent died")

    class _ExplodingMgr(_FakeMgr):
        async def __aexit__(self, exc_type, exc, tb):
            raise ValueError("credit teardown exploded")

    monkeypatch.setattr(agents, "run_orchestrator", _boom)
    monkeypatch.setattr(
        tts, "CreditContextManager", lambda **kw: _ExplodingMgr(order=wired, **kw)
    )
    with pytest.raises(RuntimeError, match="agent died"):
        _call(wired)


def test_manager_setup_failure_degrades_to_unbilled_turn(wired, monkeypatch):
    # Credit wiring must never block chat: a non-credit setup error proceeds
    # unbilled, same as the websocket path.
    import backend.services.token_tracking_service as tts

    def _broken(**kw):
        raise RuntimeError("plugin loader down")

    monkeypatch.setattr(tts, "CreditContextManager", _broken)
    resp = _call(wired)
    assert resp.message == "answer"
    assert wired == [
        "create-conversation", "save-user-message", "orchestrate", "persist",
    ]
