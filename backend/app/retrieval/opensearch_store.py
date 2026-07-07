"""
OpenSearch store (course-parity primary retrieval).  [PRD v3.0 M2]

Stores each chunk once with BOTH a BM25-analyzed `text` field and a `knn_vector`
`embedding` field, so a single index serves keyword AND dense retrieval. Hybrid
search runs a BM25 query and a kNN query and merges them with Reciprocal Rank
Fusion (RRF) — the same fusion the Chroma+rank-bm25 fallback uses, so the two
backends are behaviorally consistent.

Entirely optional: `get_opensearch_store()` returns None unless `OPENSEARCH_URL`
is set AND the cluster is reachable. When None, the app falls back to the
embedded Chroma + rank-bm25 path (keeps offline tests green; preserves a revert
path per the risk register).
"""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def _rrf_merge(bm25_ids, knn_ids, k: int = 60,
               bm25_weight: float = 1.0, knn_weight: float = 1.0):
    """Weighted Reciprocal Rank Fusion over two ranked id lists -> {id: score}.

    Each list contributes `weight / (k + rank + 1)` per id. Default weights are
    1.0/1.0 (classic RRF); the hybrid searcher passes a dense-favored pair so a
    strong dense hit isn't demoted by a lexical-only match. A doc appearing in
    BOTH lists still accumulates from each, so agreement is rewarded.
    """
    scores: dict[str, float] = {}
    for ranked, weight in ((bm25_ids, bm25_weight), (knn_ids, knn_weight)):
        for rank, cid in enumerate(ranked):
            scores[cid] = scores.get(cid, 0.0) + weight / (k + rank + 1)
    return scores


class OpenSearchStore:
    """Thin wrapper: index chunks (BM25 + kNN) and hybrid/dense search them."""

    def __init__(self, client, index: str, dim: int) -> None:
        self._client = client
        self._index = index
        self._dim = dim

    # ------------------------------------------------------------- index mgmt
    def ensure_index(self) -> None:
        """Create the index with a BM25 text field + a knn_vector field."""
        if self._client.indices.exists(index=self._index):
            return
        body = {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "source": {"type": "keyword"},
                    "section": {"type": "keyword"},
                    "section_title": {"type": "keyword"},
                    "source_url": {"type": "keyword"},
                    "label_id": {"type": "keyword"},
                    # Metadata-scoped retrieval: drug identity as keyword fields.
                    # `drug_key` is the normalized (lowercase) generic used by the
                    # scoped `terms` filter; drug_name/brand_name are for display.
                    "drug_name": {"type": "keyword"},
                    "brand_name": {"type": "keyword"},
                    "drug_key": {"type": "keyword"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self._dim,
                    },
                }
            },
        }
        self._client.indices.create(index=self._index, body=body)
        logger.info("created OpenSearch index %s (dim=%d)", self._index, self._dim)

    def reset(self) -> None:
        """Delete + recreate the index."""
        try:
            self._client.indices.delete(index=self._index, ignore=[404])
        except Exception:
            pass
        self.ensure_index()

    def count(self) -> int:
        try:
            self._client.indices.refresh(index=self._index)
            return int(self._client.count(index=self._index)["count"])
        except Exception:
            return 0

    # ----------------------------------------------------------------- writes
    def add(self, ids, embeddings, documents, metadatas) -> None:
        """Bulk upsert chunks (deterministic ids -> idempotent re-index)."""
        from opensearchpy.helpers import bulk

        self.ensure_index()
        actions = []
        for cid, emb, doc, meta in zip(ids, embeddings, documents, metadatas):
            actions.append({
                "_op_type": "index",
                "_index": self._index,
                "_id": cid,
                "_source": {
                    "text": doc,
                    "embedding": emb,
                    "source": meta.get("source", ""),
                    "section": meta.get("section", ""),
                    "section_title": meta.get("section_title", ""),
                    "source_url": meta.get("source_url", ""),
                    "label_id": meta.get("label_id", ""),
                    "drug_name": meta.get("drug_name", ""),
                    "brand_name": meta.get("brand_name", ""),
                    "drug_key": meta.get("drug_key", ""),
                    "chunk_id": cid,
                },
            })
        bulk(self._client, actions)
        self._client.indices.refresh(index=self._index)

    # ---------------------------------------------------------------- queries
    def _hit_to_dict(self, hit, score) -> dict:
        src = hit.get("_source", {})
        return {
            "chunk_id": hit.get("_id", ""),
            "text": src.get("text", ""),
            "source": src.get("source", ""),
            "section": src.get("section", ""),
            "section_title": src.get("section_title", ""),
            "source_url": src.get("source_url", ""),
            "score": score,
        }

    @staticmethod
    def _terms_filter(drug_filter):
        """OpenSearch `terms` clause restricting to a set of drug_keys, or None."""
        if not drug_filter:
            return None
        return {"terms": {"drug_key": sorted(drug_filter)}}

    def _bm25(self, query_text: str, size: int, drug_filter=None) -> list[dict]:
        match = {"match": {"text": query_text}}
        terms = self._terms_filter(drug_filter)
        query = {"bool": {"must": match, "filter": terms}} if terms else match
        body = {"size": size, "query": query}
        res = self._client.search(index=self._index, body=body)
        return [self._hit_to_dict(h, h.get("_score", 0.0))
                for h in res["hits"]["hits"]]

    def _knn(self, query_embedding, size: int, drug_filter=None) -> list[dict]:
        terms = self._terms_filter(drug_filter)
        if terms:
            # Scoped kNN: EXACT (brute-force) search over just the filtered drug
            # set via script_score + `knn_score`. The default kNN engine rejects a
            # filter *inside* the ANN clause (HTTP 400), and an exact search over a
            # single drug's handful of chunks is both cheap and more accurate than
            # ANN — exactly what metadata scoping wants.
            body = {
                "size": size,
                "query": {"script_score": {
                    "query": {"bool": {"filter": terms}},
                    "script": {
                        "source": "knn_score", "lang": "knn",
                        "params": {"field": "embedding",
                                   "query_value": query_embedding,
                                   "space_type": "cosinesimil"},
                    },
                }},
            }
        else:
            # Unscoped: fast approximate kNN over the whole index.
            body = {"size": size,
                    "query": {"knn": {"embedding": {"vector": query_embedding,
                                                    "k": size}}}}
        res = self._client.search(index=self._index, body=body)
        return [self._hit_to_dict(h, h.get("_score", 0.0))
                for h in res["hits"]["hits"]]

    def dense_search(self, query_embedding, top_k: int = 8,
                     drug_filter=None) -> list[dict]:
        """kNN-only search (baseline mode), optionally scoped to a drug set."""
        try:
            return self._knn(query_embedding, top_k, drug_filter)
        except Exception as e:
            logger.warning("OpenSearch kNN search failed: %s", e)
            return []

    def hybrid_search(self, query_text: str, query_embedding,
                      top_k: int = 8, drug_filter=None) -> list[dict]:
        """BM25 + kNN, merged with RRF (optimized mode), optionally drug-scoped."""
        try:
            bm25 = self._bm25(query_text, top_k * 2, drug_filter)
            knn = self._knn(query_embedding, top_k * 2, drug_filter)
        except Exception as e:
            logger.warning("OpenSearch hybrid search failed: %s", e)
            return []
        settings = get_settings()
        by_id = {c["chunk_id"]: c for c in bm25}
        for c in knn:
            by_id.setdefault(c["chunk_id"], c)
        fused = _rrf_merge(
            [c["chunk_id"] for c in bm25],
            [c["chunk_id"] for c in knn],
            bm25_weight=settings.rrf_bm25_weight,
            knn_weight=settings.rrf_dense_weight,
        )
        ranked_ids = [cid for cid, _ in
                      sorted(fused.items(), key=lambda kv: kv[1], reverse=True)]
        top_ids = ranked_ids[:top_k]

        # Dense-anchor guard: never let fusion drop the single strongest dense
        # hit. On a saturated corpus dense already places the right section at
        # top-1; this guarantees it survives into the reranked pool, so the
        # optimized path can't fall below the dense-only baseline on recall.
        if knn:
            dense_top = knn[0]["chunk_id"]
            if dense_top not in top_ids:
                if len(top_ids) >= top_k and top_ids:
                    top_ids[-1] = dense_top
                else:
                    top_ids.append(dense_top)

        out = []
        for cid in top_ids:
            c = dict(by_id.get(cid, {}))
            c["score"] = fused.get(cid, 0.0)
            out.append(c)
        return out


_store: OpenSearchStore | None = None
_probed = False


def get_opensearch_store() -> OpenSearchStore | None:
    """Return the OpenSearch store if configured + reachable, else None.

    Probed once; a failure (not configured / unreachable / driver missing)
    caches None so the app cleanly falls back to Chroma.
    """
    global _store, _probed
    if _probed:
        return _store
    _probed = True

    settings = get_settings()
    url = settings.opensearch_url
    if not url:
        return None
    try:
        from opensearchpy import OpenSearch

        http_auth = None
        if settings.opensearch_user:
            http_auth = (settings.opensearch_user, settings.opensearch_password)
        client = OpenSearch(
            hosts=[url],
            http_auth=http_auth,
            use_ssl=url.startswith("https"),
            verify_certs=False,
            timeout=30,
        )
        client.info()  # probe
        store = OpenSearchStore(client, settings.opensearch_index, settings.embed_dim)
        store.ensure_index()
        _store = store
        logger.info("OpenSearch store active: %s / %s", url, settings.opensearch_index)
    except Exception as e:
        logger.warning("OpenSearch unavailable (%s); using Chroma fallback", e)
        _store = None
    return _store


def reset_opensearch_store() -> None:
    """Drop the probe cache (tests / config changes)."""
    global _store, _probed
    _store = None
    _probed = False


def opensearch_enabled() -> bool:
    return get_opensearch_store() is not None
