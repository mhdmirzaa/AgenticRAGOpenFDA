"""
Tests for continuous corpus growth (PRD v3.0 M3) and the OpenSearch store's RRF
merge (PRD v3.0 M2).

Growth is exercised with a mocked openFDA fetch + a temp SQLite DB so the
watermark/paging cursor persistence is real; OpenSearch fusion is unit-tested
without a live cluster.
"""

import asyncio
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.openfda import (
    DrugLabelRecord, run_fda_growth,
    _GROWTH_SKIP_KEY, _GROWTH_WATERMARK_KEY,
)
from app.retrieval.opensearch_store import _rrf_merge


# ------------------------------------------------------------------- RRF merge
def test_rrf_merge_rewards_agreement():
    """A doc ranked highly by BOTH signals beats one ranked highly by one."""
    bm25 = ["a", "b", "c"]
    knn = ["a", "d", "e"]
    scores = _rrf_merge(bm25, knn)
    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)
    assert ranked[0] == "a"  # appears top of both lists


def test_rrf_merge_unions_ids():
    scores = _rrf_merge(["a", "b"], ["c"])
    assert set(scores) == {"a", "b", "c"}


# --------------------------------------------------------------------- growth
@pytest.fixture()
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="maistorage_growth_")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    from app.config import get_settings
    get_settings.cache_clear()
    from app import db
    db.reset_engine()
    db.init_db()
    yield
    db.reset_engine()
    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
    try:
        os.remove(path)
    except OSError:
        pass


def test_growth_advances_watermark_and_dedupes(temp_db, monkeypatch):
    """Two growth runs page forward; the second run's known label is skipped."""
    from app.ingestion import openfda as of
    from app import db

    rec1 = DrugLabelRecord("L1", "drugone", "", "url1", {"warnings": "text one"})
    rec2 = DrugLabelRecord("L2", "drugtwo", "", "url2", {"warnings": "text two"})

    async def fake_fetch(*, skip, limit, api_key=None):
        # First page returns L1; second page returns L1 (dup) + L2.
        if skip == 0:
            return [rec1], "20240101"
        return [rec1, rec2], "20240202"

    async def fake_ingest(records, **kwargs):
        return {"labels_indexed": len(records), "chunks_indexed": len(records)}

    monkeypatch.setattr(of, "fetch_newest_labels", fake_fetch)
    monkeypatch.setattr(of, "ingest_records", fake_ingest)

    stats1 = asyncio.run(run_fda_growth(batch_size=25))
    assert stats1["labels_indexed"] == 1
    assert db.get_kv(_GROWTH_SKIP_KEY) == "25"
    assert db.get_kv(_GROWTH_WATERMARK_KEY) == "20240101"
    # Record L1 so the next run can dedupe it.
    db.record_labels([rec1])

    stats2 = asyncio.run(run_fda_growth(batch_size=25))
    # Page had L1 (known -> skipped) + L2 (fresh) -> only L2 indexed.
    assert stats2["labels_indexed"] == 1
    assert stats2["skipped"] == 1
    assert db.get_kv(_GROWTH_SKIP_KEY) == "50"
    assert db.get_kv(_GROWTH_WATERMARK_KEY) == "20240202"


def test_growth_survives_empty_page(temp_db, monkeypatch):
    from app.ingestion import openfda as of

    async def empty_fetch(*, skip, limit, api_key=None):
        return [], ""

    async def fake_ingest(records, **kwargs):
        return {"labels_indexed": 0, "chunks_indexed": 0}

    monkeypatch.setattr(of, "fetch_newest_labels", empty_fetch)
    monkeypatch.setattr(of, "ingest_records", fake_ingest)

    stats = asyncio.run(run_fda_growth(batch_size=10))
    assert stats["labels_indexed"] == 0
    assert stats["skip_next"] == 10  # cursor still advances (keeps growing)
