"""Guards for the dashboard_agent soft-widget-cap `tools` refresh.

The prompt promised a rejection ("15 widgets is a HARD cap") that the code no
longer performs. Fixing the source block only reaches the inline path and
freshly-seeded profiles; rows an earlier revision seeded keep the old text
forever without this migration.
"""
import ast
import hashlib
import importlib.util
import pathlib

_VERSIONS = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
_MIGRATION = _VERSIONS / "w1dgc4p0002_refresh_dashboard_profile_soft_widget_cap.py"
_PREVIOUS = _VERSIONS / "w1dgc4p0001_refresh_dashboard_profile_widget_cap.py"


def _literal(name: str, path=None):
    tree = ast.parse((path or _MIGRATION).read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets)
    )


def _load_module():
    """Load by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_w1dgc4p0002", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chains_onto_the_current_head():
    mod = _load_module()
    assert mod.revision == "w1dgc4p0002"
    assert mod.down_revision == "chrtr0ut01"


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this revision's result changes every time
    someone edits a prompt block."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import DEFAULTS" not in src
    assert "_NEW_TOOLS" in src


def test_snapshot_matches_current_defaults():
    from backend.agents.profile_defaults import DEFAULTS

    assert _literal("_NEW_TOOLS") == DEFAULTS["dashboard_agent"]["tools"]


def test_snapshot_states_a_target_not_a_gate():
    from backend.agents.orchestrator.dashboard_widget_verifier import MAX_TOTAL_WIDGETS

    new_tools = _literal("_NEW_TOOLS")
    assert f"11-{MAX_TOTAL_WIDGETS} data widgets" in new_tools
    assert "not counted" in new_tools
    assert "HARD cap" not in new_tools


def test_old_hashes_include_the_text_the_previous_revision_wrote():
    """Installs sitting at w1dgc4p0001 hold the text it wrote. If its digest is not
    in the match set they are skipped forever and keep promising a rejection."""
    inherited = _literal("_OLD_TOOLS_HASHES", _PREVIOUS)
    old_hashes = _literal("_OLD_TOOLS_HASHES")
    assert inherited <= old_hashes

    written = _literal("_NEW_TOOLS", _PREVIOUS)
    assert hashlib.sha256(written.encode()).hexdigest() in old_hashes
