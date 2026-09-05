"""Guards for the orchestrator chat-chart routing `tools` refresh.

Editing `profile_defaults._ORCHESTRATOR_TOOLS` reaches nobody: `seed_default_profile`
only INSERTs, and `ProfileRenderer.resolve` lets any non-NULL stored column win over
the module default. Without this revision every already-seeded user keeps being told
"visualizations -> use create_dashboard" and never routes to `generate_chat_chart`.

Modelled on test_migration_w1dgc4p0001.py.
"""
import ast
import hashlib
import importlib.util
import json
import pathlib

import pytest
import sqlalchemy as sa

_VERSIONS = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
_MIGRATION = _VERSIONS / "chrtr0ut01_refresh_orchestrator_chart_routing.py"
_PREVIOUS = _VERSIONS / "0rch5c0pe01_refresh_orchestrator_profile_scoping.py"


def _literal(name: str, path=None):
    tree = ast.parse((path or _MIGRATION).read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets)
    )


def _load_module():
    """Load by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_chrtr0ut01", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chains_onto_the_chart_specs_revision():
    mod = _load_module()
    assert mod.revision == "chrtr0ut01"
    assert mod.down_revision == "chrtspecs01"
    assert callable(mod.upgrade) and callable(mod.downgrade)


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this historical revision's result
    changes every time someone edits the routing guide."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import" not in src
    assert "_NEW_TOOLS" in src


def test_snapshot_matches_current_defaults():
    from backend.agents.profile_defaults import DEFAULTS

    assert _literal("_NEW_TOOLS") == DEFAULTS["orchestrator"]["tools"]


def test_snapshot_carries_the_chart_routing():
    new_tools = _literal("_NEW_TOOLS")
    assert "generate_chat_chart" in new_tools
    assert "select_dashboard_widget" in new_tools
    # The line that mis-routed every ad-hoc chart request into a dashboard build.
    assert "Requests to create dashboards or visualizations" not in new_tools


def test_old_hashes_include_the_text_the_previous_revision_wrote():
    """Installs sitting at 0rch5c0pe01 hold the text it wrote. If its digest is
    not in the match set they are skipped forever and never see the new routing."""
    inherited = _literal("_OLD_TOOLS_HASHES", _PREVIOUS)
    old_hashes = _literal("_OLD_TOOLS_HASHES")
    assert inherited <= old_hashes

    written = _literal("_NEW_TOOLS", _PREVIOUS)
    assert hashlib.sha256(written.encode()).hexdigest() in old_hashes

    # …and the current default must NOT be treated as old, or every fresh install
    # rewrites a row with the text it already has.
    mod = _load_module()
    assert mod._is_old_tools(_literal("_NEW_TOOLS")) is False


def test_matcher_spares_user_edited_text():
    mod = _load_module()
    assert mod._is_old_tools("a routing guide the user rewrote themselves") is False
    assert mod._is_old_tools(None) is False
    assert mod._is_old_tools("") is False


def test_matcher_keys_on_the_digest_set(monkeypatch):
    mod = _load_module()
    text = "SOME OLD TOOLS TEXT"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    monkeypatch.setattr(mod, "_OLD_TOOLS_HASHES", {digest})
    assert mod._is_old_tools(text) is True
    assert mod._is_old_tools("something else") is False


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


def _row(conn, rid):
    return conn.execute(
        sa.text("SELECT * FROM agent_profiles WHERE id = :i"), {"i": rid}
    ).mappings().first()


def _run_upgrade(conn, monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod.op, "get_bind", lambda: conn)
    mod.upgrade()


def test_a_row_holding_the_previous_text_is_rewritten(conn, monkeypatch):
    previous = _literal("_NEW_TOOLS", _PREVIOUS)
    _seed(conn, id=1, agent_type="orchestrator", tools=previous, published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["tools"] == _literal("_NEW_TOOLS")


def test_the_published_snapshot_is_refreshed_too(conn, monkeypatch):
    """resolve() re-applies the snapshot over the stored column, so a stale
    snapshot would keep serving the old routing until the user re-publishes."""
    previous = _literal("_NEW_TOOLS", _PREVIOUS)
    _seed(conn, id=1, agent_type="orchestrator", tools=previous,
          published_snapshot=json.dumps({"identity": "mine", "tools": previous}))
    _run_upgrade(conn, monkeypatch)
    snapshot = json.loads(_row(conn, 1)["published_snapshot"])
    assert snapshot["tools"] == _literal("_NEW_TOOLS")
    assert snapshot["identity"] == "mine", "untouched sections must survive"


def test_user_edited_tools_are_left_alone(conn, monkeypatch):
    mine = "## Tool Usage Guide\n- do it my way"
    _seed(conn, id=1, agent_type="orchestrator", tools=mine, published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["tools"] == mine


def test_other_agent_types_are_untouched(conn, monkeypatch):
    previous = _literal("_NEW_TOOLS", _PREVIOUS)
    _seed(conn, id=1, agent_type="dashboard_agent", tools=previous, published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["tools"] == previous


def test_upgrade_is_idempotent(conn, monkeypatch):
    previous = _literal("_NEW_TOOLS", _PREVIOUS)
    _seed(conn, id=1, agent_type="orchestrator", tools=previous, published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["tools"] == _literal("_NEW_TOOLS")
