# FDA Drug-Info RAG — Production Agentic RAG

An **Agentic Retrieval-Augmented Generation** system that answers questions
about FDA-approved drugs — indications, warnings, dosage, adverse reactions,
contraindications, interactions — grounded **only** in official FDA drug-label
text, with citations back to the exact label section, or a graceful refusal when
the labels don't cover it.

> ⚕️ **Informational only — not medical advice.** Answers are drawn solely from
> FDA drug-label text and may be incomplete. Always consult a qualified
> healthcare professional. This disclaimer is enforced in the UI and appended to
> every generated answer.

Built as a production stack adapted from the *production-agentic-rag-course*
(which fetches arXiv papers) to a more serious domain: a drug-information
assistant over the **openFDA API**.

## Architecture

```
                         ┌──────────────── Apache Airflow (or APScheduler) ───────────────┐
                         │  every 15 min:  fetch → extract → dedupe → index → record       │
                         └───────────────┬────────────────────────────────────────────────┘
                                         ▼
   openFDA /drug/label.json ──▶ parse prose sections ──▶ chunk (1/section) ──▶ embed ──▶ Chroma
                                         │                                                  ▲
                                         └── dedupe by label_id ──▶ Postgres (DrugLabel)    │
                                                                                            │
User question ─▶ Route ─▶ Rewrite ─▶ Retrieve ─▶ Rerank ─▶ Grade ─▶ Decide ─▶ Generate/Refuse
                                        ▲   (dense + BM25 hybrid, Redis-cached)  │
                                        └────────── retry (max 3 iterations) ────┘
                                                                                  │
        every step traced to Langfuse (nodes, chunk ids, prompt/response, tokens, cost, latency)
        answers persisted to Postgres (sessions + messages + last-N memory)
```

### Stack
- **Backend**: FastAPI + LangGraph agent + embedded ChromaDB
- **Frontend**: Next.js + TypeScript (streaming, citations, trace panel, history)
- **Data**: openFDA API (`/drug/label.json`, keyless)
- **LLM**: OpenAI `gpt-4.1-mini`; embeddings `text-embedding-3-small`
  (provider-agnostic layer also supports Gemini/Groq/Ollama/local)
- **Retrieval**: Chroma dense + BM25 hybrid (RRF) + optional cross-encoder rerank
- **Persistence**: PostgreSQL (drug labels + chat sessions/messages/memory)
- **Orchestration**: Apache Airflow DAG (in-process APScheduler fallback)
- **Caching**: Redis (query-embedding + retrieval cache), in-memory fallback
- **Observability**: self-hosted Langfuse (per-request tracing)

## Quick start (Docker — full stack)

```bash
cp .env.example .env          # set OPENAI_API_KEY
docker compose up             # backend :8000, frontend :3000, Postgres, Airflow :8080

# add Redis and/or Langfuse (optional enhancements):
docker compose -f docker-compose.yml -f docker-compose.redis.yml \
               -f docker-compose.langfuse.yml up
```

Then open the UI at http://localhost:3000, click **Fetch FDA Labels** to build
the index, and ask a question.

## Quick start (local, no Docker)

```bash
pip install -r requirements.txt
cp .env.example .env          # set OPENAI_API_KEY

# backend
cd backend && uvicorn app.main:app --reload --port 8000

# ingest FDA drug labels (accumulates, deduped by label_id)
curl -X POST http://localhost:8000/ingest/fda

# frontend
cd frontend && npm install && npm run dev     # http://localhost:3000
```

## How the ingestion DAG works

`airflow/dags/fda_ingestion_dag.py` runs on a configurable schedule
(`FDA_DAG_SCHEDULE`, default `*/15 * * * *`):

`fetch_labels → extract_sections → dedupe → index → record`

- **fetch_labels** — pull the seed drugs from openFDA (throttled, keyless)
- **extract_sections** — parse prose sections into per-section records
- **dedupe** — drop any `label_id` already in Postgres
- **index** — chunk (one per section) → embed → upsert into Chroma
- **record** — write `DrugLabel` rows (UNIQUE `label_id` enforces DB-level dedupe)

Idempotent: deterministic chunk ids + Chroma upsert + `label_id` dedupe mean
re-runs never double-index. If Airflow can't run in an environment, the same job
runs in-process via APScheduler (`ENABLE_SCHEDULER=1`, `SCHEDULE_MINUTES`).

## Caching & observability

- **Redis cache** — query embeddings (keyed by normalized question) and
  retrieval results (keyed by query+mode) are cached with a TTL. A repeated
  question skips the embedding round-trip and vector search entirely
  (~1129 ms → ~0.1 ms on the retrieval step; see `docs/metrics.md`). Empty
  `REDIS_URL` → in-memory LRU. Stats on `/health`.
- **Langfuse** — every chat request produces a trace: one span per agent node,
  the retrieved chunk ids, the generation prompt + response, and estimated
  tokens / cost / latency. Fully optional: with no keys (or an unreachable
  server) tracing is a transparent no-op and never breaks a request.

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | health, Chroma count, cache backend + stats |
| `/ingest/fda` | POST | fetch openFDA labels, index (deduped by label_id) |
| `/ingest` | POST | (legacy) rebuild index from `corpus/` |
| `/chat` | POST | agentic RAG over SSE (optional `session_id` for memory) |
| `/trace/{id}` | GET | agent decision trace |
| `/sessions` | POST | create a chat session |
| `/sessions/{id}/messages` | GET | conversation history |

## Traditional RAG vs Agentic RAG

| Aspect | Traditional RAG | Agentic RAG (this system) |
|---|---|---|
| Retrieval | Single pass | Multi-pass (up to 3), self-correcting |
| Query handling | Direct embedding | Route + rewrite/optimize |
| Quality control | None | Grade every chunk before answering |
| Out-of-scope | Hallucinate | Graceful, explicit refusal |
| Citations | Basic or none | Validated against graded chunk ids |
| Transparency | Black box | Full decision trace + Langfuse |

## Evaluation

Real numbers (gpt-4.1-mini, `text-embedding-3-large`, OpenSearch) in `docs/metrics.md`.
Corpus grown to **332 FDA labels / 3,054 chunks**; golden set `eval/golden.jsonl` = **50
questions** (39 single-hop, 6 multi-hop across two drugs, 5 unanswerable/refusal):

```bash
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large python -m eval.run --mode baseline
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large python -m eval.run --mode optimized
```

Headline (grown corpus, 2026-07-06): **baseline dense-only wins** — Hit@1 **0.800** vs
0.720, MRR **0.812** vs 0.750, faithfulness **0.951** vs 0.950. The optimized hybrid+rerank
path **underperforms** here: on a corpus where every drug shares identical section names,
BM25 fusion and a general-domain cross-encoder both pull the *wrong drug's* same-named
section into the top ranks, which strong dense embeddings avoid. Root-caused with a
retrieval-only diagnostic and reported honestly — not tuned away (see `docs/metrics.md`).

**Metadata-scoped retrieval (2026-07-07):** the follow-up fix for that dilution — resolve the
drug(s) a question is about (cached `gpt-4.1-mini`) and restrict retrieval to them before the
similarity search. Live four-config re-measure lifts the **optimized/hybrid** path Hit@1
**0.80 → 0.86**, MRR **0.837 → 0.885** (dense already resolves drug identity, so its Hit@k is
unchanged). Toggle with `ENABLE_SCOPING`; four configs via `--scoped/--no-scoping` (see §14a).

## Performance (v3.2)

The real wins are on latency, all measured live: **batched grading** (one LLM call grades all
reranked candidates instead of one each) — **~12,438 → ~2,080 ms per grading step (5.98×)**; a
**final-answer cache** for exact-repeat stateless questions — **cold ~14,079 ms → warm <1 ms**;
the existing retrieval cache — **cold ~1,905 ms → warm ~0.78 ms**; and the reranker is **baked
into the Docker image** (loaded offline) so optimized mode never cold-starts a download.

## Tests & CI

```bash
cd backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q   # 250 passed
```

**Continuous integration** (`.github/workflows/`): `ci.yml` runs the full backend
suite + frontend `tsc --noEmit` + `next build` on every push/PR (Playwright e2e is
an on-demand job); `security.yml` runs `pip-audit` + `npm audit` + the security
suite. A failure in any blocking job fails the build. See `docs/DEPLOYMENT.md` and
`docs/OPERATIONS.md` for the production story.

## Adapted from the production course / what was skipped

**Adapted:** the production architecture (external API ingestion → Postgres →
scheduled DAG → vector store → agent → UI, plus caching and observability),
retargeted from arXiv papers to openFDA drug labels.

**Deliberately out of scope** (course had these; not needed here): OpenSearch
(kept Chroma+BM25), Docling/PDF pipeline (label text is already prose), arXiv,
Telegram bot, Jina embeddings.

**Redis and Langfuse** are enhancements — the app runs and demos without them,
and each degrades gracefully if absent.

## Production upgrade path

- Chroma → a managed vector DB (pgvector / Qdrant / Weaviate) for horizontal scale
- Airflow on Celery/Kubernetes executor; expand the seed list / add openFDA paging
- Real cross-encoder rerank (BAAI/bge-reranker-base) once the corpus de-saturates
- Redis cluster + answer-level cache; per-tenant rate limiting
- Langfuse dashboards + alerting on faithfulness / refusal regressions
- Auth, PII scrubbing, and an audit trail on the medical disclaimer acceptance

## Optional: Streamlit fallback (`demo_app.py`)

A single-process, no-Node demo fallback that imports the same backend agent
in-process. Use only if Node isn't available or the browser can't reach
`localhost:3000`. The committed primary UI is Next.js.

```bash
pip install streamlit && streamlit run demo_app.py
```

## Project structure

```
maistorage/
├── airflow/dags/            # openFDA ingestion DAG (production orchestrator)
├── backend/
│   ├── app/
│   │   ├── agent/           # LangGraph agent (state, nodes, prompts, graph)
│   │   ├── api/             # health, ingest, chat, trace, sessions
│   │   ├── ingestion/       # openFDA fetch/parse + chunk + index
│   │   ├── providers/       # LLM providers (OpenAI, Gemini, Groq, Ollama, local)
│   │   ├── retrieval/       # vectorstore, hybrid search, reranker, cache (Redis)
│   │   ├── db.py            # SQLAlchemy models + persistence helpers
│   │   ├── scheduler.py     # APScheduler ingestion fallback
│   │   └── observability.py # Langfuse tracing (graceful no-op)
│   └── tests/               # 96 tests
├── frontend/                # Next.js chat UI (streaming, citations, trace, history)
├── eval/                    # golden-set harness (Hit@k, MRR, faithfulness, refusal)
├── docker-compose*.yml      # full stack + redis/langfuse overlays
└── docs/                    # PRD, metrics, demo script
```
