"""
Tests for PostgreSQL persistence (SQLAlchemy).  [production item 2]

Runs against a temp SQLite file (same SQLAlchemy models used with Postgres in
docker), covering:
- DrugLabel dedupe by UNIQUE label_id
- known-label-id set feeding the ingestion dedupe
- session + message persistence with citations JSON + trace_id
- last-N conversation memory ordering
- data survives a simulated restart (engine disposed + reopened on same file)
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.openfda import DrugLabelRecord


def _rec(label_id, name="ibuprofen"):
    return DrugLabelRecord(
        label_id=label_id, drug_name=name, brand_name="Brand",
        source_url=f"http://x/{label_id}", sections={"warnings": "w"},
    )


@pytest.fixture
def db(tmp_path):
    """Fresh SQLite-backed DB module pointed at a temp file."""
    dbfile = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{dbfile}"

    from app.config import get_settings
    get_settings.cache_clear()

    import app.db as db_mod
    db_mod.reset_engine()
    db_mod.init_db()

    yield db_mod

    db_mod.reset_engine()
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)


class TestDrugLabelPersistence:
    def test_record_labels_inserts_new(self, db):
        n = db.record_labels([_rec("a"), _rec("b")])
        assert n == 2
        assert db.get_known_label_ids() == {"a", "b"}

    def test_unique_label_id_dedupes(self, db):
        db.record_labels([_rec("a")])
        # inserting the same label_id again adds nothing (UNIQUE enforced)
        n = db.record_labels([_rec("a"), _rec("c")])
        assert n == 1
        assert db.get_known_label_ids() == {"a", "c"}


class TestChatPersistence:
    def test_session_and_messages_persist(self, db):
        sid = db.create_session()
        assert sid
        db.add_message(sid, "user", "What are ibuprofen warnings?")
        db.add_message(
            sid, "assistant", "Do not exceed dose [1].",
            citations=[{"marker": "[1]", "chunk_id": "ibuprofen#warnings:x"}],
            trace_id="trace-123",
        )
        msgs = db.get_messages(sid)
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[1]["citations"][0]["chunk_id"] == "ibuprofen#warnings:x"
        assert msgs[1]["trace_id"] == "trace-123"

    def test_recent_memory_window_orders_chronologically(self, db):
        sid = db.create_session()
        for i in range(5):
            db.add_message(sid, "user", f"q{i}")
            db.add_message(sid, "assistant", f"a{i}")
        recent = db.get_recent_messages(sid, n=4)
        assert [m["content"] for m in recent] == ["q3", "a3", "q4", "a4"]

    def test_get_messages_unknown_session_is_empty(self, db):
        assert db.get_messages("does-not-exist") == []


class TestSurvivesRestart:
    def test_data_survives_engine_reopen(self, db, tmp_path):
        sid = db.create_session()
        db.add_message(sid, "user", "persist me")
        db.record_labels([_rec("persist-label")])

        # simulate a process restart: dispose the engine, reopen same file
        db.reset_engine()
        db.init_db()

        assert "persist-label" in db.get_known_label_ids()
        msgs = db.get_messages(sid)
        assert len(msgs) == 1 and msgs[0]["content"] == "persist me"
