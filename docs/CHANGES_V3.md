# MaiStorage — v3.0 "Course-Match" migration notes

**Supersedes** the v2.0 sections of `PROJECT_REPORT.md` where they differ.
Implements `docs/PRD.md` v3.0 (course-matched to jamwithai/production-agentic-rag-course).

This document records the delta from the v2.0 production stack to the v3.0
course-matched architecture. The core agentic RAG (LangGraph loop, validated
citations, refusal, streaming SSE, Postgres memory, Redis cache, Langfuse) is
unchanged; the items below are new or swapped.

---

## What changed (v2.0 → v3.0)

| Area | v2.0 | v3.0 | Where |
|---|---|---|---|
| Embeddings | `text-embedding-3-small` (1536-d) | **`text-embedding-3-large` (3072-d)** | `config.py` (`embed_dim`), `.env`, `providers/openai.py` |
| Primary store | Chroma + rank-bm25 | **OpenSearch (BM25 + kNN, RRF)**, Chroma fallback | `retrieval/opensearch_store.py` |
| Safety | route/refuse only | **guardrail node first** (block unsafe) | `agent/nodes.py::guardrail_node`, `prompts.py` |
| Clients | Next.js only | Next.js **+ Telegram bot** | `services/telegram/` |
| Ingestion cadence | `*/15` | **`@daily` + continuous growth** | `airflow/dags/…`, `ingestion/openfda.py::run_fda_growth` |
| Endpoints | `/chat` | + **`/ask-agentic`**, **`/ingest/fda/grow`** | `api/ask.py`, `api/ingest.py` |
| UI | single column | **split-view + live evidence panel** | `frontend/` (stage/evidence SSE events) |
| Tests | 99 | **122** (+guardrail, ask, growth, telegram) | `backend/tests/` |

---

## 1. Embeddings → text-embedding-3-large (M1)
`embed_dim` (default **3072**) is new and sizes the OpenSearch `knn_vector`
field. `.env` sets `EMBED_MODEL=text-embedding-3-large` + `EMBED_DIM=3072`.
**Re-index required** after this change (old 1536-d vectors are incompatible):
`POST /ingest/fda`. Fix the embedding model **before** enabling growth so the
corpus is embedded once and never re-embedded at scale (PRD §7 ordering rule).

## 2. OpenSearch store (M2)
`retrieval/opensearch_store.py` stores each chunk once with a BM25 `text` field
and a `knn_vector` `embedding` field. Hybrid search runs a BM25 query + a kNN
query and merges them with **Reciprocal Rank Fusion** (same fusion as the Chroma
fallback → consistent behaviour). Entirely optional and probed once:
`get_opensearch_store()` returns `None` unless `OPENSEARCH_URL` is set **and**
the cluster is reachable — otherwise the app falls back to embedded Chroma +
rank-bm25 (keeps the 122 offline tests green; preserves a revert path). The
indexer, `retrieve_node`, `/health`, and startup all select the active store.

## 3. Safety guardrail (M4a)
`guardrail_node` is the **first** node in the graph (before route/retrieval).
Hybrid decision: a deterministic keyword fast-path handles obvious cases free +
instantly; anything undecided goes to one small `gpt-4.1-mini` intent check that
**degrades to the keyword verdict on failure**. Categories & tone:
- `SELFHARM` → a **caring** "please seek help" refusal (points to 988).
- `MISUSE` / prompt-injection → a **neutral** decline.
- `ADVICE` (personalized clinical advice) → a neutral "can't advise on your case".
- `SAFE` (incl. legitimate max-dose questions) → proceeds.

A blocked question **never reaches retrieval** (verified in `test_guardrail.py`).
Surfaced as a **"Safety check"** stage in the UI + a `guardrail`/`refuse` trace
step. Toggle with `ENABLE_GUARDRAIL`.

## 4. Telegram bot (M7)
`services/telegram/` — course-faithful structure: `handlers.py` (`/start`,
`/help`, message processing) + `bot.py` (python-telegram-bot Application, long
polling). A text message is forwarded to the backend **`/ask-agentic`** endpoint
(the bot holds **no** RAG logic) and answered with citations + the disclaimer.
Async + graceful failure on backend error. Configured via `TELEGRAM__BOT_TOKEN`
(course naming; `TELEGRAM_BOT_TOKEN` also accepted). **Degrades safely:** no
token → the bot logs and exits cleanly; the rest of the stack is unaffected.

## 5. Daily sync + continuous growth (M3)
Airflow DAG schedule is now **`@daily`** with a fifth task `grow_corpus` that
delegates to **`POST /ingest/fda/grow`**. `run_fda_growth()` fetches the next
page of newest labels (`sort=effective_time:desc` + a persisted `skip` cursor in
the `kv_store` table), dedupes by `label_id`, indexes the fresh ones, and
advances the watermark — additive + idempotent, and it keeps growing even on
quiet days (paging fallback). The APScheduler fallback registers the same job.

## 6. Endpoints
- **`POST /ask-agentic`** — non-streaming agentic answer `{answer, citations,
  trace_id, refused, blocked}` (course-parity name; used by Telegram).
- **`POST /ingest/fda/grow`** — one growth batch.

## 7. Streaming contract (additive, non-breaking)
`/chat` now also emits, alongside `token`/`done`/`error`:
- `{"type":"stage","stage":…,"status":"active|done","detail":…}` — live agent
  stages: `safety → route → search → grade → decide → generate|refuse|blocked`.
- `{"type":"evidence","chunks":[{…,"grade":"PASS|FAIL"}]}` — graded candidates.
`done` now carries `blocked` in addition to `refused`.

## 8. Frontend (M6)
Warm soft-green **split-view**: left = streaming conversation with tappable `[n]`
citation chips; right = **live evidence panel** whose stage timeline animates
from the `stage` events, then settles into graded chunks with PASS/FAIL badges.
Clicking a citation highlights its chunk (by `chunk_id`). Live corpus indicator
("N label chunks · growing daily"), Grow-corpus button, always-visible
disclaimer, light/dark. **Playwright** e2e (`frontend/e2e/chat.spec.ts`,
`playwright.config.ts`) covers disclaimer, streaming, citation→chunk highlight,
stage animation, guardrail block, and unanswerable refusal.

> **Since superseded:** the split-view was later restyled into the **"Leaflet"**
> emerald medical-hub identity (light default + dark toggle, hub landing). The old
> "soft-green" descriptor above is the v3-snapshot look — see `docs/DESIGN.md` for
> the current UI.

---

## How to run (v3.0)

```bash
cp .env.example .env          # set OPENAI_API_KEY; EMBED_MODEL=text-embedding-3-large
docker compose up -d --build  # backend, frontend, Postgres, OpenSearch, Airflow, telegram-bot
curl -X POST http://localhost:8000/ingest/fda        # build the 3072-d index
curl -X POST http://localhost:8000/ingest/fda/grow   # one growth batch (or let Airflow @daily)
# optional overlays: docker-compose.redis.yml, docker-compose.langfuse.yml
```

- OpenSearch is auto-used in docker (`OPENSEARCH_URL=http://opensearch:9200`).
  Locally, leave `OPENSEARCH_URL` empty to use the Chroma fallback.
- Telegram: set `TELEGRAM__BOT_TOKEN` (BotFather) to activate the bot.

## Tests

```bash
cd backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q   # 122 passed (at v3 cut; 271 on main today)
cd frontend && npx tsc --noEmit && npm run build                        # clean
```

## Known follow-ups (not blocking)
- Live golden-set metrics were **not** re-run here (needs a real API key + a
  3072-d re-index); `eval/` harness is unchanged and ready. Re-running under
  OpenSearch + `text-embedding-3-large` is the intended before/after step, and
  the growing corpus should finally give hybrid+rerank measurable Hit@k headroom
  (v2.0 saturated at 23 labels).
- `playwright test` needs the stack up (org policy blocked localhost earlier);
  the spec is written + guarded, intended for CI.
