"""
In-process scheduled ingestion (APScheduler).  [production item 3 - fallback]

Apache Airflow is the INTENDED production orchestrator (see
airflow/dags/fda_ingestion_dag.py). This APScheduler-based scheduler is the
runnable fallback endorsed by the build plan: it executes the SAME idempotent
job (fetch -> dedupe -> chunk+embed+index -> record in Postgres) on a
configurable interval, entirely inside the FastAPI process.

Disabled by default (ENABLE_SCHEDULER=1 to turn on) so tests/CI aren't affected.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

_scheduler = None


def run_ingestion_job() -> dict:
    """The scheduled job: run the full openFDA ingestion once (idempotent).

    Dedupe uses the label ids already recorded in Postgres; a DB failure is
    non-fatal (falls back to an empty known set, and chunk-id upsert still
    prevents duplicates).
    """
    from app.ingestion.openfda import run_fda_ingestion
    from app import db

    try:
        known = db.get_known_label_ids()
    except Exception as e:
        logger.warning("scheduler: known-label lookup failed: %s", e)
        known = set()

    try:
        stats = asyncio.run(run_fda_ingestion(known_label_ids=known))
        logger.info("scheduler: ingestion complete %s", stats)
        return stats
    except Exception as e:
        logger.error("scheduler: ingestion job failed: %s", e)
        return {"error": str(e)}


def start_scheduler(
    *,
    enabled: bool | None = None,
    minutes: int | None = None,
    run_now: bool = False,
):
    """Start the background scheduler if enabled. Returns the scheduler or None."""
    global _scheduler
    settings = get_settings()
    if enabled is None:
        enabled = settings.enable_scheduler
    if not enabled:
        logger.info("scheduler disabled (set ENABLE_SCHEDULER=1 to enable)")
        return None
    if _scheduler is not None:
        return _scheduler

    from apscheduler.schedulers.background import BackgroundScheduler

    minutes = minutes or settings.schedule_minutes
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        run_ingestion_job,
        trigger="interval",
        minutes=minutes,
        id="fda_ingestion",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("scheduler started: openFDA ingestion every %s min", minutes)
    if run_now:
        run_ingestion_job()
    return _scheduler


def shutdown_scheduler() -> None:
    """Stop the scheduler (idempotent)."""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
