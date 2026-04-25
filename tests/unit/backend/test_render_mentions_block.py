"""Unit tests for backend.agents.orchestrator.prompts.render_mentions_block."""

from backend.agents.orchestrator.prompts import render_mentions_block
from backend.schemas.chat import ResolvedMention


def test_empty_list_returns_empty_string():
    assert render_mentions_block([]) == ""
    assert render_mentions_block(None) == ""


def test_single_dashboard_renders_id_and_display_name():
    block = render_mentions_block([
        ResolvedMention(type="dashboard", id=42, name="q4-revenue", display_name="Q4 Revenue"),
    ])
    assert "## Resolved @-mentions for this turn" in block
    assert "dashboard #42" in block
    assert '"Q4 Revenue"' in block
    assert "## Routing bias" in block


def test_single_connection_renders_db_type_when_present():
    block = render_mentions_block([
        ResolvedMention(
            type="connection", id=7, name="snowflake-prod",
            display_name="snowflake-prod", db_type="snowflake",
        ),
    ])
    assert "connection #7" in block
    assert "(snowflake)" in block


def test_single_notion_page_renders_page_and_parent_connection():
    block = render_mentions_block([
        ResolvedMention(
            type="notion_page", id=3, name="notion-onboarding",
            display_name="Onboarding Plan", page_id="abc-123", connection_id=3,
        ),
    ])
    assert "notion_page" in block
    assert "page_id='abc-123'" in block
    assert "connection #3" in block
    assert '"Onboarding Plan"' in block


def test_mixed_list_renders_all_three_types_and_one_routing_bias_section():
    block = render_mentions_block([
        ResolvedMention(type="dashboard", id=1, name="a", display_name="A"),
        ResolvedMention(type="connection", id=2, name="b", display_name="B", db_type="postgres"),
        ResolvedMention(
            type="notion_page", id=3, name="c", display_name="C",
            page_id="pp", connection_id=3,
        ),
    ])
    assert block.count("## Resolved @-mentions") == 1
    assert block.count("## Routing bias") == 1
    assert "dashboard #1" in block
    assert "connection #2" in block
    assert "notion_page" in block
    # Routing-bias bullets — one per type
    assert "@dashboard mentioned" in block
    assert "@connection mentioned" in block
    assert "@notion_page mentioned" in block
    assert "Mentions never go through `manage`." in block
