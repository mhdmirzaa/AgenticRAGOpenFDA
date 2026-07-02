# MaiStorage — Agentic RAG · Product Requirements Document

**Version:** 1.0
**Assessment:** Question 1 — Build an Agentic RAG that retrieves chunks correctly
**Author:** (you)
**Status:** Ready to build

---

## 0. TL;DR

MaiStorage is a **near-zero-cost Agentic RAG system** with a **provider-agnostic LLM layer**. It answers questions grounded in a document corpus using a LangGraph agent loop that retrieves, grades its own evidence, re-retrieves when needed, and answers with citations — or refuses when it can't. It ships with a Next.js chat UI, a FastAPI streaming backend, a golden-set test harness with before/after retrieval metrics, and covers **both** bonus criteria (citations + optimized retrieval).

**Locked stack:** LangGraph · Chroma · **provider-agnostic LLM (default: Google Gemini Flash free tier; fallback: Ollama local for a true $0/offline path)** · FastAPI · Next.js + TypeScript.

**LLM provider is a config switch** (`LLM_PROVIDER=gemini|openai|groq|ollama`). Best value for this project is Gemini Flash-Lite/Flash on the free tier (hosted speed + quality at effectively $0, no card), with Ollama kept as the offline fallback so the "fully local, private" story is still available and the demo survives a room with no internet. Embeddings default to Google `text-embedding-005` (~$0.006/1M) or local `nomic-embed-text` ($0) — both negligible.

---

## 1. Objectives

### 1.1 Required (from the brief)
- Build an agentic RAG that **retrieves the correct chunks**.
- Deliver a **working prototype** (demoable).
- Discuss **thought process and implementation flow**.
- Investigate **agentic RAG as a system**.
- Investigate **traditional RAG vs. agentic RAG**.
- Build **test cases to assure quality**.

### 1.2 Bonus (both targeted)
- **Citation handling** — every answer cites its source chunks.
- **Optimized retrieval** — improve accuracy (hybrid + rerank) and performance (cache, async, warm-up).

### 1.3 Non-goals
- No auth/authz.
- No multi-tenant or cloud-scale deployment.
- No expensive flagship models — the LLM layer is deliberately cheap/free-tier (near-$0), with a true $0 offline fallback (Ollama).

---

## 2. Why these choices (design rationale)

| Decision | Choice | Why |
|---|---|---|
| Question | Q1 Agentic RAG | Max technical depth + richest discussion surface; failure mode (retrieval) is engineerable via a golden set |
| Orchestration | **LangGraph** | Brief rewards a visible agent loop (grade/re-retrieve); LangGraph models this as an inspectable state graph |
| Vector DB | **Chroma** | Fully local, `pip install`, no server/Docker layer — least demo friction |
| LLM (generation) | **Provider-agnostic** — default Gemini Flash (free tier); fallback Ollama Llama 3.1 8B | Best value for a graded demo: hosted speed/quality at ~$0 via free tier, with a true $0 offline fallback. Total project cost < $1 either way, so optimize for demo smoothness + a fallback, not sticker price |
| Embeddings | **Google `text-embedding-005`** (~$0.006/1M) or local `nomic-embed-text` ($0) | Negligible cost either way; same model must be used for indexing + querying |
| Frontend | **Next.js + TS** | Plays to existing strength; far more polished demo than Streamlit |
| Corpus | Synthetic company handbook | Every answer known → golden set is trivially correct; clean structure → good chunking; multi-hop questions plantable |

---

## 3. Traditional RAG vs. Agentic RAG (required investigation)

Traditional RAG is a **fixed linear pipeline**: embed query → retrieve top-k → stuff prompt → generate. Fast and simple, but brittle: if the first retrieval misses, the answer is wrong and there is no recovery path.

Agentic RAG wraps retrieval in a **reasoning loop**. The agent decides whether to retrieve, rewrites weak queries, retrieves iteratively, **grades** whether the evidence actually answers the question, and only then generates — or refuses.

| Dimension | Traditional RAG | Agentic RAG |
|---|---|---|
| Control flow | Fixed linear pipeline | Dynamic graph with branching |
| Query handling | Used as-is | Rewritten / decomposed |
| Retrieval | Single top-k pass | Iterative, can re-retrieve |
| Quality control | None | Relevance grading of chunks |
| Failure mode | Hallucinates / wrong answer | Retries, refines, or refuses |
| Multi-hop | Weak | Handles via decomposition |
| Cost / latency | Low | Higher (more LLM calls) |
| Best for | Simple FAQ lookup | Complex, ambiguous, multi-step |

---

## 4. Architecture

```
                    ┌─────────────────────┐
                    │  Next.js + TS UI    │  chat · streaming · citations · trace
                    └──────────┬──────────┘
                               │  SSE
                    ┌──────────▼──────────┐
                    │   FastAPI backend   │  /ingest /chat /trace /health
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  LangGraph agent    │  route→rewrite→retrieve→rerank→grade→decide→generate
                    └──────────┬──────────┘
                       ┌───────┴────────┐
              ┌────────▼──────┐  ┌──────▼────────┐
              │   Chroma      │  │  LLM provider │
              │ (vectors)     │  │ gemini/ollama │
              └───────────────┘  └───────────────┘
```

### 4.1 Ingestion flow
1. Load documents (md/txt/pdf) from `corpus/`.
2. Token-aware chunking (~512 tokens, ~64 overlap), respecting structure (no mid-table/section splits).
3. Embed each chunk via the configured provider (Google `text-embedding-005`, or local `nomic-embed-text`).
4. Upsert vectors + metadata (`source`, `section`, `chunk_id`) into Chroma.

### 4.2 Agentic retrieval flow (LangGraph nodes)
1. **route** — does this need retrieval, or answer directly?
2. **rewrite** — sharpen a vague query into a search query.
3. **retrieve** — hybrid (dense + keyword) candidates from Chroma.
4. **rerank** — local reranker re-orders; keep top-n.
5. **grade** — are these chunks sufficient? (yes/no per chunk)
6. **decide** — sufficient → generate; else loop to rewrite/retrieve (**cap 2–3**).
7. **generate** — answer with inline citations, or refuse.

---

## 5. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Ingest corpus → searchable Chroma index | Must |
| FR-2 | Accept NL question via chat UI | Must |
| FR-3 | Run agentic loop to fetch correct chunks | Must |
| FR-4 | Stream answer token-by-token (SSE) | Must |
| FR-5 | Attach citations (source + section) to answers | Must (bonus) |
| FR-6 | Grade chunks; re-retrieve when insufficient | Must |
| FR-7 | Hybrid search + reranking | Should (bonus) |
| FR-8 | Cache embeddings/results | Should (bonus) |
| FR-9 | Expose retrieval trace (what/why) | Should |
| FR-10 | Refuse gracefully when evidence insufficient | Must |

---

## 6. Non-functional requirements
- **Cost:** near-$0 (Gemini free tier or local Ollama); total project spend < $1; open-source infra throughout.
- **Performance:** first token within a few seconds on 16GB; streamed thereafter.
- **Reproducibility:** one-command startup; committed golden set.
- **Transparency:** agent decisions inspectable (trace endpoint).
- **Portability:** runs offline; no network at inference time.

---

## 7. API design

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/ingest` | Index documents into Chroma |
| POST | `/chat` | Submit question; stream agentic answer (SSE) |
| GET | `/trace/{id}` | Retrieval trace for an answer |
| GET | `/health` | Service + model health |

---

## 8. Test strategy (required deliverable)

| Level | Tests | How |
|---|---|---|
| Unit | chunking, embed calls, Chroma upsert/query | pytest, mocked models |
| Retrieval | correct chunks for known queries | golden set; Hit@k / MRR |
| Agent | routing, grading, re-retrieve decisions | scripted queries assert path |
| E2E | question → cited answer | expected facts + citations |
| Regression | no metric drop after changes | re-run golden set, compare |

**Metrics:** Hit@k, MRR, faithfulness (LLM-as-judge, local), citation accuracy.

**Golden set:** ~15–30 committed `question → expected-source` pairs over the synthetic corpus. Backbone of retrieval + regression tests, and the source of the **before/after optimization table** (baseline vs. hybrid+rerank).

---

## 9. Milestones (de-risked — always demo-safe from M3)

| # | Milestone | Output | Demo-safe? |
|---|---|---|---|
| M1 | Infra + scaffold | LLM provider config (Gemini key or Ollama), Chroma, repo | — |
| M2 | Ingestion | corpus chunked, embedded, indexed | — |
| M3 | Baseline RAG + streaming | single-pass cited answers, SSE | ✅ |
| M4 | Citations | inline citations rendered in UI | ✅ (bonus 1) |
| M5 | Golden set + metrics | Hit@k/MRR harness | ✅ (test deliverable) |
| M6 | Agentic loop | grade + re-retrieve + refuse | ✅ (core) |
| M7 | Optimize | hybrid + rerank; before/after table | ✅ (bonus 2) |
| M8 | Frontend polish + trace | trace view, dry run, slides | ✅ |

Cross into "demo-safe" at M3 and **stay** there — every later stage is additive. If time runs out, you still have a working, cited, measurable RAG.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Chosen LLM too weak on hard Qs | Provider is a config switch — escalate Ollama 8B → Gemini Flash → Gemini Pro in one line; strong retrieval + grading carries most of the quality anyway |
| Agent loop latency | Cap iterations, cache, async, stream, pre-warm |
| Optimization complexity | Bonus only; ship baseline (M3) first, layer after |
| Demo machine pressure | Pre-warm models, pre-index, rehearse |
| Wrong chunk live | Demo only golden-verified questions |

---

## 11. Acceptance criteria
- Correct chunks retrieved for the golden set (Hit@k meets target).
- End-to-end streamed, cited answers in the UI.
- Agent demonstrably re-retrieves or refuses when evidence is insufficient.
- Test suite runs and reports retrieval + answer-quality metrics.
- Both bonuses demonstrable (citations + before/after optimization table).
- Full demo fits 15–20 minutes.

---

## 12. Demo script (15–20 min)

| Time | Segment | Content |
|---|---|---|
| 0–2 | Framing | Problem + traditional-vs-agentic in one slide |
| 2–5 | Architecture | Ingestion + agent-loop diagram |
| 5–12 | Live demo | Easy + hard/multi-hop Qs; streaming + citations + trace; show a refusal |
| 12–16 | Quality | Test suite + before/after metrics table |
| 16–20 | Discussion | Design choices, trade-offs, Q&A |
