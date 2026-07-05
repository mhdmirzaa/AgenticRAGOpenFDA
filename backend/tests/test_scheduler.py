"""
Tests for orchestration.  [production item 3]

The scheduled ingestion job (fetch -> dedupe -> index -> record) is the same
idempotent pipeline whether driven by Airflow (production) or the in-process
APScheduler fallback (runnable now). These tests cover the shared job wiring
and the Airflow DAG's validity.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.openfda import DrugLabelRecord, record_to_dict, record_from_dict


class TestRecordSerialization:
    def test_roundtrip(self):
        rec = DrugLabelRecord(
            label_id="x1", drug_name="ibuprofen", brand_name="Advil",
            source_url="http://x", sections={"warnings": "do not exceed"},
        )
        again = record_from_dict(record_to_dict(rec))
        assert again == rec


class TestScheduledJob:
    def test_job_runs_pipeline_with_known_ids(self, monkeypatch):
        import app.scheduler as sched
        import app.ingestion.openfda as openfda
        import app.db as db

        seen = {}

        async def fake_ingest(*args, **kwargs):
            seen["known"] = kwargs.get("known_label_ids")
            return {"labels_indexed": 1, "chunks_indexed": 3}

        monkeypatch.setattr(openfda, "run_fda_ingestion", fake_ingest)
        monkeypatch.setattr(db, "get_known_label_ids", lambda: {"already"})

        stats = sched.run_ingestion_job()
        assert stats["labels_indexed"] == 1
        assert seen["known"] == {"already"}

    def test_job_survives_db_failure(self, monkeypatch):
        import app.scheduler as sched
        import app.ingestion.openfda as openfda
        import app.db as db

        async def fake_ingest(*args, **kwargs):
            return {"labels_indexed": 0}

        def boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(openfda, "run_fda_ingestion", fake_ingest)
        monkeypatch.setattr(db, "get_known_label_ids", boom)

        # must not raise even if the DB is unreachable
        assert sched.run_ingestion_job()["labels_indexed"] == 0


class TestSchedulerLifecycle:
    def test_disabled_returns_none(self):
        import app.scheduler as sched
        s = sched.start_scheduler(enabled=False)
        assert s is None

    def test_enabled_registers_interval_jobs(self):
        import app.scheduler as sched
        s = sched.start_scheduler(enabled=True, minutes=15, run_now=False)
        try:
            assert s is not None
            jobs = s.get_jobs()
            # Two jobs now: seed ingestion + continuous growth (course parity).
            job_ids = {j.id for j in jobs}
            assert job_ids == {"fda_ingestion", "fda_growth"}
            # interval trigger fires every 15 minutes
            assert all("900" in str(j.trigger) or "15:00" in str(j.trigger)
                       for j in jobs)
        finally:
            sched.shutdown_scheduler()


class TestAirflowDag:
    def _dag_source(self):
        here = os.path.dirname(__file__)
        dag_path = os.path.normpath(
            os.path.join(here, "..", "..", "airflow", "dags", "fda_ingestion_dag.py")
        )
        assert os.path.exists(dag_path), f"missing DAG file: {dag_path}"
        with open(dag_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_dag_file_is_valid_python(self):
        compile(self._dag_source(), "fda_ingestion_dag.py", "exec")

    def test_dag_declares_pipeline_tasks(self):
        src = self._dag_source()
        for task_id in ("fetch_labels", "extract_sections", "dedupe", "index", "record"):
            assert task_id in src, f"DAG missing task: {task_id}"

    def test_dag_schedule_is_configurable_and_retries(self):
        src = self._dag_source()
        assert "FDA_DAG_SCHEDULE" in src  # configurable interval via env
        assert "retries" in src           # retries on failure
