"""Guards for the dashboard_agent widget-cap `tools` refresh.

The prompt said "max 17" while `dashboard_widget_verifier.MAX_TOTAL_WIDGETS` rejected
anything over 15 — a compliant agent still got bounced, twice, for ~119s of a 200s
build. Fixing the source constant only reaches the inline path and freshly-seeded
profiles; rows an earlier revision seeded keep the old text forever without this
migration.
"""
import ast
import hashlib
import importlib.util
import pathlib

_VERSIONS = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
_MIGRATION = _VERSIONS / "w1dgc4p0001_refresh_dashboard_profile_widget_cap.py"
_PREVIOUS = _VERSIONS / "d0cst0ry0a1b_refresh_agent_tools_docs_story_no_avg.py"


def _literal(name: str, path=None):
    tree = ast.parse((path or _MIGRATION).read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets)
    )


def _load_module():
    """Load by file path — alembic/versions is not a package."""
    spec = importlib.util.spec_from_file_location("_mig_w1dgc4p0001", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chains_onto_the_current_head():
    mod = _load_module()
    assert mod.revision == "w1dgc4p0001"
    assert mod.down_revision == "0rch5c0pe01"


def test_no_live_defaults_import_at_upgrade():
    """The snapshot must be a literal, or this revision's result changes every time
    someone edits a prompt block."""
    src = _MIGRATION.read_text()
    assert "from backend.agents.profile_defaults import DEFAULTS" not in src
    assert "_NEW_TOOLS" in src


_NEXT = _VERSIONS / "w1dgc4p0002_refresh_dashboard_profile_soft_widget_cap.py"


def test_snapshot_is_frozen():
    """`tools` is no longer asserted against DEFAULTS: w1dgc4p0002 supersedes this
    revision (the cap became a target), and its own guard holds the equality.
    Historical revisions keep their frozen literal — same split
    test_migration_d0cst0ry0a1b.py made once this revision took over."""
    assert hashlib.sha256(_literal("_NEW_TOOLS").encode()).hexdigest() == (
        "1b8d7715dc50f093bbf6ec925054bcbd11e7086155dcf07495a76cd18a221bca"
    )


def test_snapshot_is_recognised_downstream():
    """The text this revision wrote must be in the next revision's match set, or
    installs that ran it are skipped forever."""
    written = _literal("_NEW_TOOLS")
    assert hashlib.sha256(written.encode()).hexdigest() in _literal("_OLD_TOOLS_HASHES", _NEXT)


def test_snapshot_carries_the_enforced_cap():
    from backend.agents.orchestrator.dashboard_widget_verifier import MAX_TOTAL_WIDGETS

    new_tools = _literal("_NEW_TOOLS")
    assert f"{MAX_TOTAL_WIDGETS} widgets is a HARD cap" in new_tools
    assert "max 17" not in new_tools


def test_old_hashes_include_the_text_the_previous_revision_wrote():
    """Installs sitting at d0cst0ry0a1b hold the text it wrote. If its digest is not
    in the match set they are skipped forever and never see the new cap."""
    import hashlib

    # Every digest the previous revision matched on…
    inherited = _literal("_OLD_TOOLS_HASHES", _PREVIOUS)["dashboard_agent"]
    old_hashes = _literal("_OLD_TOOLS_HASHES")
    assert inherited <= old_hashes

    # …plus the text it actually writes, which is what a fresh install holds when
    # it arrives here. Asserted by digest rather than by set size: more than one
    # d0cst0ry0a1b text is in the wild, and dropping either one strands whoever
    # is holding it.
    written = _literal("_NEW_TOOLS", _PREVIOUS)["dashboard_agent"]
    assert hashlib.sha256(written.encode()).hexdigest() in old_hashes

    # …and the current default must NOT be treated as old, or every fresh install
    # rewrites a row with the text it already has.
    mod = _load_module()
    assert mod._is_old_default(_literal("_NEW_TOOLS")) is False


def test_matcher_spares_user_edited_text():
    mod = _load_module()
    assert mod._is_old_default("text a user wrote themselves") is False
    assert mod._is_old_default(None) is False
    assert mod._is_old_default("") is False


def test_matcher_keys_on_the_digest_set(monkeypatch):
    mod = _load_module()
    text = "SOME OLD TOOLS TEXT"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    monkeypatch.setattr(mod, "_OLD_TOOLS_HASHES", {digest})
    assert mod._is_old_default(text) is True
    assert mod._is_old_default("something else") is False
