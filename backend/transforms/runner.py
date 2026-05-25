"""dbt runner — orchestrates a per-scope dbt project run (Phase 4)."""
from __future__ import annotations

import gzip
import json
import logging
import subprocess
import uuid as _uuid
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

DBT_RUN_LOCK_TTL = 1800


def run_dbt(
    scope,
    model_ids: list[str] | None = None,
    triggered_by: Literal["cron", "manual", "api"] = "manual",
) -> str:
    """Run dbt for *scope*; return the new dbt_run_id."""
    import redis as syncredis

    from backend.config import settings
    from backend.database.session import SessionLocal
    from backend.models.transforms import DbtModel, DbtRun
    from backend.auth.system_context import system_context
    from backend.transforms.project_synth import synthesize_project

    redis_client = syncredis.from_url(settings.redis_url)
    lock_key = f"dbt:run:{scope.kind}:{scope.id}"
    lock = redis_client.lock(lock_key, timeout=DBT_RUN_LOCK_TTL)

    if not lock.acquire(blocking=False):
        logger.info("dbt run for scope %s already running (lock held), skipping", scope.as_path())
        return ""

    db = SessionLocal()
    run_id = str(_uuid.uuid4())

    try:
        # Resolve model names if model_ids provided
        select_models: list[str] | None = None
        if model_ids:
            models = (
                db.query(DbtModel)
                .filter(DbtModel.id.in_(model_ids))
                .all()
            )
            select_models = [m.name for m in models]

        started_at = datetime.now(timezone.utc)
        run = DbtRun(
            id=run_id,
            owner_scope_kind=scope.kind,
            owner_scope_id=scope.id,
            started_at=started_at,
            status="running",
            triggered_by=triggered_by,
        )
        db.add(run)
        db.commit()

        error_message = None
        models_run: list[dict] = []
        manifest_blob: bytes | None = None
        status = "failed"

        try:
            with system_context(reason="dbt.run", scope=scope):
                project_dir = synthesize_project(scope, db)

                cmd = ["dbt", "run", "--project-dir", project_dir, "--profiles-dir", project_dir]
                if select_models:
                    cmd += ["--select"] + select_models

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=DBT_RUN_LOCK_TTL,
                )

                # Parse run_results.json
                run_results_path = f"{project_dir}/target/run_results.json"
                try:
                    with open(run_results_path) as f:
                        run_results = json.load(f)
                    for node in run_results.get("results", []):
                        node_status = node.get("status", "error")
                        model_name = node.get("unique_id", "").split(".")[-1]
                        models_run.append({
                            "name": model_name,
                            "status": node_status,
                            "rows_affected": node.get("adapter_response", {}).get("rows_affected"),
                        })
                except (FileNotFoundError, json.JSONDecodeError):
                    logger.warning("run_dbt: could not read run_results.json for run %s", run_id)

                # Determine overall status
                if models_run:
                    all_ok = all(m["status"] == "success" for m in models_run)
                    any_ok = any(m["status"] == "success" for m in models_run)
                    status = "success" if all_ok else ("partial_success" if any_ok else "failed")
                elif result.returncode == 0:
                    status = "success"
                else:
                    status = "failed"
                    error_message = (result.stderr or result.stdout or "dbt run failed")[:2000]

                # Read and compress manifest.json
                manifest_path = f"{project_dir}/target/manifest.json"
                try:
                    with open(manifest_path, "rb") as f:
                        manifest_blob = gzip.compress(f.read())
                except FileNotFoundError:
                    logger.warning("run_dbt: manifest.json not found for run %s", run_id)

        except subprocess.TimeoutExpired:
            status = "failed"
            error_message = "dbt run timed out after 1800s"
        except Exception as exc:
            status = "failed"
            error_message = str(exc)[:2000]
            logger.exception("run_dbt: unexpected error for scope %s run %s", scope.as_path(), run_id)

        finished_at = datetime.now(timezone.utc)
        run.status = status
        run.finished_at = finished_at
        run.models_run = models_run or None
        run.manifest_blob = manifest_blob
        run.error_message = error_message
        db.commit()

        # Publish lineage:invalidate
        try:
            redis_client.publish("lineage:invalidate", json.dumps({
                "run_id": run_id,
                "scope_kind": scope.kind,
                "scope_id": scope.id,
            }))
        except Exception:
            logger.warning("run_dbt: failed to publish lineage:invalidate for run %s", run_id)

        # Publish dbt.run.failed notification
        if status == "failed":
            try:
                from backend.notifications import publish
                publish({
                    "event_type": "dbt.run.failed",
                    "scope": {"kind": scope.kind, "id": scope.id},
                    "resource_type": "dbt_model",
                    "resource_id": run_id,
                    "name": f"dbt run for {scope.as_path()}",
                    "run_id": run_id,
                    "error_message": error_message,
                })
            except Exception:
                logger.warning("run_dbt: failed to publish dbt.run.failed for run %s", run_id)

        # Land each materialized model in the DataPlane Parquet lake (GAP-3),
        # then chain profiling. Materialize first so the model is present as
        # Parquet before profile_dbt_model reads its schema. Non-fatal per model.
        if status in ("success", "partial_success") and models_run:
            ok_models = [m["name"] for m in models_run if m["status"] == "success"]
            for model_name in ok_models:
                try:
                    from backend.transforms.materialize import materialize_dbt_model_to_dataplane
                    if materialize_dbt_model_to_dataplane(scope, model_name, db=db):
                        # GAP-2f: warm dashboards backed by the model's table.
                        from backend.services.dashboard_cache import enqueue_dashboard_warm_for_table
                        enqueue_dashboard_warm_for_table(scope, model_name)
                except Exception:
                    logger.warning(
                        "run_dbt: failed to materialize %s to DataPlane for run %s",
                        model_name, run_id, exc_info=True,
                    )
                try:
                    from backend.tasks.profiling_tasks import profile_dbt_model
                    profile_dbt_model.delay(run_id, model_name, scope.kind, scope.id)
                except Exception:
                    logger.warning(
                        "run_dbt: failed to chain profile_dbt_model for %s run %s",
                        model_name,
                        run_id,
                    )

        return run_id

    except Exception as exc:
        logger.exception("run_dbt outer error for scope %s", scope.as_path())
        try:
            run_obj = db.query(DbtRun).filter(DbtRun.id == run_id).first()
            if run_obj:
                run_obj.status = "failed"
                run_obj.error_message = str(exc)[:2000]
                run_obj.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
        return run_id or ""

    finally:
        db.close()
        try:
            lock.release()
        except Exception:
            pass
        try:
            redis_client.close()
        except Exception:
            pass
