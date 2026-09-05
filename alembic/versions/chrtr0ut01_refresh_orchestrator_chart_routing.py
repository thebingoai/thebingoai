"""Refresh seeded orchestrator profiles: chat-chart tool routing.

The chat-chart branch added two tools (`generate_chat_chart`,
`select_dashboard_widget`) and rewrote the `tools` routing guide in
profile_defaults so ad-hoc chart requests stop routing to `create_dashboard`.
`seed_default_profile` only ever INSERTs, and `ProfileRenderer.resolve` lets any
non-NULL stored column win over the module default — so without this revision the
new routing reaches nobody who was already seeded, and existing users keep being
told "visualizations -> use create_dashboard".

Only `tools` changed; identity is untouched by that branch. `tools` is not
auto-composed (no personalization header, unlike identity), so matching is by
whole-text hash: rows whose current text is a known historical default are
rewritten, anything else was edited by the user and is left alone.

The hash set inherits every digest 0rch5c0pe01 knew about, plus the digest of the
text 0rch5c0pe01 itself wrote — which is what most live rows now hold.

Revision ID: chrtr0ut01
Revises: chrtspecs01
Create Date: 2026-09-02
"""
import hashlib
import json
import logging

import sqlalchemy as sa
from alembic import op

revision = "chrtr0ut01"
down_revision = "chrtspecs01"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

# sha256 of every historical `tools` default for agent_type='orchestrator'.
_OLD_TOOLS_HASHES = {
    "c4ef7d0493b2d89e57d9f3922f11701aad3fbd52af050f08e56b7a849102843c",  # 66daa6ed, 908 chars
    "ca2832625c493df9bd771674ebc6f246d49d947e8b77b589a08db05f76884399",  # 8eb5be55, 1165 chars
    "bb9343f17ea1f095a7aaf7c5097c2486de8368188d3ec57d1637b10bf7f35939",  # f859174f, 1497 chars
    "0c7df23adec8406702464de66b07fa3a3d2bbd6092082ca126ad6079ce1f30fa",  # 9be18dfb, 1993 chars
    "4a58590dc43e7dc7a15e9b4dba97823d4f51281dea6cbf82be2fa25a4523c414",  # eb64cb3c, 2198 chars
    "72d7642aff100d3b06b1b8fdfb7bebda252931fa0dc9afb50ec1a8a4831cfe4a",  # written by 0rch5c0pe01, 2320 chars
}

# Frozen snapshot of the current default — a literal, so this revision replays to
# the same result regardless of later edits to profile_defaults.
_NEW_TOOLS = '## Tool Usage Guide\n- Questions about the user\'s dashboards, data connections, or application state → use list_dashboards / list_connections\n- Questions requiring SQL queries against the user\'s databases → use data_agent tools\n- Questions about uploaded documents → use rag_agent tools\n- Requests for a persisted dashboard (saved, multiple widgets, to revisit later) → use create_dashboard\n- A single ad-hoc chart/visualization to answer one question inline in this reply (not saved as a dashboard — "show me", "plot", "chart") → use generate_chat_chart, NOT create_dashboard\n- The question refers to an @mentioned dashboard → use select_dashboard_widget instead of generate_chat_chart\n- Always prefer using a tool over saying you don\'t have access\n\n## File-to-Dashboard Workflow (IMPORTANT)\nWhen a user\'s message contains a file attachment (shown as `[File: ... (file_id: ...)]`) and they ask for a dashboard, chart, analysis, or visualization:\n1. ALWAYS call `create_dataset_from_upload` first with the file_id from the attachment\n2. Then call `create_dashboard` — the new connection will be available automatically\nNEVER ask the user to manually import, register, or set up the data. You MUST handle the ingestion workflow automatically. This covers data setup only — it does not stop you from asking scoping questions about what a dashboard should show.\n\n## Structured User Input\n- Ambiguous requirements or plan confirmation → use ask_user_question\n- Call with 1-4 structured questions (2-4 options each)\n- STOP after calling — wait for the user\'s reply\n- Do NOT use for simple yes/no — just ask in plain text\n\n## Data Agent Response Relay\nWhen relaying data_agent results to the user:\n- Write for a business audience, not a data team. Lead with "so what" — what does this mean for the business?\n- Translate technical findings into plain language (e.g., "Senior citizens cancel at twice the average rate" not "seniorcitizen=1, churn_rate_pct=41.7")\n- Drop raw technical details: no column names, null counts, SQL errors, or query metadata. The user sees agent steps in the UI already.\n- Frame numbers as comparisons, trends, or rankings (e.g., "Month-to-month customers are 3x more likely to leave than annual subscribers")\n- End with 2-3 concrete next steps the business can act on, not technical recommendations about data quality\n- If some queries failed, say what\'s missing in one line — don\'t list error messages or suggest DB fixes\n- When data is central to the answer (rankings, breakdowns, top-N lists), include a concise **markdown table** — limit to key columns, top rows, and round numbers for readability (e.g., 26.5% not 0.26537)'


def _is_old_tools(text) -> bool:
    if not text:
        return False
    return hashlib.sha256(text.encode("utf-8")).hexdigest() in _OLD_TOOLS_HASHES


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, tools, published_snapshot FROM agent_profiles "
            "WHERE agent_type = 'orchestrator'"
        )
    ).mappings().all()

    touched = 0
    for row in rows:
        updates = {}
        if _is_old_tools(row["tools"]):
            updates["tools"] = _NEW_TOOLS

        # published_snapshot feeds the live render path — refresh it the same way
        # or the new routing only appears after the user next re-publishes.
        snapshot = row["published_snapshot"]
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except ValueError:
                snapshot = None
        if isinstance(snapshot, dict) and _is_old_tools(snapshot.get("tools")):
            snapshot["tools"] = _NEW_TOOLS
            updates["published_snapshot"] = json.dumps(snapshot)

        if not updates:
            continue
        touched += 1
        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        conn.execute(
            sa.text(f"UPDATE agent_profiles SET {set_clause} WHERE id = :id"),
            {**updates, "id": row["id"]},
        )

    logger.info(
        "orchestrator chart-routing refresh: %d of %d rows updated", touched, len(rows)
    )


def downgrade() -> None:
    """No-op. The rewrite is text-for-text and the previous revision's text is
    already in _OLD_TOOLS_HASHES — re-running upgrade after a downgrade would
    just rewrite it again, so undoing buys nothing and would strip live routing.
    """
