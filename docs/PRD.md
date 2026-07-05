# MaiStorage — Agentic RAG (Course-Matched) · Product Requirements Document

**Version:** 3.0 (match-the-course / FDA)
**Assessment:** Question 1 — Build an Agentic RAG that retrieves chunks correctly
**Reference architecture:** jamwithai/production-agentic-rag-course (arXiv Paper Curator)
**Framing:** This PRD mirrors the course architecture closely, with deliberate swaps for the
developer's stack and domain: **domain → FDA drug labels**, **LLM → OpenAI**, **embeddings →
text-embedding-3-large**, and **web client → Next.js + TypeScript** (Q1 allows any frontend).
A **Telegram bot** is kept as a second client so the course's multi-client concept still holds.
All other layers (Airflow, PostgreSQL, OpenSearch, Redis, hybrid RRF retrieval, LangGraph agentic
layer, Langfuse) match the course.

---

## 0. TL;DR

An agentic RAG **FDA drug-information assistant** built to the course's production blueprint:
**openFDA** data on an **Apache Airflow** daily schedule → **PostgreSQL + OpenSearch** storage →
**hybrid retrieval (BM25 + vectors, RRF)** → **LangGraph agentic layer**
(guardrail → route → rewrite → retrieve → rerank → grade → decide → generate / refuse) → **OpenAI**
generation → **FastAPI** API →
a **Next.js + TypeScript** web UI **and a Telegram bot**, with **Redis** caching and **Langfuse** observability. The corpus
**grows continuously** from the openFDA API (daily), mirroring the course's daily arXiv sync.

**Stack (course-matched):** openFDA · Apache Airflow · PostgreSQL · **OpenSearch** · Redis ·
Langfuse · FastAPI · **Next.js + TypeScript** + **Telegram bot** · **OpenAI gpt-4.1-mini** + **text-embedding-3-large**.

---

## 1. Objectives

### 1.1 Required (Q1)
- Agentic RAG that retrieves the correct label sections.
- Working prototype / demo.
- Discussion of thought process + implementation flow.
- Investigation of the agentic RAG system.
- Traditional vs agentic RAG.
- Test cases for quality.

### 1.2 Bonus
- Citations (validated against graded chunks).
- Optimized retrieval — accuracy (hybrid + rerank) and performance (Redis cache), measured.

### 1.3 Non-goals
- No auth/authz.
- Not clinical software — informational only; medical disclaimer; answers from retrieved FDA text.

---

## 2. Course parity map (this is the point of v3.0)

| Course layer | Course uses | MaiStorage (this PRD) | Parity |
|---|---|---|---|
| Data source | arXiv API | **openFDA API** | Same pattern, swapped domain (intended) |
| Ingestion orchestrator | Apache Airflow (daily) | **Apache Airflow (daily)** | ✅ exact |
| Parse | Docling (PDF) | Section extraction (openFDA JSON) | Adapted — no PDF, so no Docling |
| Storage | PostgreSQL + **OpenSearch** | **PostgreSQL + OpenSearch** | ✅ exact |
| Cache | Redis | **Redis** | ✅ exact |
| Retrieval | Hybrid BM25 + vectors, RRF | **Hybrid BM25 + vectors, RRF** | ✅ exact |
| Agentic layer | LangGraph (guardrail/grade/rewrite) | **LangGraph (guardrail/route/rerank/grade/decide/refuse)** | ✅ match + explicit guardrail, rerank & refusal |
| LLM | Ollama | **OpenAI gpt-4.1-mini** | Swapped provider (intended) |
| Embeddings | Jina | **OpenAI text-embedding-3-large** | Swapped provider (intended) |
| API | FastAPI (/ask-agentic, /stream) | **FastAPI (/chat SSE, /ask-agentic)** | ✅ exact |
| Observability | Langfuse | **Langfuse** | ✅ exact |
| Clients | Gradio + Telegram | **Next.js + TypeScript** (primary) **+ Telegram bot** | Intended swap — Next.js is the developer's stack; Telegram kept for multi-client parity |
| Corpus behavior | Grows daily (arXiv sync) | **Grows daily (openFDA sync)** | ✅ exact |

**Intended swaps:** domain (FDA), LLM (OpenAI), embeddings (text-embedding-3-large), and the web client (Next.js instead of Gradio — Q1 allows any frontend, and Next.js is the developer's primary stack). Telegram is retained so the course's multi-client concept still holds. Everything else matches the course.

---

## 2b. Safety guardrail (medical domain)

The agent's **first node is a guardrail** that judges whether a question should be answered at all,
before any retrieval. This is distinct from `route` (which decides *where* a safe question goes):

- **Blocks:** self-harm/overdose intent, dangerous misuse ("how to get high on X"), requests for
  **personalized** medical advice (the system gives label info, not individual clinical advice),
  and prompt-injection attempts.
- **Method:** hybrid — a keyword fast-path for obvious cases (instant, free, deterministic) plus one
  small `gpt-4.1-mini` intent check for paraphrased/subtle cases; degrades to keywords if the LLM
  call fails. This avoids false-positives on legitimate dosage questions ("max safe dose" = safe)
  while catching intent-based paraphrases ("what amount would be fatal" = blocked).
- **Refusal tone:** self-harm/overdose → a **caring** refusal that gently declines and points to a
  doctor/pharmacist/helpline; misuse/injection/personalized-advice → a **neutral** clean decline.
  The medical disclaimer is always present.
- **Visibility:** shown as a **"Safety check"** stage in the Next.js evidence panel and recorded in
  the trace — giving a second, distinct refusal moment alongside the off-topic/unanswerable refusal.

This makes the assistant safe for a drug-information domain and demonstrably "knows what it must not
answer," not only "what it cannot find."

## 3. Traditional vs Agentic RAG (required investigation)

Traditional RAG: embed → retrieve top-k → stuff → generate. Fast, brittle, no recovery.
Agentic RAG: a reasoning loop that rewrites weak queries, retrieves iteratively, **grades** its
evidence, and answers or **refuses**.

| Dimension | Traditional | Agentic (this project) |
|---|---|---|
| Control flow | Fixed | Dynamic LangGraph, branching |
| Query | As-is | Rewritten + coreference-resolved |
| Retrieval | Single pass | Iterative, capped re-retrieval |
| Quality control | None | Per-chunk grading |
| Failure | Hallucinates | Refuses + disclaimer |

---

## 4. Architecture (course-matched)

```
openFDA API (/drug/label.json, keyless)          [Embeddings: OpenAI text-embedding-3-large]
        │
   Apache Airflow — Data Processing Pipeline (DAILY sync)
        │  daily sync → fetch + extract sections → chunk + index → clean up
        ▼
   Storage:  PostgreSQL  ──backfilling──►  OpenSearch  (BM25 + kNN vectors)
        │
   Hybrid Retrieval Pipeline (with RRF): hybrid search (BM25 + vectors) → context builder (top-k) → rerank
        │
   Agentic Layer (LangGraph): guardrail → route → rewrite → retrieve → rerank → grade → decide → generate / refuse   (cap 3)
        │
   LLM Generation Layer: OpenAI gpt-4.1-mini + prompt template → answer + sources + metadata
        │            (Redis cache on embeddings/retrieval)
   API Layer: FastAPI — REST + async — POST /ask-agentic · POST /chat (stream)
        │
   Clients:  Next.js + TypeScript UI (warm split-view: chat + live evidence panel)   +   Telegram (bot)
        │
   Observability Layer: Langfuse — traces + prompt versioning
```

---

## 5. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Ingest openFDA labels → OpenSearch (BM25 + vectors), dedupe by label_id | Must |
| FR-2 | Accept NL question via the Next.js web UI and Telegram | Must |
| FR-3 | Agentic loop retrieves correct label sections | Must |
| FR-4 | Stream answer token-by-token (SSE) | Must |
| FR-5 | Citations to exact label section, validated vs graded chunks | Must (bonus) |
| FR-6 | Grade chunks; re-retrieve when insufficient; hard cap 3 | Must |
| FR-7 | Hybrid (BM25 + vectors) + RRF + rerank | Should (bonus) |
| FR-8 | Redis caching (embeddings/retrieval) | Should (bonus perf) |
| FR-9 | Retrieval trace + Langfuse spans | Should |
| FR-10 | Refuse when labels don't cover the question | Must |
| FR-10a | **Guardrail (first node):** block unsafe/off-limits questions before retrieval — self-harm/overdose, dangerous misuse, personalized medical advice, prompt injection | Must (domain safety) |
| FR-10b | Guardrail decision is **hybrid** (keyword fast-path + small gpt-4.1-mini intent check, degrades to keywords on failure) | Should |
| FR-10c | Self-harm/overdose → caring "seek help" refusal; misuse/injection/advice → neutral decline; disclaimer always present | Must (domain safety) |
| FR-10d | Guardrail shown as a **"Safety check" stage** in the Next.js evidence panel + recorded in the trace | Should |
| FR-11 | Airflow DAILY sync; retrying; idempotent | Must (course parity) |
| FR-12 | **Continuous corpus growth** — daily fetch of new openFDA labels | Must (course parity) |
| FR-13 | PostgreSQL persistence: labels + chat sessions/memory | Should |
| FR-14 | Two clients: Next.js web UI (primary) + Telegram bot (messaging channel) | Should |
| FR-15 | Medical disclaimer in answers/UI | Must (domain) |

---

## 6. Non-functional requirements
- **Cost:** near-$0 infra (openFDA keyless; OpenSearch/Redis/Postgres self-hosted); OpenAI usage cents.
- **Embeddings:** **text-embedding-3-large** (3072-dim); chosen before growth so the corpus is
  indexed once and never re-embedded as it grows.
- **Performance:** fast first token (streaming + warm-up + Redis cache).
- **Reproducibility:** `docker compose up`; stable seed drugs keep the golden set valid as the
  corpus grows.
- **Transparency:** trace endpoint + Langfuse.
- **Safety:** answers only from retrieved FDA text; disclaimer; refuse rather than guess.
- **Resilience:** memory/cache/tracing/DB degrade gracefully; a subsystem outage never breaks chat.

---

## 7. Corpus growth (course-style, daily)

- **Seed:** a stable set of common drugs (evergreen) so golden-set eval stays reproducible.
- **Daily sync (Airflow):** fetch openFDA labels updated since a stored **watermark**
  (`effective_time`), extract sections, dedupe by label_id, chunk, embed
  (**text-embedding-3-large**), index into OpenSearch, advance the watermark.
- **Fallback:** if a day's "new" query is sparse, page further into the label catalog so the
  corpus still grows (demonstrable growth even on quiet days).
- **Ordering rule:** the embedding model is fixed to **text-embedding-3-large first** (re-index the
  small seed once), THEN growth is enabled — so the corpus is never re-embedded at scale.
- **Eval reproducibility:** golden questions target seed drugs only; growth is additive.

---

## 8. API design

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /ask-agentic | Agentic answer (course-parity endpoint) |
| POST | /chat | Streaming agentic answer (SSE) |
| POST | /ingest/fda | Seed ingestion into OpenSearch |
| POST | /ingest/fda/grow | One daily growth batch (fetch newest, dedupe, index) |
| GET | /trace/{id} | Retrieval/decision trace |
| POST | /sessions · GET /sessions/{id}/messages | Chat memory |
| GET | /health | Provider, models, OpenSearch doc count, cache stats |

---

## 9. Clients — Next.js web UI (primary) + Telegram bot

### 9.1 Next.js + TypeScript web UI (primary client)
A distinctive, non-generic **warm health-assistant** interface that makes the agent's reasoning
visible. This is the developer's primary stack (Next.js/TypeScript/React) and the main demo surface.

- **Identity:** warm, approachable, **soft-green** palette (health/calm), rounded corners, friendly
  type, generous spacing; trustworthy, with the medical disclaimer always visible.
- **Layout — split view:**
  - **Left (conversation):** streaming answers, tappable inline citation chips, chat history, input.
  - **Right (live evidence panel) — the signature feature:** as the agent runs, an **animated stage
    timeline** lights up in real time (understand → search FDA labels → found N candidates →
    grading M passed → decide → write / refuse), then **settles into the graded chunks** (each with
    drug name + section + PASS/FAIL grade badge) and the final citations. Clicking a citation chip
    on the left highlights its chunk on the right.
- **Why it matters:** it turns the invisible agentic behavior (grading, re-retrieval, and especially
  **refusal**) into watchable moments — the strongest way to demonstrate "agentic" to a grader.
- **Streaming:** reuses the proven SSE client (fetch + getReader + TextDecoder, token/done/error
  contract); the backend additionally emits lightweight **`stage` events** (additive, non-breaking)
  so the evidence panel can animate from the agent's trace.
- **Signature touches:** distinctive streaming cursor, subtle stage animations, a live corpus
  indicator ("N chunks · growing daily"), a thoughtful empty state.

### 9.2 Telegram bot (secondary client — messaging channel, course-faithful)
Mirrors the course's Week-7 Telegram integration structure (`src/services/telegram/` in the course:
command handlers + message processing, wired to an agentic endpoint, async with error handling).

**Structure (matching the course's layout):**
- `services/telegram/` — the bot service:
  - **command handlers** — `/start` and `/help` (welcome + usage + medical disclaimer).
  - **message processing** — on a text message, forward the user's drug question to the backend
    **agentic endpoint** (`/ask-agentic`), then reply with the cited answer + disclaimer.
- Config via **`TELEGRAM__BOT_TOKEN`** env var (BotFather token), matching the course's naming.
- **Async operations + error handling** (course requirement): non-blocking calls to the backend;
  on backend error/timeout, reply with a graceful failure message rather than crashing.
- **Degrades safely:** if `TELEGRAM__BOT_TOKEN` is absent, the bot simply doesn't start; the rest
  of the system is unaffected.

**Flow:** user DMs the bot → message handler → POST to `/ask-agentic` (same backend, same agentic
loop incl. guardrail) → bot returns the answer with citations + the medical disclaimer. No RAG logic
lives in the bot; it is a thin messaging client, proving the backend is client-agnostic.

**Honesty note:** this mirrors the course's *structure and approach* (handlers + message processing +
async + `TELEGRAM__BOT_TOKEN` + agentic endpoint). It is not a line-for-line copy of the course's
source, which lives in the Week-7 release; the implementation should follow the same shape using the
`python-telegram-bot` library.

**Not mobile:** a Telegram bot is a messaging channel, **not** a native mobile app — no
React Native/Flutter involved. (If genuine mobile access in the developer's own stack were desired
later, a React Native or Flutter client is the natural fit; the course used Telegram because it is a
Python team.)

Both clients call the identical backend; no RAG logic lives in the clients.

## 10. Test strategy

| Level | Coverage |
|---|---|
| Unit | openFDA fetch/parse/dedupe, chunking, OpenSearch upsert/query, cache, watermark |
| Retrieval | correct label sections; Hit@k / MRR (section-level) on the seed golden set |
| Agent | routing, grading, refusal, iteration cap, citation validation |
| Safety guardrail | blocks self-harm/misuse/injection/personalized-advice; legit dosage passes (no false-positive); blocked Q never reaches retrieval; LLM-fail degrades to keywords |
| Persistence | labels + sessions/messages + memory |
| Clients | Next.js UI (Playwright: split view, streaming, citation→chunk highlight, evidence stages, refusal); Telegram handler (mocked) |
| E2E | question → cited answer over OpenSearch |
| Production | Airflow daily DAG dedupes/grows; Redis cache hits; Langfuse trace (graceful if off) |

### 10.1 Playwright UI end-to-end test (browser automation)
Closes the "browser e2e not automated" gap and matches production practice. Frontend is
Next.js + TypeScript, so use **@playwright/test** (TypeScript).

- **Setup:** add `@playwright/test` to `frontend/` + a minimal `playwright.config.ts`
  (baseURL `http://localhost:3005`, streaming-tolerant timeout, retries=0 locally);
  npm script `"test:e2e": "playwright test"`.
- **One meaningful spec** against the running stack:
  1. load the app; assert the **medical disclaimer** is visible;
  2. submit "What are the warnings for ibuprofen?"; assert **tokens stream** (assistant text grows);
  3. assert a **citation chip** renders and clicking it highlights its chunk in the right panel;
  4. assert the **evidence panel stages** animate (Safety check → route → search → grade → decide)
     then show graded chunks;
  5. submit an unsafe question; assert the **"Safety check → blocked"** guardrail refusal state;
  6. submit an unindexed-drug question; assert the **unanswerable refusal** state.
- **Rules:** await the final streamed text (don't race the stream); do NOT change app behavior to
  make the test pass — test the real UI.
- **CI note:** intended to run in CI (GitHub Actions) where localhost automation is permitted, since
  local org policy blocked it during earlier verification. Wiring the CI workflow is optional.

**Metrics:** Hit@k, MRR (accuracy); Redis cold-vs-warm latency (performance); faithfulness +
citation accuracy + refusal correctness (answer quality). **Growth benefit:** as the corpus grows,
re-measure the optimized-vs-baseline delta — hybrid+rerank should show a positive Hit@k gain once
retrieval is no longer saturated.

---

## 11. Milestones

| # | Milestone |
|---|---|
| M1 | Switch embeddings → text-embedding-3-large; re-index seed |
| M2 | OpenSearch storage (BM25 + kNN) replaces prior vector store; hybrid RRF native |
| M3 | Airflow DAILY sync + continuous growth (watermark + fallback) |
| M4 | Agentic loop (route/grade/rewrite/refuse) + citations validated + trace |
| M4a | Safety guardrail node (first in graph) + hybrid decision + caring/neutral refusals + "Safety check" UI stage |
| M5 | Redis cache + before/after latency; hybrid+rerank accuracy delta (re-measured as corpus grows) |
| M6 | Next.js web UI (warm split-view + live evidence panel; reuse SSE, add stage events) |
| M7 | Telegram bot client |
| M8 | Langfuse observability (graceful if off) |
| M9 | Dockerize all; golden-set eval; demo docs |

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| OpenSearch swap destabilizes a working build | Isolate + verify no Hit@k regression; keep a revert path |
| Re-embedding cost if model changes later | Fix text-embedding-3-large BEFORE growth; index once |
| openFDA date fields sparse | Fallback paging so growth is always demonstrable |
| Growing corpus breaks golden set | Seed-only golden questions; growth additive |
| Telegram bot scope | Optional client; core RAG unaffected if it slips |
| Medical-domain risk | Disclaimer; retrieval-only answers; refusal |

---

## 13. Acceptance criteria
- Retrieval on OpenSearch returns correct label sections (Hit@k target).
- Streamed, cited answers via the Next.js web UI (with live evidence panel) and Telegram.
- Agent re-retrieves or refuses on insufficient evidence.
- Corpus grows daily from openFDA (seed stable, eval reproducible).
- Both bonuses demonstrable (validated citations; hybrid+rerank accuracy + Redis latency).
- All course layers present and matching (§2 parity map).
- Demo fits 15-20 minutes.

---

## 14. Demo script (15-20 min)
1. Framing + traditional-vs-agentic (2).
2. Architecture — walk the course parity map (§2) (3).
3. Live (Next.js UI): easy drug Q, multi-hop interaction, and TWO kinds of refusal — (a) a
   **guardrail block** on an unsafe question ("Safety check → blocked", caring seek-help message) and
   (b) an unanswerable-question refusal (empty graded set). Show streaming on the left while the
   RIGHT evidence panel animates the stages (Safety check → route → search → grade → decide) then
   reveals graded chunks + citations; show a Telegram query; trigger a growth fetch to show the
   corpus expand live (7).
4. Quality: tests + accuracy and Redis latency tables (4).
5. Discussion: course-matched design, production considerations, Q&A (4).