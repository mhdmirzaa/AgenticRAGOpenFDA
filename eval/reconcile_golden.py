"""
Reconcile golden.jsonl against the LIVE grown OpenSearch index.
[GROW_AND_REMEASURE item 3 helper]

`_source_match` in metrics.py requires the drug part of an expected source to
equal the indexed `source` (openFDA `generic_name`) exactly — e.g. a question
about metformin must expect "METFORMIN HYDROCHLORIDE#boxed-warning", not
"METFORMIN#boxed-warning". The exact salt form is only knowable from the index,
so this script pins each answerable question's expected_sources to the real
indexed source string (matched by first token) that actually contains the
requested section.

Run AFTER `/ingest/fda` has populated the grown index, BEFORE `eval/run.py`:

    OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
      python -m eval.reconcile_golden          # rewrites eval/golden.jsonl in place
    OPENSEARCH_URL=... python -m eval.reconcile_golden --dry-run   # preview only

Refusal rows (empty expected_sources) are never touched. Unresolved drugs are
reported loudly and left unchanged, so eval reveals a genuine miss rather than a
silently-passing fake.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

GOLDEN = Path(__file__).parent / "golden.jsonl"


def _load_rows() -> list[dict]:
    rows = []
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _candidate_sources(client, index: str, head: str) -> list[str]:
    """Distinct indexed `source` values whose first token is `head` (uppercased)."""
    body = {
        "size": 0,
        "query": {"prefix": {"source": head.upper()}},
        "aggs": {"srcs": {"terms": {"field": "source", "size": 100}}},
    }
    res = client.search(index=index, body=body)
    buckets = res.get("aggregations", {}).get("srcs", {}).get("buckets", [])
    return [b["key"] for b in buckets]


def _source_has_section(client, index: str, source: str, section: str) -> bool:
    body = {
        "size": 0,
        "query": {"bool": {"must": [
            {"term": {"source": source}},
            {"term": {"section": section}},
        ]}},
    }
    res = client.search(index=index, body=body)
    return res["hits"]["total"]["value"] > 0 if isinstance(
        res["hits"]["total"], dict) else res["hits"]["total"] > 0


def reconcile(dry_run: bool = False) -> int:
    from app.retrieval.opensearch_store import get_opensearch_store

    store = get_opensearch_store()
    if store is None:
        print("ERROR: OpenSearch not reachable. Set OPENSEARCH_URL and ingest first.")
        return 2
    client, index = store._client, store._index

    rows = _load_rows()
    rewrites, unresolved = 0, []

    for r in rows:
        new_sources = []
        for src in r.get("expected_sources", []):
            drug, _, section = src.partition("#")
            head = drug.split()[0] if drug else ""
            cands = _candidate_sources(client, index, head) if head else []
            # Prefer a candidate that actually has the requested section.
            chosen = next(
                (c for c in cands if _source_has_section(client, index, c, section)),
                cands[0] if cands else None,
            )
            if chosen is None:
                unresolved.append((r["id"], src))
                new_sources.append(src)  # leave as-is -> honest miss in eval
                continue
            pinned = f"{chosen}#{section}"
            if pinned != src:
                rewrites += 1
                print(f"  {r['id']}: {src!r} -> {pinned!r}")
            new_sources.append(pinned)
        r["expected_sources"] = new_sources

    print(f"\nReconciled {rewrites} source(s); {len(unresolved)} unresolved.")
    if unresolved:
        print("UNRESOLVED (drug not indexed under that first token / no such section):")
        for qid, src in unresolved:
            print(f"  - {qid}: {src}")

    if dry_run:
        print("\n--dry-run: golden.jsonl NOT modified.")
        return 0

    GOLDEN.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote reconciled golden set -> {GOLDEN}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Pin golden expected_sources to the live index")
    ap.add_argument("--dry-run", action="store_true", help="preview, don't write")
    raise SystemExit(reconcile(dry_run=ap.parse_args().dry_run))


if __name__ == "__main__":
    main()
