"""
Scoped retrieval plumbing + safety fallback (scoped-retrieval branch).

  - OpenSearch drug filter: the `terms` clause is built and threaded into the
    BM25 and kNN request bodies;
  - dense/hybrid search forward the drug_filter;
  - the retrieve node's fallback: a scoped search that returns fewer than
    `scope_min_results` auto-retries UNFILTERED (never below today's recall);
  - the indexer embeds TAGGED text but stores CLEAN text + a drug_key.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.retrieval.opensearch_store import OpenSearchStore


def _reset():
    from app.providers import base as pb
    pb.reset_provider()
    from app.config import get_settings
    get_settings.cache_clear()
    from app.retrieval.cache import clear_cache
    clear_cache()


@pytest.fixture(autouse=True)
def _clean():
    _reset()
    yield
    _reset()


# ------------------------------------------------------- terms filter builder
def test_terms_filter_sorted_and_none():
    assert OpenSearchStore._terms_filter({"beta", "alpha"}) == {
        "terms": {"drug_key": ["alpha", "beta"]}}
    assert OpenSearchStore._terms_filter(None) is None
    assert OpenSearchStore._terms_filter(set()) is None


class _FakeClient:
    """Captures the last search body so we can assert the filter was applied."""

    def __init__(self):
        self.body = None

    def search(self, index, body):
        self.body = body
        return {"hits": {"hits": []}}


def test_bm25_body_includes_filter():
    client = _FakeClient()
    store = OpenSearchStore(client=client, index="t", dim=8)
    store._bm25("warfarin warnings", 8, drug_filter={"warfarin"})
    assert client.body["query"]["bool"]["filter"] == {
        "terms": {"drug_key": ["warfarin"]}}
    assert "match" in client.body["query"]["bool"]["must"]


def test_bm25_body_no_filter_is_plain_match():
    client = _FakeClient()
    store = OpenSearchStore(client=client, index="t", dim=8)
    store._bm25("warfarin warnings", 8, drug_filter=None)
    assert "match" in client.body["query"]
    assert "bool" not in client.body["query"]


def test_knn_scoped_uses_exact_script_score_with_filter():
    # Scoped kNN must be an EXACT script_score search pre-filtered by drug_key —
    # the default engine rejects a filter inside the ANN clause (HTTP 400).
    client = _FakeClient()
    store = OpenSearchStore(client=client, index="t", dim=8)
    store._knn([0.0] * 8, 8, drug_filter={"aspirin", "warfarin"})
    ss = client.body["query"]["script_score"]
    assert ss["query"]["bool"]["filter"] == {
        "terms": {"drug_key": ["aspirin", "warfarin"]}}
    assert ss["script"]["source"] == "knn_score"
    assert ss["script"]["params"]["field"] == "embedding"


def test_knn_unscoped_uses_ann():
    client = _FakeClient()
    store = OpenSearchStore(client=client, index="t", dim=8)
    store._knn([0.0] * 8, 8, drug_filter=None)
    assert client.body["query"]["knn"]["embedding"]["k"] == 8
    assert "script_score" not in client.body["query"]


def test_dense_search_forwards_drug_filter():
    captured = {}
    store = OpenSearchStore(client=None, index="t", dim=8)
    store._knn = lambda vec, size, drug_filter=None: captured.setdefault(
        "f", drug_filter) or []
    store.dense_search([0.0] * 8, top_k=5, drug_filter={"warfarin"})
    assert captured["f"] == {"warfarin"}


def test_hybrid_search_forwards_drug_filter():
    seen = {}

    def _bm25(q, size, drug_filter=None):
        seen["bm25"] = drug_filter
        return []

    def _knn(vec, size, drug_filter=None):
        seen["knn"] = drug_filter
        return []

    store = OpenSearchStore(client=None, index="t", dim=8)
    store._bm25, store._knn = _bm25, _knn
    store.hybrid_search("q", [0.0] * 8, top_k=5, drug_filter={"aspirin"})
    assert seen["bm25"] == {"aspirin"} and seen["knn"] == {"aspirin"}


# --------------------------------------------- retrieve node safety fallback
def test_scoped_too_few_retries_unfiltered(monkeypatch):
    from app.agent import nodes

    calls = []

    async def fake_retrieve(query, use_hybrid, drug_filter):
        calls.append(drug_filter)
        if drug_filter:  # scoped: only 1 hit (< scope_min_results default 3)
            return [{"chunk_id": "s1", "text": "t", "source": "warfarin",
                     "section": "warnings"}]
        return [{"chunk_id": f"u{i}", "text": "t", "source": "warfarin",
                 "section": "warnings"} for i in range(5)]

    monkeypatch.setattr(nodes, "_retrieve_candidates", fake_retrieve)

    state = {
        "question": "warfarin warnings?", "query": "warfarin warnings",
        # Pre-set scope so the node skips entity resolution (no LLM needed).
        "scope": {"kind": "NAMED", "drug_keys": ["warfarin"], "display": "warfarin"},
        "use_scoping": True, "trace": [],
    }
    out = asyncio.run(nodes.retrieve_node(state))

    assert out["scope_path"].startswith("unfiltered(scoped-too-few)")
    assert len(out["candidates"]) == 5                 # the unfiltered result won
    assert any(f for f in calls) and any(f is None for f in calls)  # both passes ran


def test_scoped_enough_keeps_scoped(monkeypatch):
    from app.agent import nodes

    async def fake_retrieve(query, use_hybrid, drug_filter):
        return [{"chunk_id": f"c{i}", "text": "t", "source": "warfarin",
                 "section": "warnings"} for i in range(4)]  # >= min

    monkeypatch.setattr(nodes, "_retrieve_candidates", fake_retrieve)

    state = {
        "question": "warfarin warnings?", "query": "warfarin warnings",
        "scope": {"kind": "NAMED", "drug_keys": ["warfarin"], "display": "warfarin"},
        "use_scoping": True, "trace": [],
    }
    out = asyncio.run(nodes.retrieve_node(state))
    assert out["scope_path"] == "scoped"
    assert len(out["candidates"]) == 4


def test_none_scope_runs_unfiltered(monkeypatch):
    from app.agent import nodes

    async def fake_retrieve(query, use_hybrid, drug_filter):
        assert drug_filter is None  # NONE scope -> never filtered
        return [{"chunk_id": "c1", "text": "t", "source": "x", "section": "s"}]

    monkeypatch.setattr(nodes, "_retrieve_candidates", fake_retrieve)

    state = {
        "question": "hello", "query": "hello",
        "scope": {"kind": "NONE", "drug_keys": [], "display": "all"},
        "use_scoping": True, "trace": [],
    }
    out = asyncio.run(nodes.retrieve_node(state))
    assert out["scope_path"] == "unfiltered"


# ---------------------------------------------------- indexer tagging (item 1)
def test_indexer_embeds_tagged_but_stores_clean(monkeypatch):
    from app.ingestion import indexer
    from app.ingestion.chunker import Chunk

    captured = {"embed": [], "docs": [], "metas": []}

    class _Prov:
        async def embed_batch(self, texts):
            captured["embed"].extend(texts)
            return [[0.1, 0.2, 0.3] for _ in texts]

    class _VS:
        def add(self, ids, embeddings, documents, metadatas):
            captured["docs"].extend(documents)
            captured["metas"].extend(metadatas)

    from app.providers import base as pb
    pb._provider_instance = _Prov()
    monkeypatch.setattr(indexer, "get_vectorstore", lambda: _VS())
    monkeypatch.setattr(
        "app.retrieval.opensearch_store.get_opensearch_store", lambda: None)

    chunk = Chunk(
        text="Do not use in pregnancy.", source="doxycycline",
        section="contraindications", chunk_id="doxycycline#contra:1",
        metadata={"drug_name": "Doxycycline", "label_id": "L1"},
    )
    n = asyncio.run(indexer.index_chunks([chunk]))

    assert n == 1
    assert captured["embed"][0].startswith(
        "[DRUG: Doxycycline | SECTION: contraindications]")
    assert captured["docs"][0] == "Do not use in pregnancy."   # stored clean
    assert captured["metas"][0]["drug_key"] == "doxycycline"   # normalized


def test_indexer_no_drug_name_is_legacy_safe(monkeypatch):
    """A chunk without drug_name (e.g. handbook) embeds unchanged, no drug_key."""
    from app.ingestion import indexer
    from app.ingestion.chunker import Chunk

    captured = {"embed": [], "metas": []}

    class _Prov:
        async def embed_batch(self, texts):
            captured["embed"].extend(texts)
            return [[0.1, 0.2, 0.3] for _ in texts]

    class _VS:
        def add(self, ids, embeddings, documents, metadatas):
            captured["metas"].extend(metadatas)

    from app.providers import base as pb
    pb._provider_instance = _Prov()
    monkeypatch.setattr(indexer, "get_vectorstore", lambda: _VS())
    monkeypatch.setattr(
        "app.retrieval.opensearch_store.get_opensearch_store", lambda: None)

    chunk = Chunk(text="Annual leave is 20 days.", source="handbook.md",
                  section="leave-policy", chunk_id="handbook.md#leave:1")
    asyncio.run(indexer.index_chunks([chunk]))

    assert captured["embed"][0] == "Annual leave is 20 days."  # untagged
    assert "drug_key" not in captured["metas"][0]
