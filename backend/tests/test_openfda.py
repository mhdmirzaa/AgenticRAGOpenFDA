"""
Tests for openFDA drug-label ingestion.  [production item 1]

Covers, offline (no network unless respx-mocked):
- parsing a raw openFDA label result into a clean section record
- dedupe by stable label_id (within a batch and against already-known ids)
- conversion into the existing Document -> chunk -> index pipeline, with the
  drug/label metadata (label_id, source_url) propagated to each chunk
- fetch request shape (respx-mocked) + graceful empty on openFDA 404
- integration: records ingest, are retrievable, and re-running does NOT duplicate
"""

import asyncio
import hashlib
import os
import sys
import tempfile

import pytest
import respx
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion import openfda
from app.ingestion.openfda import (
    DrugLabelRecord,
    parse_label,
    dedupe_records,
    record_to_document,
    fetch_label,
    ingest_records,
    OPENFDA_ENDPOINT,
)
from app.ingestion.chunker import chunk_documents


# ---- a realistic (trimmed) openFDA /drug/label.json result -------------------
SAMPLE_RESULT = {
    "set_id": "abc-123-set",
    "id": "row-id-999",
    "indications_and_usage": [
        "IBUPROFEN is indicated for the temporary relief of minor aches and pains."
    ],
    "warnings": ["Do not use if you have ever had an allergic reaction to any pain reliever."],
    "dosage_and_administration": ["Adults: take 1 tablet every 4 to 6 hours."],
    "adverse_reactions": ["The most common adverse reactions are nausea and dyspepsia."],
    # a non-prose / empty field that must be ignored
    "spl_product_data_elements": ["IBUPROFEN 200 mg"],
    "openfda": {
        "generic_name": ["IBUPROFEN"],
        "brand_name": ["Advil"],
    },
}

NO_PROSE_RESULT = {
    "set_id": "empty-set",
    "openfda": {"generic_name": ["NOTHING"], "brand_name": ["Nihil"]},
    "spl_product_data_elements": ["just codes"],
}


class FakeEmbedder:
    """Deterministic, dependency-free embedder (hash -> fixed-dim vector)."""

    async def embed(self, text):
        return self._vec(text)

    async def embed_batch(self, texts):
        return [self._vec(t) for t in texts]

    def _vec(self, text):
        h = hashlib.md5(text.encode("utf-8")).digest()
        return [b / 255.0 for b in h]  # 16-dim, stable

    async def complete(self, prompt):  # pragma: no cover - unused here
        return "ok"

    async def generate_stream(self, prompt):  # pragma: no cover - unused here
        yield "ok"


# ---------------------------------------------------------------- parse_label
class TestParseLabel:
    def test_extracts_prose_sections(self):
        rec = parse_label(SAMPLE_RESULT)
        assert rec is not None
        assert set(rec.sections) == {
            "indications_and_usage",
            "warnings",
            "dosage_and_administration",
            "adverse_reactions",
        }
        assert "temporary relief" in rec.sections["indications_and_usage"]

    def test_uses_names_from_openfda(self):
        rec = parse_label(SAMPLE_RESULT)
        assert rec.drug_name.lower() == "ibuprofen"
        assert rec.brand_name.lower() == "advil"

    def test_label_id_and_source_url(self):
        rec = parse_label(SAMPLE_RESULT)
        assert rec.label_id == "abc-123-set"
        assert rec.label_id in rec.source_url
        assert rec.source_url.startswith("http")

    def test_returns_none_when_no_prose(self):
        assert parse_label(NO_PROSE_RESULT) is None


# ------------------------------------------------------------------- dedupe
class TestDedupe:
    def _rec(self, label_id):
        return DrugLabelRecord(
            label_id=label_id, drug_name="d", brand_name="b",
            source_url="http://x", sections={"warnings": "w"},
        )

    def test_removes_duplicate_label_ids(self):
        out = dedupe_records([self._rec("a"), self._rec("a"), self._rec("b")])
        assert [r.label_id for r in out] == ["a", "b"]

    def test_respects_known_ids(self):
        out = dedupe_records([self._rec("a"), self._rec("b")], known_label_ids={"a"})
        assert [r.label_id for r in out] == ["b"]


# --------------------------------------------------- record -> document/chunks
class TestRecordToDocument:
    def test_document_has_section_headings_and_metadata(self):
        rec = parse_label(SAMPLE_RESULT)
        doc = record_to_document(rec)
        assert doc.source.lower() == "ibuprofen"
        assert "## " in doc.content
        assert doc.metadata["label_id"] == "abc-123-set"
        assert doc.metadata["source_url"] == rec.source_url
        assert doc.metadata["brand_name"].lower() == "advil"

    def test_chunks_carry_label_metadata_one_per_section(self):
        rec = parse_label(SAMPLE_RESULT)
        chunks = chunk_documents([record_to_document(rec)])
        assert len(chunks) == 4  # one chunk per prose section
        for c in chunks:
            assert c.metadata.get("label_id") == "abc-123-set"
            assert c.metadata.get("source_url", "").startswith("http")
        sections = {c.section for c in chunks}
        assert "warnings" in sections
        assert "indications-and-usage" in sections


# --------------------------------------------------------------- fetch_label
class TestFetchLabel:
    @respx.mock
    def test_builds_request_and_parses(self):
        route = respx.get(OPENFDA_ENDPOINT).mock(
            return_value=httpx.Response(200, json={"results": [SAMPLE_RESULT]})
        )
        results = asyncio.run(fetch_label("ibuprofen", limit=1))
        assert route.called
        sent = route.calls.last.request
        assert 'openfda.generic_name:"ibuprofen"' in httpx.URL(sent.url).params["search"]
        assert len(results) == 1
        assert results[0]["set_id"] == "abc-123-set"

    @respx.mock
    def test_returns_empty_on_404(self):
        respx.get(OPENFDA_ENDPOINT).mock(return_value=httpx.Response(404, json={"error": "no"}))
        results = asyncio.run(fetch_label("nonexistentdrug", limit=1))
        assert results == []


# ------------------------------------------------------ integration: ingest
@pytest.fixture
def temp_store():
    tmp = tempfile.mkdtemp(prefix="maistorage_fda_")
    os.environ["CHROMA_PATH"] = tmp
    from app.config import get_settings
    get_settings.cache_clear()

    from app.providers import base as provider_base
    from app.retrieval import vectorstore as vs_mod

    vs_mod.reset_vectorstore()
    provider_base._provider_instance = FakeEmbedder()

    yield vs_mod.get_vectorstore()

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    get_settings.cache_clear()


class TestIngestIntegration:
    def test_records_ingest_and_are_retrievable(self, temp_store):
        rec = parse_label(SAMPLE_RESULT)
        stats = asyncio.run(ingest_records([rec]))
        assert stats["labels_indexed"] == 1
        assert stats["chunks_indexed"] == 4
        assert temp_store.count() == 4

        # retrievable: the store holds the ibuprofen sections
        all_chunks = temp_store.get_all_chunks()
        assert any(c.metadata.get("label_id") == "abc-123-set" for c in all_chunks)

    def test_rerun_does_not_duplicate(self, temp_store):
        rec = parse_label(SAMPLE_RESULT)
        asyncio.run(ingest_records([rec]))
        first = temp_store.count()
        # re-run the SAME label: deterministic chunk ids + upsert => no growth
        stats = asyncio.run(ingest_records([rec]))
        assert temp_store.count() == first
        assert stats["labels_indexed"] == 1

    def test_known_label_id_is_skipped(self, temp_store):
        rec = parse_label(SAMPLE_RESULT)
        stats = asyncio.run(ingest_records([rec], known_label_ids={"abc-123-set"}))
        assert stats["labels_indexed"] == 0
        assert stats["skipped"] == 1
        assert temp_store.count() == 0
