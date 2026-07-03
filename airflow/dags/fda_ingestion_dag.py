"""
openFDA drug-label ingestion DAG.  [production item 3]

Apache Airflow is the production orchestrator for the accumulating knowledge
base. This DAG runs on a configurable schedule (default every 15 minutes) and
executes the idempotent pipeline:

    fetch_labels -> extract_sections -> dedupe -> index -> record

Architecture note (important): Chroma (embedded SQLite) and the app Postgres are
OWNED by the backend service. Airflow must NOT write them directly — two
processes writing the same Chroma SQLite file race and fail ("readonly
database"), and the Airflow image pins SQLAlchemy 1.4 which is incompatible with
the app's psycopg3 layer. So the DAG does the *read-only* work in-worker
(fetch from openFDA, dedupe against the known-id list) and DELEGATES the writes
(chunk+embed+index into Chroma, record in Postgres) to the backend's
`POST /ingest/fda` endpoint over HTTP. The backend is the single writer.

Idempotency: the backend dedupes again by the stable openFDA label_id and
upserts deterministic chunk ids, so re-runs never double-index. Tasks retry on
transient failure; openFDA fetches are throttled inside the fetch helpers.

The backend `app` package is importable on the workers' PYTHONPATH (compose
mounts backend/) for the read-only fetch/dedupe steps.
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
# The backend service that owns Chroma + Postgres (single writer).
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

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
    """Drop labels already known, and return the fresh drugs' generic names.

    Read-only: known ids come from the backend's /health-adjacent state via the
    app package if reachable, else an empty set (the backend re-dedupes anyway).
    Returns the distinct generic_names to (re)ingest so the write step can pass
    them to the backend endpoint.
    """
    from app.ingestion.openfda import record_from_dict, dedupe_records

    ti = context["ti"]
    raw = ti.xcom_pull(task_ids="extract_sections") or []
    records = [record_from_dict(d) for d in raw]

    try:
        from app.db import get_known_label_ids
        known = get_known_label_ids()
    except Exception:
        known = set()

    fresh = dedupe_records(records, known_label_ids=known)
    # Distinct generic drug names, preserving order.
    names: list[str] = []
    for r in fresh:
        name = (getattr(r, "drug_name", "") or "").strip()
        if name and name.lower() not in {n.lower() for n in names}:
            names.append(name)
    return names


def index_and_record(**context):
    """Delegate the WRITES to the backend (single owner of Chroma + Postgres).

    POST /ingest/fda triggers the backend to fetch -> dedupe -> chunk+embed+index
    -> record in Postgres, atomically inside the writer process. Idempotent.
    """
    import httpx

    ti = context["ti"]
    names = ti.xcom_pull(task_ids="dedupe") or []
    if not names:
        return {"status": "noop", "reason": "no fresh labels", "indexed": 0}

    payload = {"drugs": names, "limit": 1}
    url = f"{BACKEND_URL}/ingest/fda"
    with httpx.Client(timeout=300.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


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
    t_index_record = PythonOperator(task_id="index_and_record", python_callable=index_and_record)

    t_fetch >> t_extract >> t_dedupe >> t_index_record
