"""
openFDA drug-label ingestion DAG.  [production item 3]

Apache Airflow is the production orchestrator for the accumulating knowledge
base. This DAG runs on a configurable schedule (default every 15 minutes) and
executes the idempotent pipeline:

    fetch_labels -> extract_sections -> dedupe -> index -> record

Idempotency: dedupe by the stable openFDA label_id (against Postgres), and the
downstream chunk ids are deterministic + Chroma upserts, so re-runs never
double-index. Tasks retry on transient failure and requests are throttled to
respect openFDA rate limits (handled inside the backend fetch helpers).

The backend `app` package must be importable on the Airflow workers' PYTHONPATH
(the docker-compose Airflow image mounts backend/ for this).
"""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# Interval is configurable via env; default */15 (every 15 minutes) for the demo.
FDA_DAG_SCHEDULE = os.environ.get("FDA_DAG_SCHEDULE", "*/15 * * * *")

DEFAULT_ARGS = {
    "owner": "maistorage",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "depends_on_past": False,
}


# --------------------------------------------------------------- task callables
def fetch_labels(**context):
    """Fetch raw openFDA label results for the seed drugs (throttled, keyless)."""
    from app.ingestion.openfda import fetch_drug_labels, record_to_dict

    records = asyncio.run(fetch_drug_labels())
    return [record_to_dict(r) for r in records]


def extract_sections(**context):
    """Pass-through of parsed per-section records (parsing happens in fetch)."""
    ti = context["ti"]
    records = ti.xcom_pull(task_ids="fetch_labels") or []
    # records are already section-structured dicts; nothing else to extract.
    return records


def dedupe(**context):
    """Drop labels whose label_id is already recorded in Postgres."""
    from app.ingestion.openfda import record_from_dict, record_to_dict, dedupe_records

    ti = context["ti"]
    raw = ti.xcom_pull(task_ids="extract_sections") or []
    records = [record_from_dict(d) for d in raw]

    try:
        from app.db import get_known_label_ids
        known = get_known_label_ids()
    except Exception:
        known = set()

    fresh = dedupe_records(records, known_label_ids=known)
    return [record_to_dict(r) for r in fresh]


def index(**context):
    """Chunk + embed + index the fresh labels into Chroma (idempotent upsert)."""
    from app.ingestion.openfda import record_from_dict, ingest_records

    ti = context["ti"]
    raw = ti.xcom_pull(task_ids="dedupe") or []
    records = [record_from_dict(d) for d in raw]
    stats = asyncio.run(ingest_records(records))
    return stats


def record(**context):
    """Record label metadata in Postgres (DB-level dedupe by UNIQUE label_id)."""
    from app.ingestion.openfda import record_from_dict
    from app.db import record_labels, init_db

    ti = context["ti"]
    raw = ti.xcom_pull(task_ids="dedupe") or []
    records = [record_from_dict(d) for d in raw]
    try:
        init_db()
        return {"labels_recorded": record_labels(records)}
    except Exception as e:
        return {"labels_recorded": 0, "error": str(e)}


with DAG(
    dag_id="fda_ingestion",
    description="Fetch openFDA drug labels and index them (idempotent, deduped).",
    schedule_interval=FDA_DAG_SCHEDULE,
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["rag", "openfda", "ingestion"],
) as dag:
    t_fetch = PythonOperator(task_id="fetch_labels", python_callable=fetch_labels)
    t_extract = PythonOperator(task_id="extract_sections", python_callable=extract_sections)
    t_dedupe = PythonOperator(task_id="dedupe", python_callable=dedupe)
    t_index = PythonOperator(task_id="index", python_callable=index)
    t_record = PythonOperator(task_id="record", python_callable=record)

    t_fetch >> t_extract >> t_dedupe >> [t_index, t_record]
