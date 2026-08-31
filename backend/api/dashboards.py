import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any
from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.auth.dependencies import forbid_viewer
from backend.models.user import User
from backend.models.dashboard import Dashboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


class DashboardCreate(BaseModel):
    title: str
    description: Optional[str] = None
    widgets: List[Any] = []


class DashboardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    widgets: Optional[List[Any]] = None


class DashboardResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    widgets: List[Any]
    data_context: Optional[Any] = None
    created_at: str
    updated_at: str
    schedule_type: Optional[str] = None
    schedule_value: Optional[str] = None
    cron_expression: Optional[str] = None
    schedule_active: bool = False
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    owner_email: Optional[str] = None
    is_shared: bool = False
    # Per-Org rollout gate: frontend loads widget data via the bulk
    # /{id}/refresh endpoint instead of one /widgets/refresh call per widget.
    bulk_widget_loading: bool = False


def _readable_org_ids(db: Session, current_user: User) -> set[str]:
    """Org ids whose dashboards the user may READ: home org + every org the
    user holds a UserOrgRole in (the 'shared with me' surface).

    Falls back to the home org alone when the governance plugin is absent
    (community standalone).
    """
    ids: set[str] = set()
    if current_user.org_id:
        ids.add(str(current_user.org_id))
    home = getattr(current_user, "home_org_id", None)
    # home_org_id may diverge from org_id (active workspace) in a later task; defensive.
    if home:
        ids.add(str(home))
    try:
        from bingo_org_governance.models import UserOrgRole
    except ImportError:
        return ids
    rows = (
        db.query(UserOrgRole.org_id)
        .filter(UserOrgRole.user_id == current_user.id)
        .all()
    )
    ids.update(str(r[0]) for r in rows)
    return ids


def _home_org_id(user) -> Optional[str]:
    """The user's home org id (their own org), independent of active workspace."""
    return getattr(user, "home_org_id", None) or (
        str(user.org_id) if user.org_id else None
    )


def _dashboard_visible_to(query, current_user: User, db: Session):
    """Read scope: dashboards in any org the caller may read (home +
    memberships). Legacy owner-without-org rows whose owner currently lives in a
    readable org stay visible. Falls back to owner-only when the caller has no org.
    """
    from sqlalchemy import or_

    readable = _readable_org_ids(db, current_user)
    if not readable:
        return query.filter(Dashboard.user_id == current_user.id)
    # Avoid a JOIN (which would duplicate rows and force a DISTINCT that Postgres
    # can't apply over the `json` widgets/data_context columns). Resolve owner
    # ids in readable orgs via a subquery instead — single table, no dupes.
    owner_ids = db.query(User.id).filter(User.org_id.in_(readable))
    return query.filter(
        or_(
            Dashboard.org_id.in_(readable),
            Dashboard.user_id.in_(owner_ids),
        )
    )


def _governance_require_mutate_dashboard(current_user: User, dashboard: Dashboard) -> None:
    """Phase 3 inline guard for PUT/DELETE on a dashboard."""
    from backend.governance.contract import require as governance_require
    governance_require(
        user=current_user,
        action="update",
        resource={
            "type": "dashboard",
            "org_id": str(dashboard.org_id) if dashboard.org_id else None,
            "owner_user_id": str(dashboard.user_id) if dashboard.user_id else None,
        },
    )


def _org_name_map(db: Session, org_ids: set) -> dict:
    """Map org_id -> name for the given ids (single query, no N+1)."""
    if not org_ids:
        return {}
    from backend.models.organization import Organization
    rows = db.query(Organization.id, Organization.name).filter(
        Organization.id.in_(org_ids)
    ).all()
    return {str(i): n for i, n in rows}


def _owner_email_map(db: Session, owner_ids: set) -> dict:
    """Map user_id -> email for dashboard owners (single query, no N+1)."""
    if not owner_ids:
        return {}
    rows = db.query(User.id, User.email).filter(User.id.in_(owner_ids)).all()
    return {str(i): e for i, e in rows}


def _bulk_widget_loading_for(current_user: User) -> bool:
    """Per-Org `bulk_widget_loading` rollout flag (False without an org)."""
    if not current_user.org_id:
        return False
    try:
        from backend.config.feature_flags import enabled
        return enabled(str(current_user.org_id), "bulk_widget_loading")
    except Exception:
        logger.warning("bulk_widget_loading flag check failed", exc_info=True)
        return False


# Widget config keys that hold query result data (potentially large).
# List view needs no data at all → strip rows/columns/data.
# Skeleton (dashboard open) needs structure to render the layout instantly but
# not the heavy value arrays → strip rows/data, KEEP columns (tables need column
# defs to render headers; the live refresh fills rows/data right after).
_LITE_CONFIG_KEYS = ("rows", "columns", "data")
_SKELETON_CONFIG_KEYS = ("rows", "data")


def _strip_widgets(widgets, keys) -> list:
    """Return widgets with the given config keys removed from each widget.config.
    Non-dict/legacy shapes pass through untouched.
    """
    out = []
    for w in widgets or []:
        if not isinstance(w, dict):
            out.append(w)
            continue
        inner = w.get("widget")
        if isinstance(inner, dict) and isinstance(inner.get("config"), dict):
            config = {k: v for k, v in inner["config"].items() if k not in keys}
            out.append({**w, "widget": {**inner, "config": config}})
        else:
            out.append(w)
    return out


def _lite_widgets(widgets) -> list:
    """List response: strip all result data (list UI reads only type/position)."""
    return _strip_widgets(widgets, _LITE_CONFIG_KEYS)


def _skeleton_widgets(widgets) -> list:
    """Dashboard-open response: strip heavy value arrays (rows/data) but keep
    columns + structure so the layout paints instantly before the live refresh
    lands. Only strips widgets that HAVE a dataSource (a refresh will refill
    them); static/no-source widgets keep their baked data — nothing would refill
    it otherwise.
    """
    out = []
    for w in widgets or []:
        if not isinstance(w, dict) or not w.get("dataSource"):
            out.append(w)
            continue
        inner = w.get("widget")
        if isinstance(inner, dict) and isinstance(inner.get("config"), dict):
            config = {k: v for k, v in inner["config"].items() if k not in _SKELETON_CONFIG_KEYS}
            out.append({**w, "widget": {**inner, "config": config}})
        else:
            out.append(w)
    return out


_TITLE_SUFFIX_RE = re.compile(r"\s*\(([^()]*)\)\s*$")


def _strip_source_suffix(title: str, widgets) -> str:
    """Drop a trailing "(csv_104)" the dashboard agent echoed into the title.

    The storage table name is internal — users recognise the file they
    uploaded, not the key it is stored under. Only a suffix naming an actual
    source table is removed, so "Q3 Sales (2024)" is left alone.
    """
    match = _TITLE_SUFFIX_RE.search(title or "")
    if not match:
        return title
    sources = {
        s
        for w in widgets or []
        if isinstance(w, dict)
        for s in (w.get("sources") or [])
        if isinstance(s, str)
    }
    if not sources:
        return title
    tokens = [t.strip() for t in match.group(1).split(",")]
    if not all(t in sources for t in tokens):
        return title
    # A title that is nothing but the table name has nothing left to show.
    return title[: match.start()].rstrip() or title


def _dashboard_to_response(
    dashboard: Dashboard,
    *,
    home_org_id: Optional[str] = None,
    org_names: Optional[dict] = None,
    owner_emails: Optional[dict] = None,
    bulk_widget_loading: bool = False,
    lite: bool = False,
    skeleton: bool = False,
) -> DashboardResponse:
    org_id = str(dashboard.org_id) if dashboard.org_id else None
    is_shared = bool(org_id and home_org_id and org_id != str(home_org_id))
    # org_name is shown on every row (own + shared); is_shared still drives the
    # frontend's shared pill styling.
    org_name = (org_names or {}).get(org_id)
    owner_email = (owner_emails or {}).get(
        str(dashboard.user_id)
    ) if dashboard.user_id else None
    return DashboardResponse(
        id=dashboard.id,
        title=_strip_source_suffix(dashboard.title, dashboard.widgets),
        description=dashboard.description,
        widgets=(
            _lite_widgets(dashboard.widgets) if lite
            else _skeleton_widgets(dashboard.widgets) if skeleton
            else (dashboard.widgets or [])
        ),
        data_context=dashboard.data_context,
        created_at=str(dashboard.created_at),
        updated_at=str(dashboard.updated_at),
        schedule_type=dashboard.schedule_type,
        schedule_value=dashboard.schedule_value,
        cron_expression=dashboard.cron_expression,
        schedule_active=dashboard.schedule_active or False,
        next_run_at=str(dashboard.next_run_at) if dashboard.next_run_at else None,
        last_run_at=str(dashboard.last_run_at) if dashboard.last_run_at else None,
        org_id=org_id,
        org_name=org_name,
        owner_email=owner_email,
        is_shared=is_shared,
        bulk_widget_loading=bulk_widget_loading,
    )


@router.get("", response_model=List[DashboardResponse])
def list_dashboards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List dashboards visible to the current user.

    Phase 3 collaborative workspace: every member of the caller's org sees
    every dashboard in the org. Legacy callers without an org_id keep the
    owner-only view.
    """
    dashboards = _dashboard_visible_to(db.query(Dashboard), current_user, db).all()
    home_org_id = _home_org_id(current_user)
    org_ids = {str(d.org_id) for d in dashboards if d.org_id}
    org_names = _org_name_map(db, org_ids)
    owner_emails = _owner_email_map(db, {str(d.user_id) for d in dashboards if d.user_id})
    bulk_widget_loading = _bulk_widget_loading_for(current_user)
    return [
        _dashboard_to_response(
            d,
            home_org_id=home_org_id,
            org_names=org_names,
            owner_emails=owner_emails,
            bulk_widget_loading=bulk_widget_loading,
            lite=True,  # list view never needs widget result data
        )
        for d in dashboards
    ]


@router.get("/{dashboard_id}", response_model=DashboardResponse)
def get_dashboard(
    dashboard_id: int,
    skeleton: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific dashboard.

    `skeleton=true` strips the heavy baked value arrays (rows/data) but keeps
    columns + structure, so the frontend can paint the dashboard layout instantly
    on open and fill widget data via the live refresh — avoids a slow full-baked
    payload blocking the first render.
    """
    dashboard = (
        _dashboard_visible_to(db.query(Dashboard), current_user, db)
        .filter(Dashboard.id == dashboard_id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    home_org_id = _home_org_id(current_user)
    org_names = _org_name_map(db, {str(dashboard.org_id)} if dashboard.org_id else set())
    owner_emails = _owner_email_map(db, {str(dashboard.user_id)} if dashboard.user_id else set())
    return _dashboard_to_response(
        dashboard,
        home_org_id=home_org_id,
        org_names=org_names,
        owner_emails=owner_emails,
        bulk_widget_loading=_bulk_widget_loading_for(current_user),
        skeleton=skeleton,
    )


@router.post("", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
def create_dashboard(
    payload: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _viewer=Depends(forbid_viewer),
):
    """Create a new dashboard."""
    dashboard = Dashboard(
        user_id=current_user.id,
        org_id=current_user.org_id,
        title=payload.title,
        description=payload.description,
        widgets=payload.widgets,
    )
    db.add(dashboard)
    db.commit()
    db.refresh(dashboard)

    # If the Org is cut over to DuckDB serving, the agent emits DuckDB SQL, so
    # mark this dashboard born-DuckDB: it's never re-transpiled and serving may
    # use the DuckDB path immediately (Phase 3 cutover gate).
    if current_user.org_id:
        try:
            from backend.config.feature_flags import enabled
            if enabled(str(current_user.org_id), "duckdb_widget_serving"):
                from backend.migration.dialect_migration import mark_born_duckdb
                mark_born_duckdb(dashboard.id, db)
        except Exception:
            logger.warning("mark_born_duckdb failed for dashboard %s", dashboard.id, exc_info=True)

    home_org_id = _home_org_id(current_user)
    org_names = _org_name_map(db, {str(dashboard.org_id)} if dashboard.org_id else set())
    owner_emails = _owner_email_map(db, {str(dashboard.user_id)} if dashboard.user_id else set())
    return _dashboard_to_response(
        dashboard,
        home_org_id=home_org_id,
        org_names=org_names,
        owner_emails=owner_emails,
        bulk_widget_loading=_bulk_widget_loading_for(current_user),
    )


@router.put("/{dashboard_id}", response_model=DashboardResponse)
def update_dashboard(
    dashboard_id: int,
    payload: DashboardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _viewer=Depends(forbid_viewer),
):
    """Update a dashboard (partial update)."""
    dashboard = (
        db.query(Dashboard)
        .filter(Dashboard.id == dashboard_id, Dashboard.org_id == current_user.org_id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    _governance_require_mutate_dashboard(current_user, dashboard)

    if payload.title is not None:
        dashboard.title = payload.title
    if payload.description is not None:
        dashboard.description = payload.description
    if payload.widgets is not None:
        dashboard.widgets = payload.widgets

    db.commit()
    db.refresh(dashboard)
    home_org_id = _home_org_id(current_user)
    org_names = _org_name_map(db, {str(dashboard.org_id)} if dashboard.org_id else set())
    owner_emails = _owner_email_map(db, {str(dashboard.user_id)} if dashboard.user_id else set())
    return _dashboard_to_response(
        dashboard,
        home_org_id=home_org_id,
        org_names=org_names,
        owner_emails=owner_emails,
        bulk_widget_loading=_bulk_widget_loading_for(current_user),
    )


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _viewer=Depends(forbid_viewer),
):
    """Hard delete a dashboard."""
    dashboard = (
        db.query(Dashboard)
        .filter(Dashboard.id == dashboard_id, Dashboard.org_id == current_user.org_id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    _governance_require_mutate_dashboard(current_user, dashboard)

    # Remove the dialect-migration journal row first — its FK on dashboards.id
    # has no ON DELETE CASCADE, so deleting a migrated/born-DuckDB dashboard
    # would otherwise fail with a ForeignKeyViolation.
    from backend.migration.dialect_migration import DashboardDialectMigration
    db.query(DashboardDialectMigration).filter(
        DashboardDialectMigration.dashboard_id == dashboard_id
    ).delete()

    db.delete(dashboard)
    db.commit()
