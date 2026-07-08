# Project Structure — MaiStorage Agentic RAG (complete & detailed)

> The **exhaustive, file-by-file** map of the repository as it stands on `main`.
> For the concise annotated summary see [`STRUCTURE.md`](../STRUCTURE.md); for the
> data-flow architecture diagram see [`docs/PRD.md`](PRD.md) §4; for the product
> requirements and course-parity map see the PRD.

**What this project is.** An agentic RAG **FDA drug-information assistant**: it answers
questions about FDA-approved drugs grounded **only** in official FDA drug-label text,
with validated citations back to the exact label section — or a graceful refusal / safety
block. Built to a production-course blueprint. The **backend is the single writer** of the
stores; the whole stack runs via one `docker compose up`.

**Stack (one line).** openFDA · Apache Airflow (`@daily`) · **OpenSearch** (BM25 + kNN,
hybrid RRF; embedded **Chroma** fallback) · PostgreSQL · Redis · Langfuse · FastAPI (SSE) ·
**Next.js + TypeScript "Leaflet" UI** (light default + dark toggle) · **Telegram bot** ·
OpenAI `gpt-4.1-mini` + `text-embedding-3-large` (3072-d).

**Scale at a glance.** Backend ≈ 6.4k LOC Python across 46 modules · 38 test modules /
**271 tests** · frontend 16 components (~1.9k LOC TS/TSX) · **Playwright 5/5** · golden set
50 Qs · corpus grows daily from openFDA.

Legend: `(NNN)` = lines of code · **[primary]** / *[fallback]* / *(optional)* marks the
runtime role · 🔑 = needs a secret/key.

---

## 1. Top-level map (holistic)

```
maistorage/
├── backend/            FastAPI + LangGraph agent (Python) — the brain & single store writer
├── frontend/           Next.js + TypeScript "Leaflet" web UI (primary client)
├── airflow/            Apache Airflow DAG — @daily openFDA ingestion + growth
├── eval/               Golden-set evaluation harness (Hit@k, MRR, faithfulness, refusal)
├── corpus/             Legacy handbook seed (pre-FDA) — still wired in via /ingest, loader.py, compose mount & tests (see §4.3)
├── docs/               PRD, design, metrics, security, deployment, ops, changelog, this file
├── .github/workflows/  CI (tests + build) and security (audits) pipelines
├── docker-compose*.yml Full stack + prod + optional redis/langfuse/override overlays
├── demo_app.py         Streamlit single-process fallback UI (no Node needed) — still wired in (imports loader, reads corpus/)
├── requirements.txt    Root Python deps (for the Streamlit fallback / local runs)
├── run.sh / run_streamlit.sh   Convenience launchers
├── .env.example        Documented env template (copy → .env, fill secrets) 🔑
├── README.md           Project overview + quick start
└── STRUCTURE.md        Concise annotated tree (this file is the exhaustive version)
```

> **Not in the public repo (local-only).** The build-scaffolding and AI-dev tooling used
> to *create* this project are intentionally excluded from the published tree (kept on the
> author's disk, `git rm --cached` + `.gitignore`): `START_HERE.md`, `commands/` (M1–M8
> bootstrap prompts), `.claude/` (vendored ECC/Superpowers skills), and the
> `docs/SKILLS_SETUP.md` · `docs/ECC_SKILLS_MANIFEST.md` · `docs/TOKEN_MONITORING.md`
> meta-docs. They are not product code and a cloner does not need them.

---

## 2. Backend — `backend/` (FastAPI + LangGraph, ~6,439 LOC)

Single writer of OpenSearch/Chroma + Postgres. Store selection, warm-up, and router
wiring happen at app-factory startup. Everything degrades gracefully (missing Redis /
Langfuse / OpenSearch / Telegram token never breaks a chat).

### 2.1 App root — `backend/app/`
```
app/
├── __init__.py
├── main.py            (207)  App factory: routers, CORS, startup warm-up, active-store selection, /metrics mount
├── config.py          (167)  Pydantic settings — provider, models, embed_dim, OpenSearch/Chroma/DB/Redis/Langfuse, guardrail, growth, security toggles
├── models.py          (143)  Pydantic schemas — ChatRequest, AskRequest/Response, Citation, TraceStep, ChatStageEvent, ChatEvidenceEvent…
├── db.py              (305)  SQLAlchemy — sessions, messages, drug_labels, kv_store (growth watermark); engine + session helpers
├── security.py        (203)  Production hardening — API-key auth dependency, rate limiting, security headers, body/question size caps
├── metrics.py         (125)  Prometheus-style counters/histograms (requests, latency, cache, retrieval)
├── logging_config.py  ( 56)  Structured JSON logging setup (JSON_LOGS toggle)
├── observability.py   (136)  Langfuse Observer — lazy; transparent no-op when keys absent (optional) 🔑
└── scheduler.py       (125)  APScheduler fallback — ingestion + growth jobs (off by default; ENABLE_SCHEDULER)
```

### 2.2 Agentic layer — `app/agent/`  (LangGraph state machine)
```
agent/
├── __init__.py
├── state.py    ( 33)  RagState TypedDict — question, chunks, grades, decision, blocked/block_category/block_message, trace
├── graph.py    (517)  Graph assembly + event-emitting runner (stage/evidence SSE) + non-streaming answer path
├── nodes.py    (690)  The nodes: guardrail · route · rewrite · retrieve · rerank · grade · decide · generate · refuse
└── prompts.py  (126)  GUARDRAIL_PROMPT · caring/neutral refusals · drug-aware chunk grader · generation prompt
```
**Graph flow** (hard cap 3 iterations; guardrail is the first node; only graded chunks
reach generation; empty graded set → clean refusal; citations validated vs graded chunk ids):
```
guardrail ─▶ route ─▶ rewrite ─▶ retrieve ─▶ rerank ─▶ grade ─▶ decide ─┬─▶ generate
    │(blocked)                       ▲                                    ├─▶ (loop, ≤3) ─▶ rewrite
    └────────────────────────────────┴── refuse ◀───────────────────────┘(insufficient)
```

### 2.3 API routes — `app/api/`  (FastAPI routers)
```
api/
├── __init__.py
├── chat.py      (117)  POST /chat — SSE streaming (stage / evidence / token / done)
├── ask.py       ( 67)  POST /ask-agentic — non-streaming agentic answer (course-parity; used by Telegram)
├── ingest.py    (111)  POST /ingest · /ingest/fda (seed) · /ingest/fda/grow (one growth batch)
├── sessions.py  ( 54)  POST /sessions · GET /sessions/{id}/messages — chat memory
├── trace.py     ( 50)  GET /trace/{id} — agent decision trace
├── health.py    ( 70)  GET /health — provider, models, active store + doc count, cache stats
└── metrics.py   ( 20)  GET /metrics — Prometheus exposition
```

### 2.4 Ingestion — `app/ingestion/`  (openFDA → chunks → index)
```
ingestion/
├── __init__.py         (lazy: heavy deps imported on first use)
├── openfda.py  (526)  Fetch seed + growth from openFDA; section extraction; watermark; run_fda_growth() paging cursor
├── chunker.py  (222)  One chunk per label section; deterministic chunk ids (idempotent re-index)
├── indexer.py  ( 83)  Embed + upsert into the active store (OpenSearch or Chroma)
└── loader.py   ( 82)  Legacy corpus/ loader (for the /ingest rebuild path)
```

### 2.5 Retrieval — `app/retrieval/`
```
retrieval/
├── __init__.py
├── opensearch_store.py  (285)  [primary]  BM25 text field + knn_vector; hybrid via Reciprocal Rank Fusion
├── vectorstore.py       (174)  [fallback] Embedded Chroma (used when OPENSEARCH_URL is empty; lazy init)
├── hybrid.py            (181)  [fallback] Chroma + rank-bm25 RRF (same fusion as OpenSearch → consistent behaviour)
├── scoping.py           (331)  Metadata-scoped retrieval — resolve target drug(s) (cached gpt-4.1-mini) + dynamic drug catalog, restrict search before similarity
├── reranker.py          ( 69)  Cross-encoder (BAAI/bge-reranker-base; baked into image; passthrough if unavailable)
└── cache.py             (243)  Redis or in-memory LRU — query-embedding / retrieval / final-answer caches
```

### 2.6 LLM providers — `app/providers/`  (provider-agnostic layer)
```
providers/
├── __init__.py
├── base.py     ( 78)  Provider protocol — generate() (streaming) + embed()
├── openai.py   (139)  [default] gpt-4.1-mini + text-embedding-3-large (3072-d) 🔑
├── gemini.py   (156)  Google Gemini (free-tier friendly) 🔑
├── groq.py     ( 97)  Groq 🔑
├── ollama.py   ( 80)  Local Ollama (chat + embed; no key)
└── local.py    ( 52)  Local/offline stub embeddings (tests, no-network)
```

### 2.7 Second client — `app/services/telegram/`
```
services/telegram/
├── __init__.py
├── bot.py       ( 66)  python-telegram-bot Application (long polling); starts only if TELEGRAM__BOT_TOKEN set 🔑
└── handlers.py  (180)  /start · /help · message → POST /ask-agentic → cited answer + disclaimer; async + graceful failure
```

### 2.8 Tests — `backend/tests/`  (38 modules · **271 tests**)
Run offline: `DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q`

| Module | # | Covers | Module | # | Covers |
|---|--:|---|---|--:|---|
| test_scoping.py | 21 | metadata scoping / catalog | test_calibration.py | 8 | refusal calibration |
| test_chunker.py | 19 | section chunking | test_golden_set.py | 7 | golden harness |
| test_agent.py | 16 | graph routing/grading | test_ask.py | 7 | /ask-agentic |
| test_openfda.py | 13 | fetch/parse/dedupe | test_api.py | 7 | route surface |
| test_telegram.py | 12 | bot handlers (mocked) | test_security_injection.py | 6 | prompt/HTTP injection |
| test_scoped_retrieval.py | 12 | scoped retrieval e2e | test_retrieval_robustness.py | 6 | retrieval edge cases |
| test_grade_batch.py | 12 | batched grading | test_resilience.py | 6 | graceful degradation |
| test_guardrail.py | 11 | safety block + degrade | test_prompts.py | 6 | prompt contracts |
| test_scheduler.py | 8 | APScheduler jobs | test_db.py | 6 | persistence |
| test_guardrail_sharpness.py | 8 | false-positive guard | test_answer_cache.py | 6 | final-answer cache |
| … +18 more | | seed_corpus, security_auth/idor/headers/input/hardening, observability, dynamic_catalog, cache, sessions, openai_embed_guard, metrics, http, growth, citations, indexer, reconcile, e2e | | | |

### 2.9 Backend infra files
```
backend/
├── Dockerfile        Multi-stage; bakes the reranker model (offline load)
├── pyproject.toml    Backend package + pinned deps + pytest config
└── maistorage_backend.egg-info/   Build metadata (generated)
```

---

## 3. Frontend — `frontend/` (Next.js + TypeScript "Leaflet", ~1.9k LOC)

"Leaflet" emerald **medical hub**: light default + dark toggle (`next-themes`), a hub
landing that folds into a split-view workspace, and a **live evidence panel** that animates
the agent's reasoning. Full token/type spec in [`docs/DESIGN.md`](DESIGN.md).

```
frontend/
├── app/
│   ├── page.tsx         ( 30)  BRAND="Leaflet"; hub ↔ workspace switch (rename brand in one place)
│   ├── layout.tsx       ( 45)  Root layout; fonts (Fraunces / Plus Jakarta / DM Mono); metadata
│   ├── providers.tsx    ( 23)  next-themes: attribute="class", defaultTheme="light", enableSystem={false}
│   └── globals.css      (105)  Tailwind base + design tokens (emerald/paper/ink/caution/danger/honey)
├── components/
│   ├── Chat.tsx             (317)  Conversation: streaming, input, history, citation chips
│   ├── StageTimeline.tsx    (176)  Animated stage trail — Safety → Scope → Search → Grade → Decide
│   ├── HubLanding.tsx       (165)  Hub dashboard — hero ask bar, stat tiles, quick actions, example cards
│   ├── EvidencePanel.tsx    (118)  Right-hand live evidence panel container
│   ├── Message.tsx          (110)  One message; renders answer + inline [n] citations
│   ├── EvidenceChunkCard.tsx( 85)  Graded chunk card (drug · section · PASS/FILTERED badge)
│   ├── Citations.tsx        ( 83)  Citation list + chip → chunk highlight
│   ├── TracePanel.tsx       ( 73)  Agent decision trace view
│   ├── ThemeToggle.tsx      ( 47)  Header sun/moon; flips class="dark", persists to localStorage
│   ├── Disclaimer.tsx       ( 25)  Always-visible medical disclaimer
│   └── LeafMark.tsx         ( 12)  🌿 wordmark / logo glyph
├── lib/
│   └── stream.ts        (243)  SSE client — token/stage/evidence/done; calls /ask, /grow, /health, /sessions
├── e2e/
│   └── chat.spec.ts     Playwright 5/5 — disclaimer · streaming+citations · citation→chunk · guardrail block · unanswerable refusal
├── public/.gitkeep      (empty public dir kept for the standalone build)
├── Dockerfile           Standalone Next.js production image
├── next.config.js · tailwind.config.ts · postcss.config.js · tsconfig.json
├── playwright.config.ts baseURL http://localhost:3005 (PLAYWRIGHT_BASE_URL override)
├── package.json · package-lock.json · next-env.d.ts · tsconfig.tsbuildinfo
├── .env.local.example   NEXT_PUBLIC_API_BASE=http://localhost:8000
└── test-results/.last-run.json   (generated by Playwright)
```

---

## 4. Data & orchestration

### 4.1 Airflow — `airflow/`
```
airflow/dags/
└── fda_ingestion_dag.py   @daily: fetch_labels → extract_sections → dedupe → index → record → grow_corpus
                           (delegates all store writes to the backend; idempotent; paging fallback on quiet days)
```

### 4.2 Evaluation — `eval/`
```
eval/
├── run.py                (215)  Golden-set runner — --mode baseline|optimized, --scoped/--no-scoping
├── metrics.py            (128)  Hit@k · MRR · faithfulness (LLM judge) · citation/refusal/answer accuracy
├── retrieval_benchmark.py(251)  Retrieval-only diagnostic (raw Hit@k, no LLM grading) — isolates each stage
├── reconcile_golden.py   (138)  Keeps golden.jsonl consistent with the indexed corpus
├── golden.jsonl          50 questions (39 single-hop · 6 multi-hop / 2 drugs · 5 unanswerable)
├── last_run_baseline.json / last_run_optimized.json   Latest scored runs
├── scoped_eval_2026-07-07/   Four-config re-measure (dense/optimized × scoped/unscoped)
└── GROW_RUNBOOK.md       How to grow the corpus + re-run eval
```

### 4.3 Legacy corpus — `corpus/`  ⚠️ still wired in — do NOT remove
```
corpus/
├── handbook.md   Pre-FDA demo corpus (company-handbook Q&A)
└── README.md     Notes on the legacy corpus
```
Predates the openFDA pivot, but **actively referenced** — not orphaned:
- **Live endpoint** `POST /ingest` → `app/ingestion/loader.py::load_corpus()` reads `settings.corpus_path` (`config.py` → `<repo>/corpus`).
- **Compose:** the `backend` service mounts `./corpus:/corpus` (`docker-compose.yml`).
- **Tests:** `test_e2e.py` and `test_observability.py` import & call `load_corpus()`; `test_agent/test_api/test_chunker/test_citations/test_scoped_retrieval` use `handbook.md` as fixture data.
- **Fallback UI:** `demo_app.py` reads `corpus/handbook.md` directly.

Retiring it is a deliberate refactor (endpoint + loader + tests + Streamlit UI), not a safe delete.

---

## 5. Docs — `docs/`
```
docs/
├── PRD.md               Product requirements + course-parity map + architecture diagram (§4)
├── PROJECT_STRUCTURE.md THIS FILE — exhaustive file-by-file map
├── DESIGN.md            "Leaflet" design system — palette, type, light/dark, layout
├── metrics.md           Real golden-set numbers (baseline vs optimized vs scoped) + honest analysis
├── PROJECT_REPORT.md    Full build report / narrative (largest doc)
├── CHANGES_V3.md        v2 → v3 "course-match" migration changelog
├── SECURITY.md          Threat model + hardening (auth, rate limit, headers, input caps)
├── DEPLOYMENT.md        Single-host deploy, reverse-proxy TLS, first-run index build
├── OPERATIONS.md        Runbook — health, cache, growth, troubleshooting
└── DEMO.md              15–20 min live demo script (FDA golden questions)
```
> The `docs/SKILLS_SETUP.md`, `docs/ECC_SKILLS_MANIFEST.md`, and `docs/TOKEN_MONITORING.md`
> meta-docs (Claude-Code / ECC build tooling) are **local-only, excluded from the public repo**.

---

## 6. Infra, CI, and root files

### 6.1 Docker / Compose topology
```
docker-compose.yml            [primary] backend · frontend · postgres · opensearch · airflow ×3 · telegram-bot
docker-compose.prod.yml       Hardened production overlay (restart policies, no dev ports)
docker-compose.redis.yml      (optional) Redis cache overlay
docker-compose.langfuse.yml   (optional) self-hosted Langfuse overlay
docker-compose.override.yml    LOCAL-ONLY (gitignored) — remaps frontend host port 3000 → 3005
```

### 6.2 CI/CD — `.github/workflows/`
```
ci.yml        On every push/PR: backend pytest (271) + frontend tsc --noEmit + next build; Playwright e2e on-demand
security.yml  pip-audit + npm audit + the backend security suite
```

### 6.3 Root loose files
```
.env.example         Documented env template (LLM provider, models, stores, security, growth, Telegram, Langfuse) 🔑
.gitignore           Ignores .env, .env.local, chroma_db/, node_modules/, .next/, override compose, db files
demo_app.py          Streamlit fallback UI — still wired in: imports app.ingestion.loader.load_corpus,
                     reads corpus/handbook.md; launched by run_streamlit.sh; documented in README (§Optional)
requirements.txt     Root Python deps (Streamlit fallback / local runs; provides the streamlit dep)
run.sh · run_streamlit.sh   Launchers (run_streamlit.sh → streamlit run demo_app.py)
README.md · STRUCTURE.md   Entry docs (see §1)   [START_HERE.md kept local-only, excluded from repo]
```

---

## 7. Dev tooling — `.claude/` *(local-only, excluded from the public repo)*
`.claude/skills/` holds **59 vendored skills** (120 files) — the ECC subset + Superpowers
workflow skills used to *build* the project — plus `.claude/ECC_SKILLS_LICENSE`. It is
AI-dev tooling, **not part of the shipped app**, and is intentionally **not published**
(kept on the author's disk via `git rm --cached` + `.gitignore`). A cloner does not need it.

---

## 8. Generated / gitignored (present on disk, not in the tree)
These exist at runtime but are **not committed** (see `.gitignore`):
```
.env · frontend/.env.local          Secrets 🔑 (OpenAI key, Telegram token) — NEVER committed
chroma_db/                          Embedded Chroma store (fallback path artifacts)
maistorage.db                       Local SQLite (default when Postgres isn't used)
docker-compose.override.yml         Local port remap (3000 → 3005)
__pycache__/ · *.egg-info/          Python build/cache
frontend/node_modules/ · .next/     Node deps + Next build output
```

---

## 9. Ports (default topology)

| Service | Container | Host (local) | Notes |
|---|---|---|---|
| Backend (FastAPI) | 8000 | 8000 | REST + SSE |
| Frontend (Next.js) | 3000 | **3005** | override remaps host → 3005; e2e baseURL is 3005 |
| OpenSearch | 9200 | 9200 | primary store |
| PostgreSQL | 5432 | 5432 | labels + chat memory |
| Airflow webserver | 8080 | 8080 | DAG UI |
| Redis *(optional)* | 6379 | 6379 | cache overlay |
| Langfuse *(optional)* | 3000 | 3001 | tracing overlay |
| Streamlit *(fallback)* | 8501 | 8501 | `demo_app.py` |

---

## 10. Runtime data flow (end to end)

```
                       Apache Airflow @daily  (or APScheduler fallback)
                       fetch → extract → dedupe → index → record → grow
                                      │  (backend is the only writer)
openFDA /drug/label.json ─▶ sections ─▶ chunk (1/section) ─▶ embed ─▶ OpenSearch [primary]
                                      └─ dedupe by label_id ─▶ Postgres (DrugLabel)   (Chroma fallback)

User (Leaflet UI  or  Telegram)
   │  POST /chat (SSE)        POST /ask-agentic
   ▼
FastAPI ─▶ LangGraph agent: guardrail ─▶ route ─▶ rewrite ─▶ retrieve ─▶ rerank ─▶ grade ─▶ decide
                               │              (metadata-scoped; Redis-cached; cap 3)      │
                               │(blocked)                                                 ├─▶ generate ─▶ cited answer + disclaimer
                               └──────────────── refuse ◀────────────────────────────────┘(insufficient)
   │
   └─▶ every step traced to Langfuse (nodes, chunk ids, prompt/response, tokens, cost, latency)
       answers persisted to Postgres (sessions + messages + last-N memory)
```

---

*Keep this file in sync with the tree when files are added or renamed. LOC figures are
point-in-time and approximate; the file list and roles are authoritative.*
