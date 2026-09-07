"""Guards for the orchestrator output-constraints refresh.

`_render_orchestrator_prompt` renders the stored `agent_profiles` row, not the
module defaults. "Never include SQL in your reply" had lived in the chassis
constant since 38f4d98 and in no seeded row, so the live prompt never carried
it — which is how, under the privacy floor, the agent came to paste a ```sql
fence and tell the user to run it themselves.

Modelled on test_migration_0rch5c0pe01.py.
"""
import ast
import importlib.util
import json
import pathlib

import pytest
import sqlalchemy as sa

_VERSIONS = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
_MIGRATION = _VERSIONS / "0utc0nstr01_refresh_orchestrator_output_constraints.py"
_PREVIOUS = _VERSIONS / "0rch5c0pe01_refresh_orchestrator_profile_scoping.py"


def _literal(name: str, path: pathlib.Path = _MIGRATION):
    tree = ast.parse(path.read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets)
    )


def _load_module():
    """Load by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_0utc0nstr01", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- shape --------------------------------------------------------------


def test_migration_file_parses_and_exposes_the_expected_names():
    mod = _load_module()
    assert mod.revision == "0utc0nstr01"
    assert mod.down_revision == "w1dgc4p0002"
    assert callable(mod.upgrade) and callable(mod.downgrade)


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this revision's result changes every
    time someone edits a prompt block."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import" not in src
    assert "orchestrator_prompt_blocks" not in src.split('"""', 2)[-1]


def test_old_identities_are_texts_ordered_longest_first():
    olds = _literal("_OLD_IDENTITIES")
    assert olds and all(isinstance(t, str) and t for t in olds)
    assert list(olds) == sorted(olds, key=len, reverse=True)


# --- the snapshot is current --------------------------------------------


def test_snapshot_matches_the_current_defaults():
    """A stale snapshot silently writes the wrong text to every seeded row."""
    from backend.agents.profile_defaults import DEFAULTS

    assert _literal("_NEW_IDENTITY") == DEFAULTS["orchestrator"]["identity"]


def test_the_immediately_previous_default_is_matched():
    """Rows seeded by 0rch5c0pe01 are exactly the rows this must reach."""
    assert _literal("_NEW_IDENTITY", _PREVIOUS) in _literal("_OLD_IDENTITIES")


def test_the_new_text_extends_the_old_rather_than_replacing_it():
    """The block is appended, so the scoping and ask rules survive untouched."""
    new = _literal("_NEW_IDENTITY")
    old = _literal("_NEW_IDENTITY", _PREVIOUS)
    assert new.startswith(old)
    assert "ask_user_question Rules" in new


def test_the_new_text_is_not_itself_a_known_old_default():
    """Otherwise upgrade would loop on its own output."""
    new = _literal("_NEW_IDENTITY")
    for old in _literal("_OLD_IDENTITIES"):
        assert not new.endswith(old)


def test_snapshot_carries_the_rules_this_revision_exists_for():
    identity = _literal("_NEW_IDENTITY")
    assert "Never include SQL" in identity
    assert "values_withheld" in identity
    assert "rendered directly under your message" in identity


# --- behaviour against a real table -------------------------------------


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


def _old():
    return _literal("_OLD_IDENTITIES")[0]


def test_a_seeded_row_is_rewritten(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=_old(), published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == _literal("_NEW_IDENTITY")


def test_a_personalized_row_keeps_its_header(conn, monkeypatch):
    """render_identity_text glues a name header on; hashing the whole column
    would skip exactly these rows, which in production are the majority."""
    personalized = "Your name is Ada.\n\n" + _old()
    _seed(conn, id=1, agent_type="orchestrator", identity=personalized, published_snapshot=None)
    _run_upgrade(conn, monkeypatch)

    got = _row(conn, 1)["identity"]
    assert got.startswith("Your name is Ada.\n\n")
    assert got.endswith(_literal("_NEW_IDENTITY"))
    assert "values_withheld" in got


def test_the_published_snapshot_is_refreshed_and_keeps_its_other_sections(conn, monkeypatch):
    """The snapshot feeds the live render path — a stale one means the rule
    only appears after the user next re-publishes."""
    snap = json.dumps({"identity": _old(), "soul": "keep me", "tools": "untouched"})
    _seed(conn, id=1, agent_type="orchestrator", identity=_old(), published_snapshot=snap)
    _run_upgrade(conn, monkeypatch)

    out = json.loads(_row(conn, 1)["published_snapshot"])
    assert out["identity"] == _literal("_NEW_IDENTITY")
    assert out["soul"] == "keep me"
    assert out["tools"] == "untouched"


def test_a_hand_edited_identity_is_left_alone(conn, monkeypatch):
    """Only known defaults are rewritten; someone's own text is theirs."""
    _seed(conn, id=1, agent_type="orchestrator", identity="I wrote this myself.",
          published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == "I wrote this myself."


def test_other_agent_types_are_untouched(conn, monkeypatch):
    _seed(conn, id=1, agent_type="dashboard_agent", identity=_old(), published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == _old()


def test_a_null_identity_does_not_crash(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=None, published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] is None


def test_running_twice_changes_nothing_the_second_time(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=_old(), published_snapshot=None)
    _run_upgrade(conn, monkeypatch)
    first = _row(conn, 1)["identity"]
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == first


def test_a_malformed_snapshot_is_skipped_not_fatal(conn, monkeypatch):
    _seed(conn, id=1, agent_type="orchestrator", identity=_old(),
          published_snapshot="{not json")
    _run_upgrade(conn, monkeypatch)
    assert _row(conn, 1)["identity"] == _literal("_NEW_IDENTITY")


# --- chain --------------------------------------------------------------


def test_exactly_one_alembic_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = pathlib.Path(__file__).resolve().parents[3]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert list(heads) == ["0utc0nstr01"], heads
