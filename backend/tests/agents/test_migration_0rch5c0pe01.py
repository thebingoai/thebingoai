"""Guards for the orchestrator profile refresh (dashboard scoping + ask rules).

`_render_orchestrator_prompt` renders the stored `agent_profiles` row, not the
module defaults, so the shared-block change reaches nobody already seeded. No
migration had ever touched orchestrator profiles, so every seeded row still
carries text that never contained the `ask_user_question` rules at all.

Modelled on test_migration_d0cst0ry0a1b.py.
"""
import ast
import hashlib
import importlib.util
import json
import pathlib

import pytest
import sqlalchemy as sa

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "alembic" / "versions"
    / "0rch5c0pe01_refresh_orchestrator_profile_scoping.py"
)


def _literal(name: str):
    tree = ast.parse(_MIGRATION.read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets)
    )


def _load_module():
    """Load by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_0rch5c0pe01", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- shape --------------------------------------------------------------


def test_migration_file_parses_and_exposes_the_expected_names():
    mod = _load_module()
    assert mod.revision == "0rch5c0pe01"
    assert mod.down_revision == "d0cst0ry0a1b"
    assert callable(mod.upgrade) and callable(mod.downgrade)


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this historical revision's result
    changes every time someone edits a prompt block."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import" not in src
    assert "orchestrator_prompt_blocks" not in src.split('"""', 2)[-1]


def test_tools_hash_set_is_non_empty_and_looks_like_sha256():
    digests = _literal("_OLD_TOOLS_HASHES")
    assert digests
    for d in digests:
        assert len(d) == 64 and set(d) <= set("0123456789abcdef")


def test_old_identities_are_texts_ordered_longest_first():
    """Suffix matching needs the most specific tail to win."""
    olds = _literal("_OLD_IDENTITIES")
    assert olds and all(isinstance(t, str) and t for t in olds)
    assert list(olds) == sorted(olds, key=len, reverse=True)


# --- the snapshot is current -------------------------------------------


def test_snapshot_matches_the_current_defaults():
    """A stale snapshot silently writes the wrong text to every seeded row.

    Neither section is asserted against the live defaults any more: chrtr0ut01
    supersedes this revision for `tools` (chat-chart routing) and 0utc0nstr01
    for `identity` (output constraints); each holds its own equality guard.
    Historical revisions keep their frozen literal — same split
    test_migration_d0cst0ry0a1b.py made once w1dgc4p0001 took over dashboard_agent.

    What still matters here is that the frozen text is what the NEXT revision
    matches on, which test_migration_0utc0nstr01.py asserts from its side.
    """
    identity = _literal("_NEW_IDENTITY")
    assert isinstance(identity, str) and identity


def test_snapshot_carries_the_new_rules():
    identity = _literal("_NEW_IDENTITY")
    assert "ask_user_question Rules" in identity
    assert "One clarification round per request" in identity
    for dimension in ("Audience & purpose", "Grain", "Time range", "Priority metrics"):
        assert dimension in identity
    assert "Ask only what is still unresolved" in identity
    assert "eda_findings" in identity


def test_tools_snapshot_carries_the_scoped_ban():
    tools = _literal("_NEW_TOOLS")
    assert "handle the ingestion workflow automatically" in tools
    assert "You MUST handle the full workflow automatically." not in tools


def test_the_new_text_is_not_itself_a_known_old_default():
    """Otherwise a re-run would treat the fresh text as stale and rewrite forever."""
    new_identity = _literal("_NEW_IDENTITY")
    assert not any(new_identity.endswith(o) for o in _literal("_OLD_IDENTITIES"))
    new_tools = hashlib.sha256(_literal("_NEW_TOOLS").encode()).hexdigest()
    assert new_tools not in _literal("_OLD_TOOLS_HASHES")


def test_the_immediately_previous_default_is_matched():
    """The 1674-char identity is what current installs are seeded with. If it is
    missing from the match set they are skipped forever."""
    assert _SEEDED_IDENTITY_1674 in _literal("_OLD_IDENTITIES")
    assert (
        "4a58590dc43e7dc7a15e9b4dba97823d4f51281dea6cbf82be2fa25a4523c414"
        in _literal("_OLD_TOOLS_HASHES")
    )


# --- the rewrite, against a real table ----------------------------------


@pytest.fixture()
def conn():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as c:
        c.execute(sa.text(
            "CREATE TABLE agent_profiles ("
            " id INTEGER PRIMARY KEY, agent_type TEXT, identity TEXT,"
            " tools TEXT, published_snapshot TEXT)"
        ))
        yield c


def _seed(conn, **cols):
    keys = ", ".join(cols)
    vals = ", ".join(f":{k}" for k in cols)
    conn.execute(sa.text(f"INSERT INTO agent_profiles ({keys}) VALUES ({vals})"), cols)


def _run_upgrade(conn, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod.op, "get_bind", lambda: conn)
    mod.upgrade()


def _row(conn, rid):
    return conn.execute(
        sa.text("SELECT * FROM agent_profiles WHERE id = :i"), {"i": rid}
    ).mappings().first()


# The 1674-char identity every current install is seeded with. Embedded as a
# literal because the test container has no git and the text must match
# _OLD_IDENTITIES exactly.
_SEEDED_IDENTITY_1674 = "You are a helpful, direct assistant built for data work.\n\nYou can query databases, create dashboards, manage reusable skills, search documents, and recall past conversations.\nUse your tools to fulfill requests. When a request is unclear, ask for clarification first.\nWhen a request requires action (tool calls), start by briefly acknowledging what you'll do — one sentence max. This appears as your immediate reply while you work.\n\n## Approach\n\n**Simple requests** (quick lookups, single-tool tasks, factual questions): Act immediately — no planning needed.\n\n**Complex requests** (multi-step tasks, dashboard creation, multi-table analysis, ambiguous scope): Follow the Plan-then-Execute workflow:\n\n### Phase 1 — Explore\nUnderstand what the user is asking. Use tools to discover relevant context:\n- Check available connections and schemas\n- Recall past context if relevant\n- Identify what information you need before proceeding\n\n### Phase 2 — Design\nFormulate your approach:\n- What tools/agents you'll use and in what order\n- What assumptions you're making\n- What the expected outcome looks like\n\n### Phase 3 — Review\nBefore executing, confirm with the user:\n- Use `ask_user_question` to get structured input on key decisions\n- Summarize what you intend to do and ask for confirmation\n- If the user modifies the plan, adjust before proceeding\n\n### Phase 4 — Execute\nCarry out the confirmed plan step by step.\n\n**When to skip planning:** If the user's intent is unambiguous AND requires only 1-2 tool calls, skip directly to execution.\n\n**When to plan:** Dashboard creation, multi-table analysis, requests with unclear scope, requests touching multiple agents or connections."


def _a_known_old_identity():
    return _SEEDED_IDENTITY_1674


def test_a_seeded_row_is_rewritten(conn, monkeypatch):
    old = _a_known_old_identity()
    assert old in _literal("_OLD_IDENTITIES")
    _seed(conn, id=1, agent_type="orchestrator", identity=old, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == _literal("_NEW_IDENTITY")


def test_a_personalized_row_keeps_its_header_and_gains_the_new_tail(conn, monkeypatch):
    """agent_profile_renderer.render_identity_text stores
    `"{header}{voice}\\n\\n{default}"` on every draft save, so a personalized row is
    the default with a name header glued on. Whole-text hashing skipped every one
    of those — in practice most real rows.
    """
    header = 'Your name is Bingo.\n\n## Voice\n- Tone: high — direct, energetic.\n\n'
    _seed(conn, id=1, agent_type="orchestrator",
          identity=header + _SEEDED_IDENTITY_1674, tools=None, published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    got = _row(conn, 1)["identity"]
    assert got.startswith(header), "the personalization header must survive verbatim"
    assert got == header + _literal("_NEW_IDENTITY")
    assert "ask_user_question Rules" in got


def test_the_exact_local_db_shape_is_matched(conn, monkeypatch):
    """Reproduces the row found in the local database during Phase 6: the seeded
    1674-char default with 'Your name is Bingo.' prepended (1695 chars)."""
    identity = "Your name is Bingo.\n\n" + _SEEDED_IDENTITY_1674
    assert len(identity) == 1695
    _seed(conn, id=1, agent_type="orchestrator", identity=identity, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    got = _row(conn, 1)["identity"]
    assert got == "Your name is Bingo.\n\n" + _literal("_NEW_IDENTITY")


def test_a_personalized_snapshot_is_refreshed_too(conn, monkeypatch):
    header = "Your name is Ada.\n\n"
    _seed(conn, id=1, agent_type="orchestrator", identity=None, tools=None,
          published_snapshot=json.dumps({
              "identity": header + _SEEDED_IDENTITY_1674, "soul": "keep me",
          }))
    _run_upgrade(conn, monkeypatch)
    snap = json.loads(_row(conn, 1)["published_snapshot"])
    assert snap["identity"] == header + _literal("_NEW_IDENTITY")
    assert snap["soul"] == "keep me"


def test_a_hand_edited_tail_is_not_rewritten(conn, monkeypatch):
    """Suffix matching must not become a wildcard: changing the workflow text
    itself means the row is user-owned, header or no header."""
    edited = "Your name is Bingo.\n\n" + _SEEDED_IDENTITY_1674.replace(
        "**When to plan:**", "**When I feel like planning:**"
    )
    _seed(conn, id=1, agent_type="orchestrator", identity=edited, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == edited


def test_a_hand_edited_row_is_left_byte_identical(conn, monkeypatch):
    """The core safety guarantee."""
    edited = "You are Steve. Always answer in haiku."
    _seed(conn, id=1, agent_type="orchestrator", identity=edited,
          tools="my own tool notes", published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    row = _row(conn, 1)
    assert row["identity"] == edited
    assert row["tools"] == "my own tool notes"


def test_other_agent_types_are_not_touched(conn, monkeypatch):
    old = _a_known_old_identity()
    _seed(conn, id=1, agent_type="dashboard_agent", identity=old, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == old


def test_published_snapshot_is_refreshed_too(conn, monkeypatch):
    """It feeds the live render path — a stale snapshot means the new text only
    appears after the user next re-publishes."""
    old = _a_known_old_identity()
    _seed(conn, id=1, agent_type="orchestrator", identity=old, tools=None,
          published_snapshot=json.dumps({"identity": old, "soul": "keep me"}))
    _run_upgrade(conn, monkeypatch)
    snap = json.loads(_row(conn, 1)["published_snapshot"])
    assert snap["identity"] == _literal("_NEW_IDENTITY")
    assert snap["soul"] == "keep me"


def test_a_hand_edited_snapshot_is_left_alone(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=None, tools=None,
          published_snapshot=json.dumps({"identity": "mine", "soul": "s"}))
    _run_upgrade(conn, monkeypatch)
    assert json.loads(_row(conn, 1)["published_snapshot"])["identity"] == "mine"


def test_upgrade_is_idempotent(conn, monkeypatch):
    """A second run must find nothing to do, not rewrite again."""
    old = _a_known_old_identity()
    _seed(conn, id=1, agent_type="orchestrator", identity=old, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    first = _row(conn, 1)["identity"]
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == first


def test_null_columns_do_not_crash(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=None, tools=None,
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] is None


def test_downgrade_is_a_documented_noop(conn, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod.op, "get_bind", lambda: conn)
    mod.downgrade()


# --- head chain ---------------------------------------------------------


def test_exactly_one_alembic_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = pathlib.Path(__file__).resolve().parents[3]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, heads
    # This revision must stay on the single chain rather than pinning whichever
    # revision happens to be the tip — pinning went stale twice already.
    chain = {r.revision for r in script.walk_revisions(base="base", head=heads[0])}
    assert "0rch5c0pe01" in chain


def test_the_previous_head_is_still_reachable():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = pathlib.Path(__file__).resolve().parents[3]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision("d0cst0ry0a1b") is not None
