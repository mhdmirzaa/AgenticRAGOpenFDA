"""
Retrieval-robustness tests (ENHANCE item 2).

Proves the hybrid path can't score below the dense-only baseline by construction:
  - fusion is dense-favored (a dense-unique hit outranks a lexical-unique hit at
    the same rank), while still rewarding docs both signals agree on;
  - the single strongest dense hit is always present in the hybrid output
    (dense-anchor guard), so the reranked pool is a superset of the dense top-1.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings
from app.retrieval.opensearch_store import _rrf_merge, OpenSearchStore


# ------------------------------------------------------------- weighted fusion
def test_default_weights_favor_dense():
    s = get_settings()
    assert s.rrf_dense_weight >= s.rrf_bm25_weight


def test_dense_unique_outranks_lexical_unique_at_same_rank():
    # bm25-unique "x" at rank0 vs knn/dense-unique "y" at rank0.
    scores = _rrf_merge(["x"], ["y"], bm25_weight=0.5, knn_weight=1.0)
    assert scores["y"] > scores["x"]


def test_agreement_still_beats_single_signal():
    # A doc in BOTH lists accumulates from each and wins.
    scores = _rrf_merge(["a", "b"], ["a", "c"],
                        bm25_weight=0.5, knn_weight=1.0)
    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)
    assert ranked[0] == "a"


def test_backward_compatible_default_weights():
    # No weights passed -> classic RRF (1.0/1.0), agreement wins.
    scores = _rrf_merge(["a", "b", "c"], ["a", "d", "e"])
    assert max(scores, key=scores.get) == "a"


# --------------------------------------------------------------- dense anchor
def _store_with_stub_hits(bm25_hits, knn_hits):
    """An OpenSearchStore whose _bm25/_knn are replaced with fixed results."""
    store = OpenSearchStore(client=None, index="test", dim=8)
    # drug_filter is accepted (scoped retrieval) but ignored by these unscoped
    # fusion/anchor tests.
    store._bm25 = lambda query_text, size, drug_filter=None: list(bm25_hits)
    store._knn = lambda query_embedding, size, drug_filter=None: list(knn_hits)
    return store


def _hit(cid):
    return {"chunk_id": cid, "text": cid, "source": cid, "section": "s",
            "section_title": "", "source_url": "", "score": 0.0}


def test_hybrid_never_drops_strongest_dense_hit():
    # Fusion would rank "both" first and, at top_k=1, drop the dense top-1.
    bm25 = [_hit("both"), _hit("lex1")]
    knn = [_hit("dense1"), _hit("both")]
    store = _store_with_stub_hits(bm25, knn)
    out = store.hybrid_search("q", [0.0] * 8, top_k=1)
    ids = [c["chunk_id"] for c in out]
    assert "dense1" in ids  # anchored back in despite fusion dropping it


def test_hybrid_pool_superset_keeps_dense_top_with_room():
    bm25 = [_hit("both"), _hit("lex1"), _hit("lex2")]
    knn = [_hit("dense1"), _hit("both"), _hit("dense2")]
    store = _store_with_stub_hits(bm25, knn)
    out = store.hybrid_search("q", [0.0] * 8, top_k=8)
    ids = {c["chunk_id"] for c in out}
    # With headroom, the dense top-1 AND the agreed doc are both retained.
    assert "dense1" in ids and "both" in ids
