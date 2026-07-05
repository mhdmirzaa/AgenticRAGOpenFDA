# Project Structure — MaiStorage (v3.0, course-matched / openFDA)

Monorepo. Agentic RAG **FDA drug-information assistant** built to the production-course
blueprint. Backend is the single writer of the stores; the whole stack runs via one
`docker compose up`.

**Stack:** openFDA · Apache Airflow (@daily) · **OpenSearch (BM25 + kNN, hybrid RRF)** ·
PostgreSQL · Redis · Langfuse · FastAPI (SSE) · **Next.js + TypeScript** UI **+ Telegram bot** ·
OpenAI `gpt-4.1-mini` + `text-embedding-3-large` (3072-d). Chroma retained as offline fallback.

```
maistorage/
├── backend/                          FastAPI + LangGraph agent (Python) — single writer of the stores
│   ├── app/
│   │   ├── main.py                   App factory: routers, CORS, startup warm-up, store selection
│   │   ├── config.py                 Pydantic settings (provider, models, OpenSearch/Chroma/DB/Redis/Langfuse, embed_dim, guardrail, growth)
│   │   ├── models.py                 Schemas: ChatRequest, AskRequest/Response, Citation, TraceStep, ChatStageEvent, ChatEvidenceEvent…
│   │   ├── db.py                     SQLAlchemy: sessions, messages, drug labels, kv_store (growth watermark)
│   │   ├── observability.py          Langfuse Observer (lazy; no-op when keys absent)
│   │   ├── scheduler.py              APScheduler fallback: ingestion + growth jobs (off by default)
│   │   ├── agent/
│   │   │   ├── graph.py              Graph assembly + event-emitting runner (stage/evidence) + non-streaming answer
│   │   │   ├── nodes.py              guardrail / route / rewrite / retrieve / rerank / grade / decide / generate / refuse
│   │   │   ├── prompts.py            GUARDRAIL_PROMPT + caring/neutral refusals + drug-aware grader + generation
│   │   │   └── state.py              RagState TypedDict (incl. blocked / block_category / block_message)
│   │   ├── api/
│   │   │   ├── chat.py               POST /chat — SSE streaming (stage/evidence/token/done)
│   │   │   ├── ask.py                POST /ask-agentic — non-streaming (course-parity + Telegram)
│   │   │   ├── ingest.py             POST /ingest · /ingest/fda (accumulate) · /ingest/fda/grow (one growth batch)
│   │   │   └── sessions.py · trace.py · health.py
│   │   ├── ingestion/                openfda.py (seed + growth + watermark), loader, chunker, indexer  [lazy __init__]
│   │   ├── providers/                Provider-agnostic LLM layer (openai/gemini/groq/ollama/local)
│   │   ├── retrieval/
│   │   │   ├── opensearch_store.py   PRIMARY: BM25 + knn_vector, hybrid via RRF
│   │   │   ├── vectorstore.py        FALLBACK: Chroma (used when OPENSEARCH_URL is empty)  [lazy __init__]
│   │   │   ├── hybrid.py             Chroma + rank-bm25 RRF (fallback hybrid)
│   │   │   ├── reranker.py           Cross-encoder (BAAI/bge-reranker-base; passthrough if unavailable)
│   │   │   └── cache.py              Redis (or in-memory LRU) query/retrieval cache
│   │   └── services/telegram/        Telegram bot: handlers.py (start/help/message) + bot.py (PTB Application)
│   ├── tests/                        15 test modules (unit, agent, guardrail, ask, growth, telegram, persistence, e2e)
│   └── Dockerfile / pyproject.toml
│
├── frontend/                         Next.js + TypeScript UI (warm soft-green split view)
│   ├── components/                   Chat, EvidencePanel, StageTimeline, EvidenceChunkCard, Message, Citations, TracePanel, Disclaimer
│   ├── lib/stream.ts                 SSE client: token/stage/evidence/done; /ask, /grow, /health, /sessions
│   ├── e2e/chat.spec.ts              Playwright e2e (disclaimer, streaming+citations, blocked, refusal)
│   └── playwright.config.ts / Dockerfile
│
├── airflow/dags/fda_ingestion_dag.py @daily: fetch → extract → dedupe → index_and_record → grow_corpus (delegates writes to backend)
├── eval/                             Golden-set harness: run.py, metrics.py, golden.jsonl (17 Qs), last_run_*.json
├── docker-compose.yml               backend, frontend, postgres, opensearch, airflow ×3, telegram-bot
├── docker-compose.redis.yml / .langfuse.yml   optional overlays
└── docs/                            PRD.md, PROJECT_REPORT.md, CHANGES_V3.md, metrics.md, DEMO.md
```

## The agentic loop
`guardrail → route → rewrite → retrieve → rerank → grade → decide → generate / refuse`
(hard cap 3 iterations; guardrail is the first node; only graded chunks reach generation;
empty graded set → clean refusal; citations validated against graded chunk ids.)

## Key endpoints
- `POST /chat` — SSE streaming agentic answer (stage/evidence/token/done)
- `POST /ask-agentic` — non-streaming (course-parity + Telegram)
- `POST /ingest/fda` · `POST /ingest/fda/grow` — seed ingest + one growth batch
- `GET /trace/{id}` · `POST /sessions` · `GET /sessions/{id}/messages` · `GET /health`

## How to run
```
# full stack (recommended)
docker compose up --build
# with optional overlays
docker compose -f docker-compose.yml -f docker-compose.redis.yml -f docker-compose.langfuse.yml up --build

# after it's up: build the 3072-d index
curl -X POST http://localhost:8000/ingest/fda

# eval
cd eval && python run.py --mode baseline    # and --mode optimized

# frontend dev (Next.js)
cd frontend && npm install && npm run dev    # UI on http://localhost:3005
# frontend e2e
cd frontend && npm run test:e2e              # Playwright (stack must be up)
```

## Manual setup (only-you steps)
- Docker Desktop running.
- `OPENAI_API_KEY` in `.env` (bare value — no inline `#` comments; docker `env_file` keeps them).
- `EMBED_MODEL=text-embedding-3-large` (3072-d). If switching stores, reset the store AND its
  dedupe registry together, then re-run `/ingest/fda`.
- Optional: `TELEGRAM__BOT_TOKEN` (from @BotFather) for the Telegram client; Langfuse keys for tracing.