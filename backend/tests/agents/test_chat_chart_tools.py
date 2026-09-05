"""Guards for the chat-chart tools.

Three regressions this covers:

  * `select_dashboard_widget` was owner-only while the mention picker is fed by
    the org-wide `GET /dashboards` — an org member could mention a dashboard the
    tool then called "not accessible".
  * `_best_title_match` fell back to `widgets[0]` when nothing matched, so an
    unrelated-but-valid chart answered the question and the result depended on
    widget order.
  * `generate_chat_chart` executed SQL shapes `create_dashboard` rejects
    (unaggregated category charts, unbounded scatter/bubble).

DB fixture mirrors test_refresh_visibility.py (real SQLite, so the or_/subquery
read-scope predicate is exercised rather than mocked).
"""
from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import create_engine, JSON, LargeBinary
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

from backend.agents.context import AgentContext
from backend.agents.orchestrator.chat_chart_tools import (
    _best_title_match,
    build_chat_chart_tools,
)
from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.organization import Organization
from backend.models.user import User


def _run(coro):
    return asyncio.run(coro)


def _widget(wid: str, title: str, wtype: str = "chart") -> dict:
    return {"id": wid, "widget": {"type": wtype, "config": {"title": title}}}


# ── _best_title_match ────────────────────────────────────────────────────────

_SALES = _widget("w-sales", "Sales by Region")
_REVENUE = _widget("w-revenue", "Monthly Revenue")


def test_no_token_overlap_returns_none():
    """The review's own example: 'earn' != 'revenue', 'month' != 'monthly', so
    every score is 0 — previously this handed back whichever widget was first."""
    assert _best_title_match([_SALES, _REVENUE], "How much did we earn each month?") is None


def test_no_match_is_independent_of_widget_order():
    q = "How much did we earn each month?"
    assert _best_title_match([_SALES, _REVENUE], q) is _best_title_match([_REVENUE, _SALES], q)


def test_real_overlap_still_matches_regardless_of_order():
    q = "what does revenue look like"
    assert _best_title_match([_SALES, _REVENUE], q)["id"] == "w-revenue"
    assert _best_title_match([_REVENUE, _SALES], q)["id"] == "w-revenue"


def test_short_tokens_do_not_count_as_a_match():
    """Tokens of 3 chars or fewer are dropped, so 'by' must not match 'Sales by
    Region' — otherwise stopwords alone pick a chart."""
    assert _best_title_match([_SALES], "show me by") is None


# ── select_dashboard_widget: read scope ──────────────────────────────────────

@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
                col.server_default = None
            elif isinstance(col.type, BYTEA):
                col.type = LargeBinary()
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def seeded(db):
    db.add_all([
        Organization(id="org-1", name="Org 1", feature_flags={}),
        Organization(id="org-2", name="Org 2", feature_flags={}),
        User(id="u-owner", email="owner@x.test", org_id="org-1"),
        User(id="u-member", email="member@x.test", org_id="org-1"),
        User(id="u-outsider", email="outsider@x.test", org_id="org-2"),
        Dashboard(
            user_id="u-owner", org_id="org-1", title="Org dash",
            widgets=[_widget("w-revenue", "Monthly Revenue")],
        ),
    ])
    db.commit()
    return db.query(Dashboard).first()


def _select(db, user_id: str, dashboard_id: int, question: str = "monthly revenue"):
    context = AgentContext(user_id=user_id, available_connections=[1])
    tools = {t.name: t for t in build_chat_chart_tools(context, lambda: db)}
    return json.loads(
        tools["select_dashboard_widget"].invoke(
            {"dashboard_id": dashboard_id, "question": question}
        )
    )


def test_owner_can_select(db, seeded):
    out = _select(db, "u-owner", seeded.id)
    assert out["success"] is True and out["widget_id"] == "w-revenue"


def test_org_member_can_select_a_dashboard_they_did_not_create(db, seeded):
    """The bug: mentionable via GET /dashboards, but 'not accessible' here."""
    out = _select(db, "u-member", seeded.id)
    assert out["success"] is True and out["widget_id"] == "w-revenue"


def test_other_org_user_cannot_select(db, seeded):
    out = _select(db, "u-outsider", seeded.id)
    assert out["success"] is False and "not found" in out["message"]


def test_unmatched_question_returns_no_match_not_a_widget(db, seeded):
    out = _select(db, "u-owner", seeded.id, question="How much did we earn each month?")
    assert out["success"] is False
    assert "no widget" in out["message"]


# ── generate_chat_chart: shares create_dashboard's widget guards ─────────────

def _generate(db, widget: dict, monkeypatch):
    """Invoke the tool with SQL execution stubbed — the guards must reject
    before execution, so a call through to _execute_widget_sql is a failure."""
    executed = []

    async def _never(*args, **kwargs):
        executed.append(args)
        return None

    monkeypatch.setattr("backend.agents.dashboard_tools._execute_widget_sql", _never)
    # No Redis in a unit run — the chart_ref store is exercised end-to-end elsewhere.
    monkeypatch.setattr(
        "backend.agents.orchestrator.chat_chart_tools.store_query_result",
        lambda *a, **k: None,
    )
    context = AgentContext(user_id="u-owner", available_connections=[1])
    tools = {t.name: t for t in build_chat_chart_tools(context, lambda: db)}
    out = json.loads(_run(tools["generate_chat_chart"].ainvoke({"widget": widget})))
    return out, executed


def _chart(chart_type: str, sql: str, **extra) -> dict:
    return {
        "type": "chart", "chartType": chart_type, "connectionId": 1, "sql": sql,
        "title": f"{chart_type} chart", **extra,
    }


def test_unaggregated_category_chart_is_rejected_before_execution(db, monkeypatch):
    out, executed = _generate(db, _chart(
        "bar", "SELECT region, sales FROM t",
        labelColumn="region", datasetColumns=[{"column": "sales", "label": "Sales"}],
    ), monkeypatch)
    assert out["success"] is False
    assert any(v["code"] == "chart_not_aggregated" for v in out["violations"]), out
    assert executed == []


def test_unbounded_scatter_is_rejected(db, monkeypatch):
    out, _ = _generate(db, _chart(
        "scatter", "SELECT price, nights FROM listings",
        xMetricColumn="price", yMetricColumn="nights",
    ), monkeypatch)
    assert out["success"] is False
    assert any(v["code"] == "scatter_not_bounded" for v in out["violations"]), out


def test_bounded_raw_scatter_passes_the_guards(db, monkeypatch):
    out, executed = _generate(db, _chart(
        "scatter", "SELECT price, nights FROM listings LIMIT 1000",
        xMetricColumn="price", yMetricColumn="nights",
    ), monkeypatch)
    assert "violations" not in out, out
    assert executed, "guards passed, so the SQL must have been executed"


def test_aggregated_category_chart_passes_the_guards(db, monkeypatch):
    out, executed = _generate(db, _chart(
        "bar", "SELECT region, SUM(amount) AS revenue FROM orders GROUP BY region",
        labelColumn="region", datasetColumns=[{"column": "revenue", "label": "Revenue"}],
    ), monkeypatch)
    assert "violations" not in out, out
    assert executed, "guards passed, so the SQL must have been executed"


def test_chat_chart_execution_never_samples_rows_for_the_llm(db, monkeypatch):
    """The privacy claim: no row data reaches the LLM, SQL-repair path included."""
    seen = {}

    async def _capture(widget, factory, **kwargs):
        seen.update(kwargs)
        return None

    monkeypatch.setattr("backend.agents.dashboard_tools._execute_widget_sql", _capture)
    monkeypatch.setattr(
        "backend.agents.orchestrator.chat_chart_tools.store_query_result",
        lambda *a, **k: None,
    )
    context = AgentContext(user_id="u-owner", available_connections=[1])
    tools = {t.name: t for t in build_chat_chart_tools(context, lambda: db)}
    _run(tools["generate_chat_chart"].ainvoke({"widget": _chart(
        "bar", "SELECT region, SUM(amount) AS revenue FROM orders GROUP BY region",
        labelColumn="region", datasetColumns=[{"column": "revenue", "label": "Revenue"}],
    )}))
    assert seen.get("allow_row_sampling") is False


# ── the breakdown ("stack by") contract the docstring promises ───────────────

def test_breakdown_column_survives_hydration_and_pivots_into_one_series_each():
    """The reported bug: "bar chart with product category as the breakdown
    dimension" rendered ONE flat series. The SQL was right and the pivot works —
    the model just never emitted breakdownColumn, because the tool docstring
    never mentioned it. Lock the round-trip the docstring now advertises."""
    from backend.agents.dashboard_agent.widget_specs.widgets import build_widgets
    from backend.connectors.base import QueryResult
    from backend.services.widget_transform import transform_widget_data

    lean = {
        "type": "chart", "chartType": "bar", "connectionId": 1,
        "sql": "SELECT quarter, category, revenue FROM sales",
        "labelColumn": "quarter", "breakdownColumn": "category",
        "datasetColumns": [{"column": "revenue", "label": "Revenue", "aggregation": "sum"}],
        "options": {"stacked": "standard"},
    }
    w = build_widgets([lean])[0]
    assert w["dataSource"]["mapping"]["breakdownColumn"] == "category"
    assert w["widget"]["config"]["options"]["stacked"] == "standard"

    rows = [["Q1", "Phone", 10], ["Q1", "TV", 5], ["Q2", "Phone", 8], ["Q2", "TV", 7]]
    out = transform_widget_data(
        QueryResult(columns=["quarter", "category", "revenue"], rows=rows,
                    row_count=len(rows), execution_time_ms=1.0),
        w["dataSource"]["mapping"],
    )["data"]
    assert out["labels"] == ["Q1", "Q2"]
    assert {d["label"]: d["data"] for d in out["datasets"]} == {"Phone": [10, 8], "TV": [5, 7]}


def test_the_docstring_documents_every_chart_mapping_key():
    """generate_chat_chart's docstring is the ONLY spec the orchestrator sees for
    this tool — it has no get_widget_spec tool and never reads the dashboard
    agent's guidance. A mapping key the builder supports but the docstring omits
    is invisible to the model, which then improvises (sliceLabel for a breakdown,
    a pie-only option). That has now shipped three times; this catches the next."""
    from backend.agents.dashboard_agent.widget_specs.widgets.chart import ChartWidget

    context = AgentContext(user_id="u", available_connections=[1])
    doc = {t.name: t for t in build_chat_chart_tools(context, lambda: None)}
    doc = doc["generate_chat_chart"].description

    # Keys deliberately left out: niche per-bar decoration on timeline charts,
    # already covered by the timeline paragraph's "optional" note.
    undocumented = {"barLabelColumn", "tooltipColumn"}
    missing = [k for k in ChartWidget._MAPPING_KEYS if k not in doc and k not in undocumented]
    assert not missing, f"undocumented chart mapping keys: {missing}"


# ── the tool result grounds the reply ────────────────────────────────────────

def _generate_with_rendered_data(db, widget, monkeypatch, datasets):
    async def _render(w, *a, **k):
        w["widget"]["config"]["data"] = {"labels": ["Q1"], "datasets": datasets}
        return None

    monkeypatch.setattr("backend.agents.dashboard_tools._execute_widget_sql", _render)
    monkeypatch.setattr(
        "backend.agents.orchestrator.chat_chart_tools.store_query_result",
        lambda *a, **k: None,
    )
    context = AgentContext(user_id="u-owner", available_connections=[1])
    tools = {t.name: t for t in build_chat_chart_tools(context, lambda: db)}
    return json.loads(_run(tools["generate_chat_chart"].ainvoke({"widget": widget})))


def test_result_reports_the_series_count_and_stacking(db, monkeypatch):
    """Without these the model has nothing to check its prose against, and it
    described a one-series chart as "stacked by product category"."""
    widget = _chart(
        "bar", "SELECT quarter, category, SUM(revenue) AS revenue FROM sales GROUP BY 1, 2",
        labelColumn="quarter", breakdownColumn="category",
        datasetColumns=[{"column": "revenue", "label": "Revenue", "aggregation": "sum"}],
        options={"stacked": "standard"},
    )
    out = _generate_with_rendered_data(db, widget, monkeypatch, [
        {"label": "Phone", "data": [10]}, {"label": "TV", "data": [5]},
    ])
    assert out["success"] is True
    assert out["series_count"] == 2
    assert out["stacked"] is True


def test_a_kpi_reports_no_series_count(db, monkeypatch):
    """Only charts have series — a kpi reporting series_count=0 would read as a
    failed render to the model."""
    out = _generate_with_rendered_data(db, {
        "type": "kpi", "label": "Total", "valueColumn": "rev", "aggregation": "sum",
        "connectionId": 1, "sql": "SELECT SUM(rev) AS rev FROM t",
    }, monkeypatch, [])
    assert out["success"] is True
    assert "series_count" not in out and "stacked" not in out


def test_a_single_series_chart_reports_itself_as_not_stacked(db, monkeypatch):
    """stacked=true on one series stacks nothing — the result must not claim it
    does, whatever the options say."""
    widget = _chart(
        "bar", "SELECT quarter, SUM(revenue) AS revenue FROM sales GROUP BY 1",
        labelColumn="quarter",
        datasetColumns=[{"column": "revenue", "label": "Revenue", "aggregation": "sum"}],
    )
    out = _generate_with_rendered_data(db, widget, monkeypatch, [{"label": "Revenue", "data": [10]}])
    assert out["series_count"] == 1
    assert out["stacked"] is False

