"""Callers that hold a session must hand it to the connector factory.

`test_agent_txn_release.py` already proves the factory *forwards* a session it is
given. This proves the callers actually give it one — the half that was missed,
and the half that costs pool slots.

`get_connector_for_connection(connection)` with no session makes the connector
resolve its DataPlane on a session it opens itself, *while the caller still holds
its own*. `data_plane_service.get_plane_for_connection` documents where that
goes: under pool pressure the thread waits `db_pool_timeout` for a second slot
while pinning the first, "which is how contention becomes a pile-up rather than a
queue". With 20 PgBouncer slots in production, widget serving and the SQL API
doing this per request is the mechanism that turns load into collapse.

A static scan rather than a test per call site: the failure mode is *omission*,
so what needs guarding is the shape of every call — including the next one
somebody writes. Mocking eleven FastAPI handlers would test less and cost more.
"""

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Call sites that legitimately pass no session, with the reason. Anything else
# holding a session and omitting it is the bug this file exists to catch.
ALLOWED = {
    # The session is opened, used, and closed in a `finally` *above* the loop
    # that builds connectors — nothing is held by the time the factory runs, so
    # there is no second checkout to avoid. Passing `db` here would hand over a
    # closed session.
    ("agents/dashboard_tools.py", "_resolve_widget_connections"),
}


def _enclosing_function(tree: ast.Module, node: ast.AST) -> str:
    """Name of the innermost function containing *node*, or '<module>'."""
    best, best_span = "<module>", None
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.lineno <= node.lineno <= (fn.end_lineno or fn.lineno):
            span = (fn.end_lineno or fn.lineno) - fn.lineno
            if best_span is None or span < best_span:
                best, best_span = fn.name, span
    return best


def _sessionless_calls():
    """Every `get_connector_for_connection(...)` call passing no session."""
    for path in BACKEND.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name != "get_connector_for_connection":
                continue
            has_session = len(node.args) > 1 or any(
                kw.arg == "db_session" for kw in node.keywords
            )
            if has_session:
                continue
            rel = str(path.relative_to(BACKEND))
            yield rel, node.lineno, _enclosing_function(tree, node)


def test_every_caller_holding_a_session_forwards_it():
    offenders = [
        (rel, line, fn)
        for rel, line, fn in _sessionless_calls()
        if (rel, fn) not in ALLOWED
    ]

    assert not offenders, (
        "these call sites build a connector without handing over the session "
        "they already hold, so the connector opens a second pool checkout "
        "against the first:\n"
        + "\n".join(f"  {rel}:{line} in {fn}()" for rel, line, fn in sorted(offenders))
        + "\n\nPass the session: get_connector_for_connection(connection, db). "
        "If the caller genuinely holds none, add it to ALLOWED with the reason."
    )
