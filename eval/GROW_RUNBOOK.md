# Grow + re-measure runbook (GROW_AND_REMEASURE)

Deterministic steps to grow the corpus to ~300 labels and honestly re-measure
baseline vs optimized on the ~50-question golden set. Requires the live stack
(OpenSearch + backend) up and `OPENAI_API_KEY` set.

```bash
# 0. Bring the stack up (OpenSearch, Postgres, Redis, backend, ...)
docker compose up -d --build
#    optional: -f docker-compose.redis.yml   (recommended)

# 1. Grow the index to ~300 labels (SEED_DRUGS now has ~317 names; unresolved
#    names are skipped, so expect ~250-300 labels). Deduped by label_id; embeds
#    with text-embedding-3-large (3072-d) into OpenSearch.
curl -X POST http://localhost:8000/ingest/fda
#    Confirm the grown size:
curl -s http://localhost:8000/health | python -m json.tool   # store.documents ~= 2500-3500 chunks

# 2. Pin the golden set's expected_sources to the EXACT indexed generic_name
#    strings (e.g. metformin -> METFORMIN HYDROCHLORIDE). Never touches refusals.
cd eval
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.reconcile_golden --dry-run        # preview the rewrites first
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.reconcile_golden                  # rewrite golden.jsonl in place
#    Review the "UNRESOLVED" list: any drug not indexed -> drop/adjust that Q
#    (do NOT leave a question pointing at a drug the corpus doesn't have).

# 3. Re-measure — REAL numbers, both modes, against the grown index.
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.run --mode baseline
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.run --mode optimized
#    Raw results: eval/last_run_baseline.json, eval/last_run_optimized.json

# 4. Transcribe the REAL aggregate numbers into:
#      - docs/PROJECT_REPORT.md §14 (metrics table + honest interpretation)
#      - eval/metrics.md (corpus size, golden size, before/after table)
#      - STRUCTURE.md (corpus size mention)
#    If optimized still doesn't beat baseline, say so plainly — do NOT fabricate.

# 5. Verify nothing regressed.
cd ../backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q
cd ../frontend && npx tsc --noEmit && npx next build
PLAYWRIGHT_BASE_URL=http://localhost:3005 npx playwright test   # stack must be up
```

**Honesty rule:** the only permitted tuning if optimized still underperforms is a
minimal RRF/rerank sanity check (`rrf_dense_weight`/`rrf_bm25_weight`,
`rerank_top_n`) — never overfit to the golden set. Report the real delta either way.
