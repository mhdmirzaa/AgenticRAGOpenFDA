# MaiStorage — Agentic RAG (Production Stack) · Product Requirements Document

**Version:** 2.0 (production / openFDA)
**Assessment:** Question 1 — Build an Agentic RAG that retrieves chunks correctly
**Status:** In build on branch `production-stack` (finished handbook Q1 preserved on `working-demo-backup`)

---

## 0. TL;DR

MaiStorage is an **agentic RAG drug-information assistant**. It ingests official **FDA drug-label
text** from the **openFDA API** (keyless), on an **Apache Airflow** schedule, into **Chroma + BM25
hybrid** retrieval. A **LangGraph** agent routes, rewrites, retrieves, reranks, **grades its own
evidence**, re-retrieves up to a hard cap, then answers **with validated citations to the exact
label section** or **refuses**. **PostgreSQL** persists label metadata + chat sessions/memory;
**Redis** caches for performance; **Langfuse** provides end-to-end observability. A **Next.js +
TypeScript** UI streams answers with citations, a retrieval-trace panel, chat history, and a
medical disclaimer.

**Stack:** openFDA · Airflow · Chroma+BM25 · LangGraph · PostgreSQL · Redis · Langfuse · FastAPI ·
Next.js + TypeScript · OpenAI gpt-4.1-mini + text-embedding-3-small · Docker Compose.

**Architecture note:** modeled on the jamwithai/production-agentic-rag-course blueprint (arXiv +
Airflow + Postgres + OpenSearch + Ollama + Gradio), adapted to a healthcare domain and this
stack: openFDA instead of arXiv, Chroma+BM25 instead of OpenSearch, OpenAI instead of Ollama,
Next.js instead of Gradio, plus Redis + Langfuse + an agentic (grade/re-retrieve/refuse) loop.

---

## 1. Objectives

### 1.1 Required (Q1)
- Agentic RAG that **retrieves the correct label sections**.
- **Working prototype** (Next.js UI, demoable).
- **Discussion** of thought process + implementation flow.
- **Investigation** of agentic RAG as a system.
- **Traditional vs agentic RAG** comparison.
- **Test cases** to assure quality.

### 1.2 Bonus (both targeted)
- **Citations** — answers cite the exact FDA label section, validated against graded chunks.
- **Optimized retrieval** — accuracy (hybrid + rerank) AND performance (Redis caching, async,
  warm-up), each measured before/after.

### 1.3 Non-goals
- No auth/authz. No multi-tenant scale-out.
- Not clinical software — informational only; a medical disclaimer is shown and answers come
  solely from retrieved FDA label text.

---

## 2. Design rationale

| Decision | Choice | Why |
|---|---|---|
| Data source | **openFDA API** (`/drug/label.json`) | Keyless like arXiv; rich prose label sections chunk well; serious, impressive domain |
| Orchestration | **Apache Airflow** | Scheduled, retrying, idempotent ingestion (course pattern) |
| Vector store | **Chroma + BM25 hybrid** | Kept from prior build; hybrid = accuracy bonus; avoids an OpenSearch migration |
| DB | **PostgreSQL** | Production-grade persistence for labels + chat memory |
| Cache | **Redis** | Performance bonus; survives restarts; shared cache |
| Observability | **Langfuse** | Per-request tracing (nodes/tokens/latency/cost); strong demo artifact |
| LLM | **OpenAI gpt-4.1-mini** | Reliable instruction-following for cite/refuse; cheap |
| Embeddings | **text-embedding-3-small** | Standard, cheap; same model index + query |
| Frontend | **Next.js + TypeScript** | Primary stack; polished custom UI beats Gradio/Streamlit |
| Agent | **LangGraph** | Explicit grade/re-retrieve/refuse loop = the Q1 "agentic" core |

---

## 3. Traditional RAG vs Agentic RAG (required investigation)

Traditional RAG is a fixed line: embed query → retrieve top-k → stuff prompt → generate. Fast but
brittle — a bad first retrieval yields a wrong answer with no recovery.

Agentic RAG wraps retrieval in a reasoning loop that rewrites weak queries, retrieves iteratively,
**grades** whether evidence is sufficient, and answers or **refuses**.

| Dimension | Traditional RAG | Agentic RAG (this project) |
|---|---|---|
| Control flow | Fixed pipeline | Dynamic graph, branching |
| Query handling | As-is | Rewritten as needed |
| Retrieval | Single pass | Iterative, re-retrieves (cap) |
| Quality control | None | Per-chunk relevance grading |
| Failure mode | Hallucinates | Refuses cleanly |
| Best for | Simple FAQ | Ambiguous/multi-hop; safety-sensitive domains |

---

## 4. Architecture

```
openFDA API (/drug/label.json, keyless)
        │
   Apache Airflow DAG (scheduled, idempotent, dedupe by label_id)
        │  fetch -> extract sections -> chunk -> embed -> index
        ▼
   Chroma (dense) + BM25 (keyword)      PostgreSQL (labels + sessions + messages)
        │                                        ▲
        ▼                                        │
   LangGraph agent: route -> rewrite -> retrieve -> rerank -> grade -> decide -> {generate | loop | refuse}
        │            (Redis cache on embed/retrieve)      (cap=3; only graded chunks generate)
        ▼
   FastAPI  ── /chat (SSE) · /ingest · /trace/{id} · /sessions · /health
        │           (every request traced to Langfuse: nodes, tokens, latency, cost)
        ▼
   Next.js + TypeScript UI (streaming · citations · trace panel · history · medical disclaimer)
```

---

## 5. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Ingest openFDA drug labels → Chroma index (dedupe by label_id) | Must |
| FR-2 | Accept NL question via Next.js chat UI | Must |
| FR-3 | Agentic loop fetches correct label sections | Must |
| FR-4 | Stream answer token-by-token (SSE) | Must |
| FR-5 | Citations to exact label section, validated vs graded chunks | Must (bonus) |
| FR-6 | Grade chunks; re-retrieve when insufficient; hard cap 3 | Must |
| FR-7 | Hybrid (dense+BM25) + reranking | Should (bonus) |
| FR-8 | Redis caching (embeddings/retrieval/answers) | Should (bonus perf) |
| FR-9 | Retrieval trace via /trace/{id} + Langfuse | Should |
| FR-10 | Refuse when labels don't cover the question | Must |
| FR-11 | Airflow DAG: scheduled, retrying, idempotent ingestion | Should |
| FR-12 | Postgres persistence: labels + chat sessions/memory | Should |
| FR-13 | Medical disclaimer in UI + answers | Must (domain) |

---

## 6. Non-functional requirements
- **Cost:** near-$0 — openFDA keyless; only OpenAI usage (cents); Redis/Langfuse/Postgres self-hosted.
- **Performance:** fast first token (streaming + warm-up + Redis cache).
- **Reproducibility:** `docker compose up`; committed golden set with seeded stable drugs.
- **Transparency:** per-request trace (endpoint + Langfuse).
- **Safety:** answers only from retrieved FDA text; disclaimer; refuse rather than guess.
- **Resilience:** app runs even if Langfuse is disabled/unreachable (instrumentation degrades gracefully).

---

## 7. API design

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /ingest | Trigger openFDA ingestion into Chroma |
| POST | /chat | Submit question; stream agentic answer (SSE) |
| GET | /trace/{id} | Retrieval trace for an answer |
| POST | /sessions | Create a chat session |
| GET | /sessions/{id}/messages | Chat history |
| GET | /health | Service + model + cache status |

---

## 8. Test strategy (required deliverable)

| Level | Tests | How |
|---|---|---|
| Unit | section extraction, chunking, embed calls, dedupe | pytest, mocked API/embeddings |
| Retrieval | correct label sections for known drug questions | golden set; Hit@k / MRR (section-level) |
| Agent | grading, re-retrieve, refusal, loop cap | scripted queries assert path |
| E2E | question → cited answer over openFDA data | expected facts + citations |
| Production | Airflow DAG dedupes; Postgres persists + memory; Redis cache hits; Langfuse trace (and app works if off) | integration tests |

**Metrics:** Hit@k, MRR (accuracy); Redis cold-vs-warm latency (performance); faithfulness +
citation accuracy + refusal correctness (answer quality, via gpt-4.1-mini).

**Golden set:** seeded stable drugs (e.g. ibuprofen, amoxicillin, warfarin) so questions are
reproducible; includes multi-hop (interactions) and unanswerable (refusal) cases.

---

## 9. Milestones (de-risked; demo-safe early)

| # | Milestone | Demo-safe? |
|---|---|---|
| M1 | openFDA ingestion + section extraction + dedupe | — |
| M2 | Baseline retrieve + generate + SSE streaming | ✅ |
| M3 | Citations (validated) + Next.js UI + disclaimer | ✅ (bonus 1) |
| M4 | Golden set + accuracy metrics | ✅ (test deliverable) |
| M5 | Agentic loop (grade/re-retrieve/refuse) + trace | ✅ (core) |
| M6 | Hybrid + rerank; before/after accuracy | ✅ (bonus 2a) |
| M7 | PostgreSQL persistence + chat memory | ✅ |
| M8 | Redis caching + before/after latency | ✅ (bonus 2b) |
| M9 | Airflow DAG (scheduled, idempotent) | ✅ |
| M10 | Langfuse observability (graceful if off) | ✅ |
| M11 | Dockerize all + demo docs | ✅ |

Fallback: if a production layer (Airflow/Redis/Langfuse) can't finish, the core RAG + openFDA +
Postgres + UI is still a complete, demoable system. Drop enhancements before dropping a working demo.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Full stack too large for timeline | Priority order; enhancements (Redis/Langfuse) optional; `working-demo-backup` preserved |
| Airflow setup friction | Fall back to a scheduled background fetch; document Airflow as the production orchestrator |
| Langfuse self-host heavy (own DB) | Isolate it; app must run if Langfuse is off |
| News/data churn breaks golden set | Seed stable drugs so golden questions stay valid |
| Medical domain risk | Disclaimer; answer only from retrieved FDA text; refuse when uncovered |

---

## 11. Acceptance criteria
- Correct label sections retrieved on the golden set (Hit@k target met).
- End-to-end streamed, cited answers in the Next.js UI.
- Agent re-retrieves or refuses when evidence is insufficient.
- Tests pass; accuracy AND performance before/after numbers are real.
- Both bonuses demonstrable (validated citations; hybrid+rerank + Redis latency delta).
- Production layers work (Airflow/Postgres/Redis/Langfuse) OR are cleanly documented as the
  upgrade path if a fallback was used.
- Full demo fits 15-20 minutes.

---

## 12. Demo script (15-20 min)
1. Framing + traditional-vs-agentic (2 min).
2. Architecture walk incl. Airflow/Postgres/Redis/Langfuse (3 min).
3. Live demo: easy drug Q, multi-hop interaction Q, and a refusal; show streaming + citations +
   trace panel + Langfuse dashboard (7 min).
4. Quality: test suite + accuracy and Redis latency before/after tables (4 min).
5. Discussion: design choices, production considerations, Q&A (4 min).