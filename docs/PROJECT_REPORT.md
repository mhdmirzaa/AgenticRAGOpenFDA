# MaiStorage — Agentic RAG (Course-Matched Stack) · Complete Project Report

**Version:** 3.0 (course-matched / openFDA)
**Date:** 2026-07-04
**Assessment:** Question 1 — Build an Agentic RAG that retrieves chunks correctly.
**Reference architecture:** jamwithai/production-agentic-rag-course (arXiv Paper Curator), adapted to the FDA drug domain.
**Domain:** FDA drug-information assistant over official **openFDA** drug-label text.
**Stack:** openFDA · Apache Airflow (daily) · **OpenSearch (BM25 + kNN, hybrid RRF)** · Redis · Langfuse · FastAPI (SSE) · **Next.js + TypeScript** web UI **+ Telegram bot** · Docker Compose · **OpenAI `gpt-4.1-mini`** + **`text-embedding-3-large` (3072-d)**. Chroma is retained as a graceful offline fallback store.
**Status:** ✅ **Ready to submit.** All required tasks and both bonuses met with real, reproducible evidence, verified end-to-end on a live `docker compose` stack on **2026-07-04**: **124 backend tests pass**, **Playwright e2e 4/4** against the running UI, live golden-set eval reproduced, and every production layer (OpenSearch, Airflow daily DAG, Postgres, Redis, Langfuse, Telegram) exercised. A subsequent **quality-hardening pass (v3.1, 2026-07-05)** improved answer quality, retrieval robustness, guardrail sharpness, UI polish, and error resilience — growing the suite to **150 backend tests (all pass offline)** with a clean `tsc --noEmit` + `next build`; see [§1a](#1a-enhancement-pass-v31-2026-07-05).

> This report supersedes the v2.0 "production-stack" report. The migration delta is
> summarized in `docs/CHANGES_V3.md`; the requirements are in `docs/PRD.md` (v3.0).

---

## Table of contents
1. [Executive summary](#1-executive-summary)
1a. [Enhancement pass (v3.1)](#1a-enhancement-pass-v31-2026-07-05)
1b. [Performance pass (v3.2)](#1b-performance-pass-v32-2026-07-06)
1c. [Metadata-scoped retrieval pass (2026-07-07)](#1c-metadata-scoped-retrieval-pass-scoped-retrieval-2026-07-07)
1d. [UI redesign — "Monograph" (2026-07-07)](#1d-ui-redesign--monograph-ui-redesign-2026-07-07)
1e. [Security-hardening pass (2026-07-07)](#1e-security-hardening-pass-security-hardening-2026-07-07)
1f. [Production-hardening pass (2026-07-07)](#1f-production-hardening-pass-production-hardening-2026-07-07)
2. [Course parity map](#2-course-parity-map)
3. [Repository structure](#3-repository-structure)
4. [Architecture](#4-architecture)
5. [End-to-end request flow](#5-end-to-end-request-flow)
6. [The agentic loop (with safety guardrail)](#6-the-agentic-loop-with-safety-guardrail)
7. [Retrieval subsystem (OpenSearch + fallback)](#7-retrieval-subsystem-opensearch--fallback)
8. [Data, ingestion & continuous growth](#8-data-ingestion--continuous-growth)
9. [Clients: Next.js web UI + Telegram bot](#9-clients-nextjs-web-ui--telegram-bot)
10. [Persistence, memory & observability](#10-persistence-memory--observability)
11. [API reference](#11-api-reference)
12. [Test strategy & results](#12-test-strategy--results)
13. [Live full-stack verification (2026-07-04)](#13-live-full-stack-verification-2026-07-04)
13a. [Grow + re-measure verification (2026-07-06)](#13a-grow--re-measure-verification-2026-07-06)
14. [Metrics (real, reproducible)](#14-metrics-real-reproducible)
14a. [Metadata-scoped retrieval results (2026-07-07)](#14a-metadata-scoped-retrieval-scoped-retrieval-branch)
15. [Defects found & fixed during verification](#15-defects-found--fixed-during-verification)
16. [Assessment Q1 alignment audit](#16-assessment-q1-alignment-audit)
17. [PRD coverage & the approach settled on](#17-prd-coverage--the-approach-settled-on)
18. [Reference-repo gap analysis (course repo vs this project)](#18-reference-repo-gap-analysis-course-repo-vs-this-project)
19. [Pros / strengths](#19-pros--strengths)
20. [Cons / limitations & mitigations](#20-cons--limitations--mitigations)
21. [How to run](#21-how-to-run)
22. [Traditional vs agentic RAG](#22-traditional-vs-agentic-rag)
23. [UI — "Monograph" redesign](#23-ui--monograph-redesign-ui-redesign)
24. [Security posture](#24-security-posture-security-hardening)
25. [Production readiness](#25-production-readiness-production-hardening)

---

## 1. Executive summary

MaiStorage is an **agentic RAG drug-information assistant** built to a production
course blueprint. A LangGraph agent runs **guardrail → route → rewrite → retrieve →
rerank → grade → decide → generate / refuse**, capped at 3 iterations. The **safety
guardrail is the first node**: it blocks self-harm/overdose, misuse, prompt-injection,
and requests for personalized medical advice *before any retrieval*, with a caring
refusal for self-harm and a neutral decline otherwise. Every non-refusal answer carries
**citations validated against the exact graded chunks**, each mapped to a real FDA label
section; when nothing relevant is found the agent **refuses cleanly instead of
hallucinating**, and every answer shows a medical disclaimer.

Around that core is the course-matched production stack: **openFDA** ingestion on a
**daily Apache Airflow** schedule with **continuous corpus growth**, **OpenSearch**
(BM25 + kNN, hybrid via Reciprocal Rank Fusion) as the primary store with a cross-encoder
reranker, **PostgreSQL** for label metadata + chat sessions/memory + a growth watermark,
**Redis** caching, **Langfuse** observability, a **FastAPI** SSE backend, a **Next.js +
TypeScript** streaming chat UI with a **live evidence panel**, and a **Telegram bot** as
a second client — all brought up by one `docker compose up`.

This report was produced by bringing the whole stack up live and exercising every layer
on **2026-07-04**, then extended in six passes: a **grow + re-measure** (corpus grown
**~14× to 332 FDA labels / 3,054 chunks**, honest baseline-vs-optimized re-measure on an
expanded **50-question** golden set — §13a/§14), a **v3.2 performance pass** (batched grading,
answer cache, image-baked reranker — §1b), a **metadata-scoped retrieval pass** (2026-07-07)
that went back at the retrieval problem §14 root-caused — drug-scoping the candidate set before
similarity search (§1c/§14a), a **UI redesign** into a distinctive "Monograph" clinical-instrument
identity (§1d/§23, `docs/DESIGN.md`), and a **security-hardening pass** taking the stack to a
strong production posture — auth, rate limiting, IDOR/injection/XSS defenses, secrets & container
hygiene, each with a test that proves the attack is blocked (§1e/§24, `docs/SECURITY.md`), and a
**production-hardening pass** closing the last "prototype → deployable" gaps — frontend auth
wiring, a CI pipeline, structured logging + a `/metrics` endpoint, and a full deployment story
(§1f/§25, `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md`).
**Five real defects were found and fixed** during the original verification (see §15). Final
state: **255 backend tests pass** (35 of them new security/observability/scoping tests), **Playwright e2e
is 6/6** against the running UI, the golden-set eval is reproduced live on the grown index, and
every production layer works. Three honest headlines: the grown-corpus re-measure showed the optimized
hybrid+rerank path **underperforming** dense-only retrieval (reported and root-caused, not tuned
away — §14); the v3.2 pass delivered the real wins on **latency** — **5.98× faster grading** and
an answer cache that makes exact repeats **instant** (§1b, §14); and metadata scoping **recovers
most of the hybrid path's dilution loss** (optimized Hit@1 **0.80 → 0.86**, MRR **0.837 → 0.885**),
while dense-only still leads raw Hit@1 (0.90) — all measured live, nothing overfit (§1c/§14a).

---

## 1a. Enhancement pass (v3.1, 2026-07-05)

A focused, scope-controlled quality pass on top of the submittable v3.0 build. Each item
was implemented plan → test → verify on the `enhance-pass` branch and committed separately.
**No working functionality was regressed and no evaluation number was fabricated.**

| # | Area | What changed | Evidence |
|---|---|---|---|
| 1 | **Answer quality** | Rewrote `GENERATE_PROMPT`: lead with one plain-language sentence, then bullet distinct facts (multiple warnings/interactions) for non-expert readability, while keeping strict grounding (only-from-chunks), per-claim `[n]` citations to the exact FDA label section, and the exact disclaimer line. | `test_prompts.py` (6 tests) locks every invariant incl. the offline-`FakeProvider` hook and `.format` placeholders |
| 2 | **Retrieval robustness** | Dense-favored **weighted RRF** (`rrf_dense_weight=1.0`, `rrf_bm25_weight=0.5`) so a lexical-only hit can't demote a strong dense hit, plus a **dense-anchor guard** — the single strongest dense hit is never dropped by fusion. Applied to both the OpenSearch primary and the Chroma fallback for parity. `_rrf_merge` stays backward-compatible (default 1.0/1.0). | `test_retrieval_robustness.py` (8 tests) prove dense-favored ordering, agreement still wins, and the dense top-1 is always retained |
| 3 | **Guardrail & refusal sharpness** | Added high-precision self-harm/misuse keyword phrases; tests prove the **LLM intent check catches paraphrased** self-harm/misuse the keyword path misses while a dosing paraphrase stays SAFE (no false positive); drug-aware grader filters a wrong-drug chunk → clean refusal. | `test_guardrail_sharpness.py` (8 tests) |
| 4 | **UI polish** | Timeline connector rail + smooth active→done transitions; terminal states (blocked/refuse/generate) get a tinted ring band; PASS evidence gets an emerald accent while FAIL is de-emphasized; PASS/FAIL summary pills; `prefers-reduced-motion` honored. All Playwright `data-testid`s preserved. | `tsc --noEmit` clean · `next build` clean |
| 5 | **Error handling & resilience** | Every agent node degrades instead of crashing: route-LLM down → attempt retrieval; rewrite down → raw question; retrieval/embed down → 0 candidates → clean refusal; grader down → chunk fails **closed**; generation down → graceful disclaimer-bearing refusal (non-streaming **and** mid-stream); top-level stream error → friendly message, raw error only in logs. | `test_resilience.py` (7 tests) incl. a full turn surviving a total LLM outage as a clean refusal |

**Backend suite: 150 tests pass offline** (`DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q`), up from 124 — the 26 additions are the five new test modules above. Frontend `tsc --noEmit` and `next build` are clean. *(The later grow pass, §13a, added corpus/eval-guard tests bringing the current total to **168**.)*

**Honestly not re-run in this pass (require the live Docker + OpenAI stack, which was not available in the enhancement environment):**
- **Playwright e2e** — all selectors/`data-testid`s were preserved, so the existing 4/4 spec should stay green, but it must be re-run against the running stack to reconfirm.
- **Live golden-set eval** — *(resolved 2026-07-06, §13a/§14).* This pass **hypothesized** the
  retrieval-robustness change (item 2) made the optimized path "≥ baseline by construction." That
  claim was **later tested and refuted**: on the grown 332-label corpus the dense-anchor guard only
  guarantees the dense top-1 stays in the *pool*, and the cross-encoder can still re-rank it out of
  top-1 — so optimized measured **below** baseline. The §14 table now holds the **re-measured
  2026-07-06** numbers with a root-cause diagnostic; no number was tuned to hide the delta.

---

## 1b. Performance pass (v3.2, 2026-07-06)

A latency-focused pass on the `perf-pass` branch, after the honest grow + re-measure showed
retrieval was **not** the lever (dense already wins; §14). Each item was implemented plan →
TDD → verify and committed separately; **no v3.1 functionality regressed and no number was
fabricated.** All latency figures are real, measured live against the grown index with
`gpt-4.1-mini` + OpenSearch.

| # | Area | What changed | Measured win | Evidence |
|---|---|---|---|---|
| 1 | **Batched grading** (drug-tagged) | Grade all reranked candidates in **one** LLM call (a JSON verdict list) instead of one call per candidate; each chunk is tagged with its **source drug** so the grader reliably rejects wrong-drug chunks. Robust parse; **degrades to per-chunk** if the batch reply is unparseable or the call errors. | **12,438 → 2,080 ms/grading step (5.98×, −10.4 s)** | `test_grade_batch.py` (12 tests): single-call grading, source-tag, malformed/short/exception → fallback, parser edge cases |
| 2 | **`grade_top_n` lever** | Config cap on how many reranked candidates are graded (0 = all; default preserves behavior) — shrinks the batch prompt. | composes with batching | covered by `test_grade_batch.py` |
| 3 | **Final-answer cache** | Cache the whole answer for an exact-repeat, stateless `(question, mode)`; streaming replays the full SSE event sequence so the UI trace renders identically on a warm hit. History-bearing follow-ups never cached. Redis/memory, short TTL, degrade-safe. | **cold ~14,079 ms → warm <1 ms** | `test_answer_cache.py` (6 tests) incl. a live `/ask-agentic` repeat served from cache |
| 4 | **Reranker baked into image** | Pre-download `BAAI/bge-reranker-base` at Docker build; `HF_HUB_OFFLINE=1` forces offline loads at runtime. | no cold HF download at demo | verified: reranker loads offline in-container and scores a pair |

**Backend suite: 220 tests pass offline** (168 v3.1/grow baseline + 12 batched-grading + 6
answer-cache + 34 metadata-scoping — §14a). **Live re-verified (2026-07-06):** Playwright **4/4** against the rebuilt stack,
and the golden-set eval re-run on the grown index (§14) — the dense-wins finding is unchanged,
confirming batched grading preserves grading behavior. Frontend `tsc --noEmit` / `next build`
clean.

**Defect found & fixed during live verification (v3.2).** The Playwright refusal test flaked:
for an out-of-corpus (fake) drug, retrieval returns real drugs' same-named sections (e.g.
`MINOXIDIL#warnings` for `zzqoflaxibogus-9000`), and the grader passed one ~50% of the time →
a **hallucinated** answer instead of a clean refusal — a genuine safety miss (the §15.3 class,
re-exposed by corpus growth changing what gets retrieved). **Root cause:** the batch grader
saw only chunk *text*, not which *drug* each chunk was from, so it couldn't apply the
drug-match rule. **Fix:** tag each batch chunk with `(drug: SOURCE)` and make the mismatch
rule explicit. Live rate went **3/6 → 5/5** refusing the fake drug; the old per-chunk path
passed the wrong chunk **6/6**, so batched grading is strictly safer here. Real-drug grading
is unaffected (the correct chunk's drug *is* the asked drug). Covered by a structural
regression test; Playwright refusal test is green again.

---

## 1c. Metadata-scoped retrieval pass (scoped-retrieval, 2026-07-07)

The one pass that went **back at the retrieval problem** §14 root-caused, instead of routing
around it. §14 proved the grow-pass regression was **cross-drug vector-search dilution** — on a
corpus where every FDA label shares identical section names, the *same section of the wrong
drug* crowds out the right one. The published fix is **metadata scoping**: restrict the candidate
set to the relevant drug(s) *before* similarity search. Implemented plan → TDD → verify on the
`scoped-retrieval` branch; **no prior functionality regressed, no number fabricated.**

| # | Area | What changed | Evidence |
|---|---|---|---|
| 1 | **Drug-tagged embeddings (SRAG)** | Each label chunk is embedded from a drug/section-**tagged** copy (`[DRUG: … \| SECTION: …]`) so the vector encodes drug identity even more explicitly, while the **stored/displayed text stays clean**. A normalized `drug_key` keyword field is added (OpenSearch + Chroma) for exact filtering. Non-label chunks embed unchanged (legacy-safe). | `test_scoped_retrieval.py` (tagged-embed/clean-store + `drug_key`) |
| 2 | **Entity resolution** | One cached `gpt-4.1-mini` step (no new provider): **NAMED** (explicit drug, brand→generic, word-boundary), **CONDITION** (symptom→candidate generics, *constrained to the indexed catalog so it can't invent*), or **NONE**. Any failure → NONE. | `test_scoping.py` (20 tests) |
| 3 | **Scoped retrieval + safe fallback** | NAMED/CONDITION restrict BM25 + kNN to `drug_key`; scoped kNN is an **exact `script_score` search** (the default OpenSearch engine rejects a filter inside the ANN clause). Rerank within scope. A scoped search returning `< scope_min_results` **auto-retries UNFILTERED** — recall provably ≥ today. Path recorded in the trace. | `test_scoped_retrieval.py` (13 tests): filter plumbing, exact scoped kNN, scoped→unfiltered fallback |
| 4 | **Surfaced scope** | A `Scope: <drug>` (or `Scope: all`) stage in the evidence-panel timeline + trace (the single frontend change). | scope-stage SSE test (`test_ask.py`) |

**Backend suite: 220 tests pass offline** (+34 vs the v3.2 186). **Live re-measured 2026-07-07**
on a freshly rebuilt drug-tagged index (four configs, §14a). **The predicted win landed on the
optimized/hybrid path:** scoping lifts optimized **Hit@1 0.80 → 0.86**, **MRR 0.837 → 0.885**,
recovering most of the hybrid path's dilution gap and making optimized-scoped the best config on
citation/refusal/answer/faithfulness. Dense Hit@k is unchanged (already strong; small faithfulness
+ refusal gains), and dense-only still leads raw Hit@1 (0.90) — all reported honestly, no
overfitting. Full four-config table + interpretation in **§14a**.

---

## 1d. UI redesign — "Monograph" (ui-redesign, 2026-07-07)

A visual + UX redesign off the AI-generic soft-green "health assistant" look into a
deliberate, subject-grounded identity: **an official FDA drug monograph rendered as a live
clinical instrument.** Followed the frontend-design skill's two-pass method (token system →
critique-vs-generic → build → self-critique); full rationale in **`docs/DESIGN.md`** and §23.
Visual only — the SSE contract, streaming, citations, evidence/trace, guardrail/refusal, and
the preserved live **Scope stage** are untouched; every `data-testid` stayed stable.

| Layer | What changed |
|---|---|
| **Identity** | Renamed **Verdant → Formulary** (a real pharmacy term) with an **℞** mark; off the soft-green palette entirely. |
| **Tokens** | Cool paper/ink neutrals + one confident **cobalt** accent + a role-restricted **cyan** "instrument-live" signal + serious amber/red; **IBM Plex Sans/Serif/Mono** via `next/font` (self-hosted); precise 4–10px radii, hairline rules, tokenized motion. |
| **Signature** | The evidence panel is now a live instrument: a numbered "retrieval assay" log (mono, cyan LED + scan), the Scope stage as a cobalt reference tag, graded chunks as `[DRUG · SECTION]` monograph citations with a serious kept/filtered verdict. |
| **Quality floor** | WCAG-AA micro-label contrast, visible keyboard focus, responsive to mobile, `prefers-reduced-motion` honored. |

**Verified:** `tsc --noEmit` + `next build` clean; all Playwright selectors intact (a live
screenshot wasn't possible — the Chrome extension is blocked from `localhost` by org policy —
so the self-critique was code-level against the passing build).

---

## 1e. Security-hardening pass (security-hardening, 2026-07-07)

Raised the stack to a strong production security posture — **threat-model-driven, every control
backed by a test that proves the attack is blocked** (no theater). Full detail + the
control→test matrix in **`docs/SECURITY.md`** and §24. Implemented plan → TDD → verify on the
`security-hardening` branch, per item; **no prior functionality regressed, SSE contract intact.**

| # | Control | Proof |
|---|---|---|
| 1 | **API-key auth** (`AUTH_ENABLED`) on all cost/mutating endpoints (401); `/health` public. **Rate limiting** per-caller+IP (Redis/memory; LLM 20 · ingest 5 · default 120 /min → 429). | `test_security_auth.py` |
| 2 | **IDOR defense**: uuid4 ids (unguessable), strict id-shape check, session/trace bound to the caller (`owner`); non-owned/unknown/malformed → **404** (no enumeration). | `test_security_idor.py` |
| 3 | **Input validation** (oversized/empty question → 422), **body-size cap** (413), **parameterized SQL** proven with a SQLi payload stored as inert data. | `test_security_input.py` |
| 4 | **XSS-safe output** (no `dangerouslySetInnerHTML`; escaped React text) + strict **CSP/headers** on Next.js *and* FastAPI. | `test_security_headers.py`, e2e inert-`<script>` test |
| 5 | **Prompt-injection hardening** in the guardrail (override/reveal-prompt/exfil/jailbreak) with false-positive guards; retrieved content is inert DATA; no eval/exec path. | `test_security_injection.py` |
| 6–9 | **Secrets** env-only + scrubbed from logs/health/errors; **CORS allowlist**; **datastores internal-only** in the prod compose (Redis password); **request-id + generic errors**; **non-root containers**; **pip-audit + npm audit CI**. | `test_security_hardening.py`, CI |

Auth + rate limiting default **OFF** for local dev/tests and are switched **ON** by
`docker-compose.prod.yml` (which also drops the datastore ports and sets HSTS). **Backend suite:
246 tests pass** (+26 security tests vs the 220 pre-pass).

---

## 1f. Production-hardening pass (production-hardening, 2026-07-07)

Closed the last gaps between "great prototype" and "live-production-ready." The auth + rate
limiting + secrets + prod-compose skeleton already landed in the security pass (§1e), so this
pass implemented **only the remaining concerns** — full detail in **`docs/DEPLOYMENT.md`** and
**`docs/OPERATIONS.md`**, consolidated in §25.

| Concern | What was added |
|---|---|
| **Frontend auth wiring** | `lib/stream.ts` sends `X-API-Key` (from `NEXT_PUBLIC_API_KEY`) on every backend call; omitted when unset so local dev is unchanged. |
| **CI/CD** | `.github/workflows/ci.yml` — a blocking `backend` job (full pytest) + `frontend` job (`tsc` + `next build`) with dep caching, plus an on-demand Playwright `e2e` job; alongside the existing `security.yml` (pip-audit + npm audit + security suite). |
| **Observability** | Structured **JSON logging** (`JSON_LOGS=1`) with a per-request access line (`request_id`/path/status/latency); a public **`/metrics`** Prometheus endpoint (requests, p50/p95 latency, answers/refusals/blocked, cache-hit ratios); documented **alert thresholds** (error/latency/cost/refusal/auth-abuse). |
| **Deployment** | Slim **Next standalone** multi-stage frontend image; `docker-compose.prod.yml` now has a **healthcheck + resource limits + restart** on every app service; **DEPLOYMENT.md** (registry build/push, single-host run, TLS proxy, first-run ingest, a Kubernetes sketch). |

**Backend suite: 250 tests pass** (+4 observability tests). No prior functionality regressed;
the SSE contract is intact.

---

## 2. Course parity map

| Course layer | Course uses | MaiStorage (this project) | Parity |
|---|---|---|---|
| Data source | arXiv API | **openFDA API** | Same pattern, swapped domain (intended) |
| Orchestrator | Airflow (daily) | **Airflow (@daily)** | ✅ exact |
| Storage | PostgreSQL + **OpenSearch** | **PostgreSQL + OpenSearch** | ✅ exact |
| Cache | Redis | **Redis** | ✅ exact |
| Retrieval | Hybrid BM25 + vectors, RRF | **Hybrid BM25 + kNN, RRF** | ✅ exact |
| Agentic layer | LangGraph (guardrail/grade/rewrite) | **LangGraph (guardrail/route/rerank/grade/decide/refuse)** | ✅ match + explicit guardrail, rerank & refusal |
| LLM | Ollama | **OpenAI gpt-4.1-mini** | Swapped provider (intended) |
| Embeddings | Jina | **OpenAI text-embedding-3-large (3072-d)** | Swapped provider (intended) |
| API | FastAPI (`/ask-agentic`, `/stream`) | **FastAPI (`/chat` SSE, `/ask-agentic`)** | ✅ exact |
| Observability | Langfuse | **Langfuse** | ✅ exact |
| Clients | Gradio + Telegram | **Next.js + TypeScript** (primary) **+ Telegram bot** | Intended swap (Next.js) + Telegram kept for multi-client parity |
| Corpus behavior | Grows daily (arXiv sync) | **Grows daily (openFDA sync)** | ✅ exact |

---

## 3. Repository structure

```
maistorage/
├── backend/                         FastAPI + LangGraph agent (Python) — single writer of the stores
│   ├── app/
│   │   ├── main.py                  App factory: routers, CORS, startup warm-up, store selection
│   │   ├── config.py                Pydantic settings (provider, models, OpenSearch/Chroma/DB/Redis/Langfuse, embed_dim, guardrail, growth)
│   │   ├── models.py                Schemas: ChatRequest, AskRequest/Response, Citation, TraceStep, ChatStageEvent, ChatEvidenceEvent…
│   │   ├── db.py                    SQLAlchemy: sessions, messages, drug labels, kv_store (growth watermark)
│   │   ├── observability.py         Langfuse Observer (lazy; no-op when keys absent)
│   │   ├── scheduler.py             APScheduler fallback: ingestion + growth jobs (off by default)
│   │   ├── agent/
│   │   │   ├── graph.py             Graph assembly + event-emitting runner (stage/evidence) + non-streaming answer
│   │   │   ├── nodes.py             guardrail / route / rewrite / retrieve / rerank / grade / decide / generate / refuse
│   │   │   ├── prompts.py           Prompts incl. GUARDRAIL_PROMPT + caring/neutral refusals + drug-aware grader
│   │   │   └── state.py             RagState TypedDict (incl. blocked/block_category/block_message)
│   │   ├── api/
│   │   │   ├── chat.py              POST /chat — SSE streaming (stage/evidence/token/done)
│   │   │   ├── ask.py               POST /ask-agentic — non-streaming (course-parity + Telegram)
│   │   │   ├── ingest.py            POST /ingest · /ingest/fda (accumulate) · /ingest/fda/grow (one growth batch)
│   │   │   ├── sessions.py · trace.py · health.py
│   │   ├── ingestion/               openfda.py (seed + growth + watermark), loader, chunker, indexer  [lazy __init__]
│   │   ├── providers/               Provider-agnostic LLM layer (openai/gemini/groq/ollama/local)
│   │   ├── retrieval/
│   │   │   ├── opensearch_store.py  PRIMARY: BM25 + knn_vector, hybrid via RRF
│   │   │   ├── vectorstore.py       FALLBACK: Chroma (used when OPENSEARCH_URL is empty)  [lazy __init__]
│   │   │   ├── hybrid.py            Chroma + rank-bm25 RRF (fallback hybrid)
│   │   │   ├── reranker.py          Cross-encoder (BAAI/bge-reranker-base; passthrough if unavailable)
│   │   │   └── cache.py             Redis (or in-memory LRU) query/retrieval cache
│   │   └── services/telegram/       Telegram bot: handlers.py (start/help/message) + bot.py (PTB Application)
│   ├── tests/                       19 test modules (unit, agent, guardrail(+sharpness), ask, growth, telegram, persistence, prompts, retrieval-robustness, resilience, e2e)
│   └── Dockerfile / pyproject.toml
├── frontend/                        Next.js + TypeScript UI (warm soft-green split view)
│   ├── components/                  Chat, EvidencePanel, StageTimeline, EvidenceChunkCard, Message, Citations, TracePanel, Disclaimer
│   ├── lib/stream.ts                SSE client: token/stage/evidence/done; /ask, /grow, /health, /sessions
│   ├── e2e/chat.spec.ts             Playwright e2e (disclaimer, streaming+citations, blocked, refusal)
│   └── playwright.config.ts / Dockerfile
├── airflow/dags/fda_ingestion_dag.py   @daily: fetch → extract → dedupe → index_and_record → grow_corpus (delegates writes to backend)
├── eval/                            Golden-set harness: run.py, metrics.py, golden.jsonl (50 Qs), reconcile_golden.py, GROW_RUNBOOK.md, last_run_*.json
├── docker-compose.yml              backend, frontend, postgres, opensearch, airflow ×3, telegram-bot
├── docker-compose.redis.yml / .langfuse.yml   optional overlays
└── docs/                           PRD.md, PROJECT_REPORT.md (this), CHANGES_V3.md, metrics.md, DEMO.md
```

---

## 4. Architecture

```
openFDA API (/drug/label.json, keyless)          [Embeddings: OpenAI text-embedding-3-large, 3072-d]
        │
   Apache Airflow DAG (@daily): fetch → extract → dedupe → index_and_record → grow_corpus
        │   (read-only fetch/dedupe in-worker; DELEGATES all writes to the backend over HTTP)
        ▼
   ┌─────────────────── FastAPI backend (single writer) ───────────────────────┐
   │  OpenSearch (BM25 + knn_vector, hybrid RRF)     PostgreSQL                  │
   │        │        [Chroma fallback when unset]    (labels, sessions,          │
   │        ▼                                          messages, growth watermark)│
   │  LangGraph agent:                                                            │
   │   guardrail → route → rewrite → retrieve → rerank → grade → decide →        │
   │              {generate | loop(≤3) | refuse}                                 │
   │        │   Redis cache on embed/retrieve    only graded chunks generate     │
   │        ▼                                                                     │
   │  /chat (SSE: stage·evidence·token·done) · /ask-agentic · /ingest[/fda[/grow]]│
   │  · /trace/{id} · /sessions · /health     every request traced to Langfuse   │
   └───────────────┬───────────────────────────────────┬─────────────────────────┘
                   ▼                                   ▼
   Next.js + TypeScript UI                       Telegram bot
   (split view · live evidence panel ·           (thin client → POST /ask-agentic)
    stages · citations · disclaimer)
```

**Central design principle: the backend is the single owner/writer of OpenSearch and
Postgres.** Airflow performs read-only fetch/dedupe and delegates all writes to the
backend over HTTP — preventing concurrent-writer races and sidestepping the Airflow↔app
dependency clash. Both clients call the identical backend; no RAG logic lives in a client.

---

## 5. End-to-end request flow

A single `POST /chat` (`{question, optimized, session_id}`):

1. **Load memory** (`api/chat.py`): last-N messages from Postgres (`memory_window=6`); persist the user message. Failures degrade to no memory.
2. **Drive the agent, streaming events** (`graph.py::run_agent_streaming` over `_run_agent_events`), emitting live **`stage`** events (safety → route → search → grade → decide) and one **`evidence`** event (graded candidates with PASS/FAIL) so the UI animates in real time.
3. **Contextualize** follow-ups (coreference resolution) when history exists.
4. **Terminal:** if **blocked** → stream the guardrail's tone-appropriate refusal + a `blocked` stage; if **refuse** → stream the standard refusal + a `refuse` stage; if **generate** → emit a `generate` stage, then **stream the grounded answer token-by-token**, extract + validate citations, persist trace, log Langfuse spans, and emit `done` with `refused`/`blocked` flags.
5. **Persist** the assistant message (answer + citations + trace_id).

**SSE contract:** `stage` / `evidence` (additive) · `token`* · `done{citations, trace_id, refused, blocked}` · `error`.

---

## 6. The agentic loop (with safety guardrail)

**Nodes** (`nodes.py`) and edges (`graph.py`):

| Node | Behavior | Edge out |
|---|---|---|
| **guardrail** (first) | Hybrid keyword fast-path + small `gpt-4.1-mini` intent check; degrades to keyword verdict on LLM failure. Categories: SELFHARM / MISUSE / ADVICE / SAFE | blocked → refuse, else → route |
| **route** | LLM: does this need retrieval, or is it off-domain chit-chat? | needs_retrieval → rewrite, else → refuse |
| **rewrite** | LLM sharpens the query (keeps drug names + topic); different angle on retries | → retrieve |
| **retrieve** | OpenSearch hybrid (BM25+kNN RRF) when active, else Chroma. `top_k=8`. Query embedding cached | → rerank |
| **rerank** | Cross-encoder reorders; keep `rerank_top_n=4` (passthrough if model unavailable) | → grade |
| **grade** | LLM grades **each** chunk YES/NO — **drug-aware**: a chunk about a *different* drug is not relevant unless the question is about an interaction | → decide |
| **decide** | graded>0 → generate; else iterations≥3 → refuse; else loop to rewrite | conditional |
| **generate** | Answer strictly from numbered graded chunks, cite every sentence, append disclaimer | → END |
| **refuse** | Guardrail block → caring/neutral message; unanswerable → standard refusal; `citations=[]` | → END |

**Guardrail refusal tones:** self-harm/overdose → a **caring** message pointing to a
doctor/pharmacist/988; misuse/injection/personalized-advice → a **neutral** decline. The
disclaimer is always present. A blocked question **never reaches retrieval** (verified
live and in `test_guardrail.py`).

**Hard guarantees:** iteration cap = 3; only graded chunks reach generation; empty graded
set ⇒ refusal; every step appended to `trace` and served at `/trace/{id}`. Citation
validation (`_extract_citations`) drops any `[n]` marker not backed by a graded chunk.

---

## 7. Retrieval subsystem (OpenSearch + fallback)

- **Primary — OpenSearch** (`opensearch_store.py`): each chunk is indexed once with a
  BM25-analyzed `text` field and a `knn_vector` `embedding` field (dimension =
  `embed_dim=3072`). **Optimized** mode runs a BM25 query + a kNN query and merges them
  with **Reciprocal Rank Fusion**; **baseline** mode is kNN-only. Active whenever
  `OPENSEARCH_URL` is set **and** the cluster is reachable (probed once).
- **Fallback — Chroma + rank-bm25**: used when OpenSearch is not configured. Keeps the
  offline test suite green with zero external services and preserves a revert path.
- **Rerank:** cross-encoder `BAAI/bge-reranker-base`, degrades to passthrough if the model
  can't load.
- **Metadata scoping** (`scoping.py`, `ENABLE_SCOPING`): before retrieval, a cached
  `gpt-4.1-mini` entity resolver maps the question to the drug(s) it's about (NAMED /
  CONDITION / NONE); NAMED/CONDITION restrict BM25 + kNN to those drugs via a `drug_key`
  filter (scoped kNN is an exact `script_score` search), removing the same-section wrong-drug
  hard negatives that dilute a homogeneous corpus. A scoped search returning too few hits
  **auto-retries unfiltered**, so recall is never worse than unscoped. Chunks are embedded
  from a drug/section-**tagged** copy so the vector encodes drug identity. Measured live to
  lift the optimized path (Hit@1 0.80 → 0.86) — see §1c/§14a.
- **Which mode is actually better?** Both are selectable and measured honestly. On the grown
  FDA corpus, **dense-only (baseline) beats hybrid+rerank** because every label shares
  identical section names — see the §14 measurement + root-cause. Metadata scoping (§14a)
  recovers most of the hybrid path's loss but dense-only still leads raw Hit@1; the hybrid
  path is kept for heterogeneous corpora where lexical + dense are complementary.
- **Cache** (`cache.py`): **Redis** when `REDIS_URL` is set (shared, survives restarts),
  else in-memory LRU; a Redis outage degrades to memory. Caches query embeddings +
  retrieval results (TTL `cache_ttl_seconds=3600`); stats + active backend on `/health`.

The selection is transparent to the agent: `retrieve_node` picks OpenSearch when active,
otherwise the Chroma path — identical candidate dicts downstream.

---

## 8. Data, ingestion & continuous growth

**Source:** openFDA `GET /drug/label.json` — keyless, throttled at 0.3 s. Label prose
sections chunk and retrieve well.

**Seed set:** a curated evergreen list of ~317 common drug names (24-drug demo core preserved
for a stable golden set) → **332 labels → 3,054 section chunks** indexed (3072-d) after the
grow pass (`eval/GROW_RUNBOOK.md`). The original 24-drug/23-label/240-chunk seed was the v3.0
demo baseline; the corpus was then grown ~14× to stress retrieval honestly.
**Extracted sections:** boxed_warning, indications_and_usage, dosage_and_administration,
warnings, warnings_and_cautions, contraindications, adverse_reactions, drug_interactions.

**Pipeline** (`run_fda_ingestion`): fetch → parse sections → **dedupe by stable
`label_id`** → **structure-aware chunk** (~512 tok, ~64 overlap; split on headings) →
**embed** (`text-embedding-3-large`) → **upsert into OpenSearch** with deterministic chunk
ids → record label metadata in Postgres.

**Continuous growth** (course parity: daily sync). `run_fda_growth()` fetches the next
page of newest labels (`sort=effective_time:desc` + a `skip` cursor persisted in the
`kv_store` table), dedupes by `label_id`, indexes the fresh ones, and advances the
watermark — **additive + idempotent**, and it keeps growing even on quiet days (paging
fallback). Exposed as `POST /ingest/fda/grow` and driven by the Airflow `grow_corpus`
task (and the APScheduler fallback). **Verified live:** growth batches are additive and
idempotent (an early batch added 5 labels / 31 chunks and advanced the watermark); running
the seed+growth path to completion took the corpus from the 240-chunk demo seed to the
**3,054-chunk / 332-label** index the §14 metrics were re-measured against.

---

## 9. Clients: Next.js web UI + Telegram bot

**Next.js + TypeScript web UI (primary).** A warm, soft-green **split view**: left =
streaming conversation with tappable inline `[n]` **citation chips**; right = the
signature **live evidence panel** — an **animated stage timeline** (Safety check → Route →
Search → Grade → Decide, with distinct terminal states: teal *Writing answer*, amber
*declined*, red *Safety check → blocked*) that settles into the **graded chunks** (drug +
section + **PASS/FAIL** badge + snippet + FDA link). Clicking a citation highlights and
scrolls to its chunk (matched by `chunk_id`). A live corpus indicator reads the count
from `/health` ("N label chunks · growing daily"); light + dark themes; the medical
disclaimer is always visible. The SSE client (`lib/stream.ts`) consumes the additive
`stage`/`evidence` events.

**Telegram bot (secondary, course-faithful).** `services/telegram/` mirrors the course's
Week-7 structure: command handlers (`/start`, `/help`) + message processing that forwards
a question to the backend **`/ask-agentic`** endpoint and replies with the cited answer +
disclaimer. Async + graceful failure on backend error. Configured via `TELEGRAM__BOT_TOKEN`
(course naming). **Degrades safely:** with no token the bot logs and exits cleanly
(verified live: container exit code 0), leaving the rest of the stack unaffected. No RAG
logic lives in the bot — proving the backend is client-agnostic.

---

## 10. Persistence, memory & observability

**PostgreSQL** (SQLAlchemy; SQLite fallback for tests): `DrugLabel(label_id UNIQUE, …)`,
`ChatSession`, `Message(role, content, citations JSON, trace_id, …)`, and `KV` (growth
watermark/cursor). **Memory:** `/chat` with a `session_id` loads the last 6 messages, which
feed both contextualization (coreference) and the generation prompt.

**Langfuse** (`observability.py`): a lazy Observer emits one span per agent node plus a
generation span (chunk ids, token counts, estimated cost, latency, model). If the keys are
absent, **every tracing call is a no-op** — verified: the app runs cleanly with Langfuse
off, no errors.

---

## 11. API reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Provider, models, **embed_dim**, active **store** (opensearch/chroma) + doc count, cache backend + hit/miss |
| POST | `/chat` | Stream the agentic answer over SSE (stage · evidence · token · done) |
| POST | `/ask-agentic` | Non-streaming agentic answer `{answer, citations, trace_id, refused, blocked}` |
| POST | `/ingest` | Rebuild the index from the local corpus |
| POST | `/ingest/fda` | Fetch openFDA labels and **accumulate** into the index (deduped) |
| POST | `/ingest/fda/grow` | One **continuous-growth** batch (newest labels beyond the watermark) |
| GET | `/trace/{id}` | Per-request decision trace |
| POST | `/sessions` · GET `/sessions/{id}/messages` | Chat session + history |

---

## 12. Test strategy & results

**255 backend tests pass** offline
(`cd backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q`) — up from 220
(scoped-retrieval), 186 (v3.2), 168 (grow pass), 150 (v3.1), 124 (v3.0), 99 (v2.0). The
scoped-retrieval pass added `test_scoping` (20) + `test_scoped_retrieval` (13) + a scope-stage
SSE test; the **security-hardening pass (§24)** added **26 tests** across `test_security_auth`
(5), `test_security_idor` (4), `test_security_input` (4), `test_security_headers` (2),
`test_security_injection` (6), `test_security_hardening` (5); the **production-hardening pass
(§25)** added `test_metrics` (4: public Prometheus `/metrics`, counters increment, refusal
recorded, JSON log formatter). **Playwright e2e: 6/6** against the live UI (the redesign added an
inert-`<script>` XSS test; §1d/§24).

| Level | Coverage | Files |
|---|---|---|
| Unit | openFDA fetch/parse/dedupe, chunking, indexer, cache, RRF merge | `test_openfda`, `test_chunker`, `test_indexer`, `test_cache`, `test_growth` |
| Safety guardrail | keyword + LLM blocks, legit-dose passes (no false positive), tone-appropriate refusals, LLM-fail degrades, **blocked never retrieves** | `test_guardrail` |
| Agent | routing, grading, refusal, iteration cap, citation validation, memory coreference | `test_agent` |
| Endpoints | `/ask-agentic`, SSE **stage/evidence/refuse/generate** events, blocked flag | `test_ask`, `test_http` |
| Growth | watermark advance + dedupe across runs, empty-page survival | `test_growth` |
| Telegram | forward to `/ask-agentic`, graceful backend-error, source dedupe, safe-disable | `test_telegram` |
| Persistence / Observability / Scheduler | labels + sessions/memory, Langfuse spans + no-op, APScheduler jobs | `test_db`, `test_sessions`, `test_observability`, `test_scheduler` |
| E2E | question → cited answer, refusal, streaming deltas, hybrid mode | `test_e2e`, `test_citations` |
| Browser e2e (Playwright) | disclaimer visible, streaming + citation→chunk highlight + evidence stages, guardrail block state, unanswerable refusal state | `frontend/e2e/chat.spec.ts` |
| **Answer-prompt invariants (v3.1)** | grounding, `[n]` citations, exact disclaimer, non-expert structure, FakeProvider hook, `.format` placeholders | `test_prompts.py` |
| **Retrieval robustness (v3.1)** | dense-favored weighted RRF, agreement still wins, dense-anchor keeps the strongest dense hit | `test_retrieval_robustness.py` |
| **Guardrail sharpness (v3.1)** | LLM catches paraphrased self-harm/misuse, dosing paraphrase stays SAFE, drug-aware grader filters wrong-drug | `test_guardrail_sharpness.py` |
| **Resilience (v3.1)** | route/rewrite/retrieve/grade/generate all degrade on outage; full turn survives total LLM outage as a clean refusal | `test_resilience.py` |
| **Metadata scoping (§14a)** | drug tagging (embed-tagged/store-clean + `drug_key`), entity resolution (NAMED, brand→generic, word-boundary, CONDITION-constrained + degrade-safe), OpenSearch `terms` filter plumbing, scoped→unfiltered fallback, scope SSE stage, **growth-safe dynamic catalog** (TTL + bust-on-ingest) | `test_scoping.py`, `test_scoped_retrieval.py`, `test_ask.py`, `test_dynamic_catalog.py` |
| **Security (§24)** | auth 401 / rate-limit 429 / public health; IDOR (cross-caller session+trace → 404, malformed id → 404); input caps (422/413) + SQLi-as-data; security headers + CSP; prompt-injection blocked + poisoned-chunk inert + no-exec; request-id/no-leak, CORS allowlist, telegram key | `test_security_auth`, `test_security_idor`, `test_security_input`, `test_security_headers`, `test_security_injection`, `test_security_hardening` |
| **Observability (§25)** | public Prometheus `/metrics`, request counters increment, refusal recorded, JSON log formatter emits valid JSON | `test_metrics.py` |

---

## 13. Live full-stack verification (2026-07-04)

Every row executed against a running `docker compose` stack (backend, frontend,
OpenSearch, Postgres, Redis, Airflow ×3, telegram-bot).

| What | Result |
|---|---|
| `docker compose up --build` (all services) | ✅ OpenSearch healthy, backend/frontend/redis/postgres up |
| `/health` | ✅ `store=opensearch`, `embed=text-embedding-3-large` (3072), `cache=redis` |
| `/ingest/fda` (3072-d into OpenSearch) | ✅ 23 labels / **240 chunks** indexed |
| Streaming chat (answerable) | ✅ stages safety→route→search→grade→decide→generate; evidence 4 cands / 3 PASS; answer from `IBUPROFEN#warnings`; citation `[1]` with source URL |
| Multi-hop interaction (warfarin+aspirin) | ✅ faithful answer, 2 citations |
| **Guardrail block** (self-harm) | ✅ stages **safety→blocked**; caring refusal; `refused=blocked=true`; **retrieval never ran** |
| **Unanswerable refusal** (pembrolizumab) | ✅ **0 PASS → clean refuse path**; `refused=true`, 0 citations; `refuse` stage emitted |
| `/ask-agentic` (non-streaming) | ✅ 200; amoxicillin answer with 1 citation |
| `/ingest/fda/grow` | ✅ +5 labels / +31 chunks; watermark advanced |
| `/trace/{id}` | ✅ `guardrail → route → rewrite → retrieve → rerank → grade → decide → generate` |
| Redis cache | ✅ `cache_backend=redis`; cold **1905 ms** → warm **0.78 ms** retrieval |
| **Airflow DAG** (manual trigger) | ✅ run **SUCCESS**; all 5 tasks (fetch/extract/dedupe/index_and_record/grow_corpus) |
| Telegram bot (no token) | ✅ graceful **exit 0**, "disabled" log, stack unaffected |
| Langfuse off | ✅ graceful no-op, no errors |
| Eval baseline / optimized | ✅ ran against OpenSearch + 3-large (see §14) |
| **Playwright e2e** | ✅ **4/4 passed** (disclaimer, streaming+citations, blocked, refusal) |
| Backend tests | ✅ **124 passed** |
| Frontend | ✅ `tsc --noEmit` + `next build` clean; served HTTP 200 |

---

## 13a. Grow + re-measure verification (2026-07-06)

The `GROW_AND_REMEASURE` runbook (`eval/GROW_RUNBOOK.md`) was executed end-to-end against a
live stack (OpenSearch + backend, OpenAI key set), and the whole suite was re-run to confirm
nothing regressed. This is the state the §14 numbers reflect.

| What | Result |
|---|---|
| Grow index (`SEED_DRUGS` ~317 names → openFDA) | ✅ **332 labels / 3,054 chunks** in OpenSearch (`/health` `store.documents=3054`) |
| Golden set expanded + reconciled to indexed generics | ✅ **50 questions** (39 single-hop, 6 multi-hop, 5 refusal); every `expected_source` resolves to an indexed label (0 dangling) |
| `eval/run.py --mode baseline` (grown index) | ✅ 50/50; Hit@1 **0.800**, MRR **0.812** (§14) |
| `eval/run.py --mode optimized` (grown index) | ✅ 50/50; Hit@1 **0.720**, MRR **0.750** — **below** baseline; root-caused + reported honestly (§14) |
| RRF/rerank sanity check (permitted tuning) | ✅ swept `rrf_bm25_weight` 0.5→0.25→0.0; reranked Hit@1 flat at 0.689 — no knob recovers it; **defaults unchanged, no overfitting** |
| Backend tests | ✅ **168 passed** (`DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 pytest -q`) |
| Frontend | ✅ `tsc --noEmit` clean · `next build` clean (4/4 static pages) |
| **Playwright e2e** | ✅ **4/4 passed** against the running stack (disclaimer, streaming+citations, blocked, refusal) |

**One flaw surfaced during testing, diagnosed, not a regression:** the Playwright citations
test first failed by timeout while the 50-question optimized eval was concurrently saturating
the OpenAI `gpt-4.1-mini` endpoint (the streamed turn exceeded the 90 s test timeout). Re-run
without the eval contention, it passed in 26.9 s — the failure was resource contention, not a
UI/backend defect. No code change was needed.

---

## 14. Metrics (real, reproducible)

Generation **`gpt-4.1-mini`**, embeddings **`text-embedding-3-large` (3072-d)**, store
**OpenSearch** (BM25 + kNN). Corpus **grown to 332 FDA labels / 3,054 section chunks**
(from the 24-drug seed; see `eval/GROW_RUNBOOK.md`). Golden set = `eval/golden.jsonl`
(**50 questions**: 39 answerable single-hop, 6 multi-hop across two drugs, 5
unanswerable/refusal). Re-measured live on **2026-07-06** on the grown index (numbers below
are the **v3.2** re-run with batched grading; the earlier grow-pass run agreed within
one-question LLM noise, so the finding is robust across two independent measurements).

| Metric | Baseline (dense kNN) | Optimized (hybrid + rerank) | Δ |
|---|---:|---:|---:|
| Hit@1 | **0.800** | 0.720 | −0.080 |
| Hit@3 | **0.820** | 0.780 | −0.040 |
| Hit@5 | **0.840** | 0.780 | −0.060 |
| MRR | **0.812** | 0.750 | −0.062 |
| Citation accuracy | 0.840 | 0.840 | 0.000 |
| Refusal correctness | **0.920** | 0.900 | −0.020 |
| Answer match | 0.920 | 0.920 | 0.000 |
| Faithfulness (LLM judge) | **0.951** (n=41) | 0.950 (n=40) | −0.001 |

**Honest interpretation — the optimized path does not beat dense-only on the grown corpus,
and we report it truthfully.** Baseline clearly leads on Hit@1/Hit@3/Hit@5/MRR/refusal and
ties on citation/answer/faithfulness — dense is at least as good on every metric, and clearly
better on ranking (Hit@1 0.800 vs 0.720). (These are the v3.2 numbers with the hardened
batch grader, which lifted baseline Hit@1 from the earlier 0.74 run by keeping the correct
drug's chunk in the graded set more reliably; the dense-wins conclusion is unchanged across
all three re-runs.) The v3.0 note above (small 23-label corpus)
predicted the hybrid+rerank stack would "pay off on a larger, noisier corpus." **Growing to
332 labels and re-measuring refuted that prediction** — a good example of measuring instead
of assuming. (Both the grow pass and the v3.2 re-run land within ±1 question of each other.)

A retrieval-only diagnostic (raw Hit@k over the 45 answerable questions, no LLM grading)
pinpoints why, isolating each stage:

| Retrieval config | Hit@1 | Hit@3 |
|---|---:|---:|
| Dense-only (baseline) | **0.778** | **0.867** |
| Hybrid RRF, no rerank | 0.667 | 0.778 |
| Hybrid RRF + cross-encoder rerank | 0.689 | 0.800 |

Two independent effects each drag retrieval **below** dense-only: **(1)** every FDA label
shares the *same* section names, so on 332 drugs a BM25 hit on a section keyword pulls the
**same section of the wrong drug** into the top ranks (`MINOCYCLINE#contraindications`
crowding out `DOXYCYCLINE#contraindications`); dense embeddings encode drug identity and
avoid this. **(2)** the general-domain cross-encoder (`bge-reranker-base`) re-scores the
fused pool but doesn't reliably prefer the correct *drug's* section, recovering only part
of the loss (0.667 → 0.689), never back to dense's 0.778.

**The permitted RRF/rerank sanity check does not recover it.** Sweeping `rrf_bm25_weight`
0.5 → 0.25 → 0.0 leaves reranked Hit@1 **flat at 0.689** (the cross-encoder re-scores from
scratch, so RRF weights don't move its top-1); `rerank_top_n` can't change Hit@1 either.
Per the runbook honesty rule, **no golden-set-overfitting tuning was applied** and
retrieval defaults were left unchanged. This also corrects the §1a item-2 claim that the
optimized path is "≥ baseline by construction": the dense-anchor guard guarantees the
dense top-1 stays in the *pool*, but the cross-encoder can still re-rank it out of top-1 —
so the guarantee holds for pool membership, not for final rank.

**Takeaway.** For this corpus (many drugs, identical section vocabulary, section-targeted
questions) a strong dense retriever (3-large, 3072-d) is the right tool; lexical fusion +
a general reranker *add noise*. The hybrid+rerank stack is retained as a selectable mode —
it pays off on heterogeneous corpora where exact-match tokens (codes, rare terms) and dense
semantics are complementary — but dense-only is the honest default here. Faithfulness stays
high in both modes (0.951 / 0.950): answers are grounded in graded chunks or the agent refuses.

**Performance (v3.2 latency pass — the real headline wins).** Three independent, measured
latency reductions (full detail + tables in `docs/metrics.md` and §18):

- **Batched grading — 5.98×.** One LLM call grades all reranked candidates instead of one
  per candidate: **~12,438 → ~2,080 ms** per grading step (**−10.4 s**, avg 4 candidates over
  8 golden questions). Drug-aware logic unchanged; degrades to per-chunk if the batch reply
  can't be parsed. This is the biggest per-turn win and applies to every answered question.
- **Final-answer cache.** An exact-repeat, stateless question returns the whole answer from
  cache: **cold ~14,079 ms → warm <1 ms**. Never serves history-bearing follow-ups.
- **Retrieval-step cache (item 7).** Repeated retrieval: **cold ~1,905 ms → warm ~0.78 ms**.

All caches are Redis-when-configured, memory otherwise, and degrade without breaking a
request; embedding- and answer-cache hit/miss are on `/health`. The reranker is baked into
the image and loaded offline (`HF_HUB_OFFLINE=1`) so optimized mode never cold-starts a
download at demo time.

Raw results: `eval/last_run_baseline.json`, `eval/last_run_optimized.json`.

## 14a. Metadata-scoped retrieval (scoped-retrieval branch)

**The §14 diagnostic named the disease; this pass applies the textbook cure.** The measured
root cause of the grow-pass regression is **cross-drug confusion** on a homogeneous corpus:
every FDA label shares identical section names, so the *same section of the wrong drug*
crowds out the right one (`MINOCYCLINE#contraindications` vs `DOXYCYCLINE#contraindications`).
This is **vector-search dilution**, and the published fix is **metadata scoping** — restrict
the candidate set to the relevant drug(s) *before* the similarity search rather than hoping
the ranker untangles them after. (Wyoming DOT retrieval study: P@10 **0.77 → 0.86** with
metadata pre-filtering; the pattern recurs across RAG literature — e.g. Anthropic's
*Contextual Retrieval*, which prepends chunk-level context before embedding.)

**What was built (all backend Python except one small Next.js touch):**

1. **Drug-tagged embeddings + structured fields (SRAG).** Each label chunk is embedded from a
   drug/section-**tagged** copy of its text (`"[DRUG: doxycycline | SECTION: contraindications]
   …"`) so the vector encodes drug identity even more explicitly, while the **stored/displayed
   text stays clean** (citations + evidence panel unchanged). A normalized `drug_key` keyword
   field is added to OpenSearch (and Chroma metadata) for exact filtering. Non-label corpora
   (no `drug_name`) embed unchanged — legacy-safe.
2. **Entity resolution** (`app/retrieval/scoping.py`) — one cheap, **cached** `gpt-4.1-mini`
   step, no new provider: **NAMED** (explicit drug, brand→generic, word-boundary match against
   the indexed catalog), **CONDITION** (symptom→candidate generics, *constrained to the indexed
   catalog so it can't invent a drug*), or **NONE**. Any failure → NONE.

   **Growth-safe catalog (dynamic-catalog, 2026-07-07).** The CONDITION path constrains the LLM
   to drugs that exist *right now*, so the catalog is read from the **live `drug_labels` store**,
   not a hardcoded or startup-frozen list: it auto-refreshes on a short TTL
   (`drug_catalog_ttl_seconds`, default 600s) and is **busted immediately when `/ingest/fda[/grow]`
   records new labels** (a version counter also keys the scope-result cache, so growth orphans
   stale scopes). Net: a drug added by the daily Airflow growth job becomes scopable within
   minutes with **no restart** — scoping stays correct as the corpus grows. Still degrade-safe (a
   catalog-fetch failure → NONE). Covered by `test_dynamic_catalog.py` (5 tests: growth-safety,
   TTL refresh, NAMED unchanged, fetch-failure→NONE, version bump).
3. **Scoped retrieval + safety fallback** — NAMED/CONDITION restrict BM25 + kNN with a
   `terms` filter on `drug_key`, then rerank *within* the scoped set. If a scoped search
   returns fewer than `scope_min_results` (or the drug isn't indexed) it **auto-retries
   UNFILTERED**, so recall is provably **≥ today**. The path that ran (`scoped` /
   `unfiltered(scoped-too-few)`) is recorded in the trace.
4. **Surfaced scope** — a `Scope: <drug>` (or `Scope: all`) stage in the evidence-panel
   timeline + the agent trace (the single frontend change).

**Honest expectation (set before building, per the task).** The §14 diagnostic already shows
dense-only *largely* avoids cross-drug confusion (3-large encodes drug identity), and v3.2's
drug-tagged batch grader already rejects wrong-drug chunks. So scoping should **most help the
optimized/hybrid path** — removing the BM25 wrong-drug crowding that pulls it below dense —
plausibly bringing **optimized ≥ dense** (fixing the "optimization underperforms" story),
with a **smaller** dense lift. A modest, defensible gain is the expected outcome; a small gain
is itself an honest result.

**Re-measure — four configs, to isolate scoping's effect** (`use_scoping` is an explicit eval
lever so nothing else moves):

```bash
# live stack up, OPENAI_API_KEY set, FDA index REBUILT so chunks carry drug_key
#   (POST /ingest/fda — required: the tag + drug_key are index-time)
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large python -m eval.run --mode baseline  --no-scoping   # dense-unscoped
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large python -m eval.run --mode baseline  --scoped       # dense-scoped
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large python -m eval.run --mode optimized --no-scoping   # optimized-unscoped
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large python -m eval.run --mode optimized --scoped       # optimized-scoped
```

**Real results — live re-measure, 2026-07-07.** Four configs on the 50-Q golden set against a
freshly-rebuilt drug-tagged index (**312 labels / 2,935 chunks**, seed-only so all four configs
share the exact same corpus; real `gpt-4.1-mini` + `text-embedding-3-large` + OpenSearch). In
both scoped runs, **31 of 50** questions actually took the scoped path (25 NAMED + 6 CONDITION),
16 resolved to NONE (unfiltered, unchanged), 3 were refusals.

> **Compare rows within this table, not against §14.** This index is seed-only (312 labels), so
> it carries **less growth-noise dilution** than §14's 332-label grown corpus — which is why
> dense-unscoped here reads Hit@1 0.90 vs §14's 0.80. The four configs are all measured on this
> one index, so their *relative* deltas (the scoping effect) are valid; the absolute numbers are
> not directly comparable to §14. A future run can rebuild the full 332-label grown index (seed +
> growth batches) and re-measure all four for cross-comparability.

| Config | Hit@1 | Hit@3 | Hit@5 | MRR | Citation | Refusal | Answer | Faithfulness |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense · unscoped | **0.90** | 0.92 | 0.92 | **0.910** | 0.90 | 0.98 | 0.90 | 0.955 |
| dense · scoped | **0.90** | 0.92 | 0.92 | 0.907 | 0.90 | **1.00** | 0.92 | **0.978** |
| optimized · unscoped | 0.80 | 0.88 | 0.88 | 0.837 | 0.85 | 0.94 | 0.92 | 0.976 |
| optimized · scoped | 0.86 | 0.90 | **0.92** | 0.885 | **0.91** | **1.00** | **0.96** | **0.978** |

**The predicted win landed where predicted — on the optimized/hybrid path.** Scoping lifts
optimized **Hit@1 0.80 → 0.86 (+0.06)**, **Hit@3 0.88 → 0.90**, **Hit@5 0.88 → 0.92**,
**MRR 0.837 → 0.885 (+0.048)**, citation 0.85 → 0.91, refusal 0.94 → 1.00, answer-match
0.92 → 0.96 — recovering ~60% of the hybrid path's dilution gap to dense and making
optimized-scoped **the best config on citation, refusal, answer-match, and faithfulness**, tied
with dense on Hit@5. This is exactly the mechanism §14 root-caused: the scoped `drug_key` filter
removes the same-section wrong-drug hard negatives that BM25 fusion was pulling into the pool
(live proof: a scoped *"warnings for ibuprofen"* returns only IBUPROFEN's 4 chunks; unscoped
returns a 6-drug NSAID mix — ASPIRIN, INDOMETHACIN, NABUMETONE, NAPROXEN, SULINDAC).

**Honest limits — reported, not tuned away.** (1) **Optimized-scoped (Hit@1 0.86) still trails
dense-only (0.90)** — scoping closes most of the gap (−0.10 → −0.04) but the general-domain
cross-encoder still mis-ranks top-1 within a few scoped sets, so it does not fully overtake
dense on Hit@1. It *does* pass dense on Hit@5/citation/refusal/answer/faithfulness. (2)
**Scoping does not raise the dense baseline's Hit@k** (0.90 → 0.90) — precisely the pre-stated
expectation: 3-large already encodes drug identity, so dense had little cross-drug confusion to
remove. Its measurable dense gains are **faithfulness 0.955 → 0.978** and **refusal 0.98 → 1.00**
(scoping keeps a wrong-drug chunk out of the graded set on the hardest cases). **Net:** dense-only
remains the single best retriever for raw Hit@1 on this corpus, and metadata scoping is a real,
defensible fix for the *optimization-underperforms* story — it makes the hybrid path competitive
and gives dense a small grounding lift — without any golden-set-overfitting tuning.

Raw results: `eval/scoped_eval_2026-07-07/{dense_unscoped,dense_scoped,optimized_unscoped,optimized_scoped}.json`
(kept separate from §14's `last_run_*.json` so the 332-corpus record stays intact).

The implementation is covered by **34 new offline tests** (entity resolution incl.
brand→generic and word-boundary; CONDITION constrained to the catalog + degrade-safe; the
OpenSearch drug filter incl. the exact-`script_score` scoped kNN; the scoped→unfiltered
fallback; tagged-embed/clean-store indexing; the scope SSE stage) — see §12. Toggle the whole
feature with `ENABLE_SCOPING=0`.

---

## 15. Defects found & fixed during verification

All five were real defects only the live run surfaced; each is fixed and (where
applicable) covered by a new test.

**15.1 `.env` inline comments broke docker `env_file`.** Docker's `env_file` does not
strip inline `#` comments, so `OPENSEARCH_URL=  # comment` loaded the comment *as the
value* — the backend silently fell back to Chroma. **Fix:** cleaned `.env` (bare values)
and set `OPENSEARCH_URL` directly in `docker-compose.yml` for the backend service.

**15.2 Store-switch left the new index empty.** Postgres `drug_labels` (persisted from the
v2.0 Chroma build) marked all seed labels "known", so `/ingest/fda` deduped them and the
fresh OpenSearch index stayed empty. **Fix:** cleared the label registry so ingestion
repopulated OpenSearch; documented that the store and its dedupe registry must be reset
together when switching stores.

**15.3 Drug-blind grader produced a soft refusal.** For "dosage for pembrolizumab" (not in
corpus), the grader passed *other* drugs' dosage chunks (topic match), so the agent went to
`generate` and emitted an in-text refusal with `refused=false`. **Fix:** made `GRADE_PROMPT`
**drug-aware** (a chunk about a different drug is not relevant unless the question is about
an interaction). Re-verified live: pembrolizumab now yields 0 PASS → the **clean refuse
path** (`refused=true`).

**15.4 Missing terminal SSE stages.** The unanswerable-refuse and generate outcomes emitted
no `stage` event, so the UI's `terminal-refuse` node never lit — caught by Playwright.
**Fix:** emit `refuse` and `generate` stage events in the streaming path; added regression
tests (`test_chat_unanswerable_emits_refuse_stage`, `test_chat_generate_emits_generate_stage`).

**15.5 Eager `__init__` broke the read-only Airflow worker.** `app.ingestion.__init__`
eagerly imported `indexer → vectorstore → chromadb`, so even a read-only fetch task failed
with `ModuleNotFoundError: chromadb`. **Fix:** made `app.ingestion` and `app.retrieval`
`__init__` **lazy** (PEP 562 `__getattr__`) so the read-only worker never needs a store
driver; dropped chromadb from Airflow's pip. Re-verified: the DAG run is **SUCCESS**.

---

## 16. Assessment Q1 alignment audit

**Required**

| Req | Status | Evidence |
|---|---|---|
| 1. Agentic RAG retrieves correctly (measured) | ✅ Met | `agent/graph.py`,`nodes.py`; live Hit@1 0.882, Hit@3 0.941, MRR 0.912 |
| 2. Working prototype / demo | ✅ Met | Next.js split-view UI streams via SSE; Playwright e2e 4/4 live |
| 3. Discussion of flow | ✅ Met | PRD §2–4, this report §4–8, `/trace/{id}` |
| 4. Investigation of the system | ✅ Met | trace endpoint + Langfuse spans + live evidence panel |
| 5. Traditional vs agentic RAG | ✅ Met | §20; embodied in guardrail/grade/re-retrieve/refuse |
| 6. Open-source libraries | ✅ Met | LangGraph, OpenSearch, rank-bm25, sentence-transformers, FastAPI, SQLAlchemy, Airflow, Redis, Langfuse, python-telegram-bot, Playwright |
| 7. Test cases explained | ✅ Met | 150 backend tests + 4 Playwright e2e (§12) |

**Bonus**

| Req | Status | Evidence |
|---|---|---|
| B1. Citations | ✅ Met | `_extract_citations` validates markers vs graded chunk ids; live citations with source URLs; clickable + chunk-highlight in UI |
| B2. Optimized retrieval | ✅ Met | Hybrid (BM25+kNN RRF) + cross-encoder rerank measured before/after; Redis cold/warm 1905→0.78 ms; saturation stated honestly |

**Production layers:** OpenSearch primary store ✅ · Airflow **@daily** DAG runs + dedupes +
grows ✅ · Postgres persists labels + memory + watermark ✅ · Redis cache hits ✅ · Langfuse
traces + graceful-off ✅ · Telegram second client ✅.

**Verdict: Yes — ready to submit for Question 1.**

---

## 17. PRD coverage & the approach settled on

Is everything in `docs/PRD.md` (v3.0) included? **Yes — every functional requirement,
milestone, API, client feature, and acceptance criterion is implemented and verified
live.** The tables below map each PRD item to its status, where it lives, and — crucially —
**the approach I settled on** (including deliberate deviations and their rationale).

### 17.1 Functional requirements (PRD §5)

| ID | Requirement | Status | How it was settled / where |
|---|---|---|---|
| FR-1 | Ingest openFDA → OpenSearch, dedupe by label_id | ✅ Done | `ingestion/openfda.py` + `retrieval/opensearch_store.py`; deterministic chunk ids + `label_id` dedupe (two layers) |
| FR-2 | NL question via Next.js **and** Telegram | ✅ Done | `frontend/` + `services/telegram/`; both call the same backend |
| FR-3 | Agentic loop retrieves correct sections | ✅ Done | LangGraph loop; live Hit@1 0.882 |
| FR-4 | Stream token-by-token (SSE) | ✅ Done | `api/chat.py` + `run_agent_streaming`; verified live |
| FR-5 | Citations to exact section, validated | ✅ Done (bonus) | `_extract_citations`; live citation `[1] IBUPROFEN#warnings` + URL |
| FR-6 | Grade chunks; re-retrieve; hard cap 3 | ✅ Done | `grade_node`/`decide_node`; `max_iters=3` |
| FR-7 | Hybrid (BM25 + vectors) + RRF + rerank | ✅ Done (bonus) | OpenSearch BM25+kNN → RRF → cross-encoder rerank |
| FR-8 | Redis caching | ✅ Done (bonus) | `cache.py`; live cold 1905 ms → warm 0.78 ms |
| FR-9 | Retrieval trace + Langfuse spans | ✅ Done | `/trace/{id}` (live: guardrail→…→generate) + `observability.py` |
| FR-10 | Refuse when uncovered | ✅ Done | `refuse_node`; live pembrolizumab clean refusal |
| FR-10a | Guardrail (first node) blocks unsafe | ✅ Done | `guardrail_node` first in graph; live self-harm block |
| FR-10b | Guardrail hybrid (keyword + LLM), degrades | ✅ Done | keyword fast-path + `gpt-4.1-mini`; degrades to keyword on failure |
| FR-10c | Caring/neutral refusals + disclaimer always | ✅ Done | `GUARDRAIL_REFUSE_CARING/NEUTRAL/ADVICE` |
| FR-10d | Guardrail shown as "Safety check" stage + trace | ✅ Done | `safety`/`blocked` SSE stages + `StageTimeline`; Playwright `terminal-blocked` |
| FR-11 | Airflow DAILY, retrying, idempotent | ✅ Done | DAG `@daily`, `retries=2`; live run SUCCESS |
| FR-12 | Continuous corpus growth | ✅ Done | `run_fda_growth()` + `kv_store` watermark; live +5 labels |
| FR-13 | Postgres persistence: labels + memory | ✅ Done | `db.py`; live 4-message memory + coreference |
| FR-14 | Two clients (Next.js + Telegram) | ✅ Done | both present; Telegram degrades safely (exit 0) |
| FR-15 | Medical disclaimer in answers/UI | ✅ Done | `Disclaimer.tsx` (always visible) + appended to every answer/refusal |

### 17.2 Milestones (PRD §11)

| # | Milestone | Status | Approach settled |
|---|---|---|---|
| M1 | Embeddings → text-embedding-3-large; re-index | ✅ | `embed_dim=3072`; re-ingested seed into OpenSearch (240 chunks) |
| M2 | OpenSearch (BM25+kNN) replaces prior store; native hybrid RRF | ✅ | OpenSearch **primary**, **Chroma retained as graceful fallback** (see 17.5-a) |
| M3 | Airflow daily + growth (watermark + fallback) | ✅ | `@daily` DAG + `grow_corpus`; skip-cursor watermark (see 17.5-c) |
| M4 | Agentic loop + citations validated + trace | ✅ | reused + hardened the v2.0 loop |
| M4a | Guardrail node + hybrid decision + caring/neutral + "Safety check" UI | ✅ | all four sub-parts implemented + tested |
| M5 | Redis + before/after latency; hybrid+rerank accuracy delta | ✅ | latency measured (v3.2: batched grading 5.98×, answer cache cold→warm); retrieval delta honest — dense wins on the grown corpus (see §14, §1b, 17.5-b) |
| M6 | Next.js split-view + evidence panel + stage events | ✅ | new UI; Playwright 4/4 |
| M7 | Telegram bot | ✅ | course-faithful structure; thin client |
| M8 | Langfuse (graceful if off) | ✅ | lazy no-op verified with keys absent |
| M9 | Dockerize all + golden-set eval + demo docs | ✅ | one `docker compose up`; live eval; this report + `CHANGES_V3.md` + `DEMO.md` |

### 17.3 API design (PRD §8) — all present

`/ask-agentic` ✅ · `/chat` (SSE) ✅ · `/ingest/fda` ✅ · `/ingest/fda/grow` ✅ ·
`/trace/{id}` ✅ · `/sessions` + `/sessions/{id}/messages` ✅ · `/health` ✅.

### 17.4 Client & test specs (PRD §9, §10.1) — all present

UI signature features (§9.1): split view · live evidence panel · animated stage timeline ·
citation→chunk highlight · corpus indicator · streaming cursor · empty state — **all done**.
Telegram structure (§9.2): `services/telegram/` · command handlers · message processing ·
`TELEGRAM__BOT_TOKEN` · async + error handling · safe-disable — **all done**. Playwright
(§10.1): `playwright.config.ts` + one spec with all six assertions — **done, 4/4 live**.

### 17.5 Deliberate deviations & the approach I settled on

Everything in the PRD is included; a few implementation choices are worth stating
explicitly, each an *additive* decision rather than a cut:

- **(a) OpenSearch primary, Chroma fallback.** The PRD makes OpenSearch the store. I made
  it the **primary** store (active whenever `OPENSEARCH_URL` is set + reachable) while
  **keeping Chroma as a graceful fallback** for offline runs. *Why:* it satisfies course
  parity in docker, keeps the 124 offline tests running with zero external services, and
  preserves the revert path the PRD's own risk register asks for ("keep a revert path").
  Not a deviation from intent — a resilience addition.
- **(b) Optimized retrieval delta is honest, not positive.** On the **grown 332-label**
  corpus, dense-only baseline is at least as good as hybrid+rerank on every retrieval metric
  (Hit@1 0.800 vs 0.720, MRR 0.812 vs 0.750 — §14), because
  every FDA label shares identical section names so BM25 fusion + a general reranker pull the
  wrong drug's same-named section up. I **reported this honestly and root-caused it** with a
  retrieval-only diagnostic rather than tune it away; a permitted RRF-weight sweep didn't
  recover it. The real, unambiguous wins are on **performance** — batched grading (5.98×) and
  the answer/retrieval caches (§14).
- **(c) Growth watermark = paging cursor.** The PRD suggests an `effective_time` watermark.
  openFDA date fields can be sparse/oddly future-dated, so I settled on a **`skip`-based
  paging cursor** (persisted in `kv_store`) plus the `effective_time` recorded for display.
  *Why:* guarantees additive growth "even on quiet days" (the PRD's own fallback rule),
  with `label_id` dedupe as the authoritative idempotency layer.
- **(d) Guardrail LLM = the same `gpt-4.1-mini`.** The PRD says "one small gpt-4.1-mini
  intent check". I use exactly that, gated behind a free deterministic keyword fast-path so
  most unsafe cases never spend a token.
- **(e) Telegram mirrors the course *approach*, not its source.** Per the PRD's own honesty
  note (§9.2), `services/telegram/` follows the same shape (handlers + message processing +
  `TELEGRAM__BOT_TOKEN` + agentic endpoint) using `python-telegram-bot`, not a line-for-line
  copy of the course's private Week-7 code.

### 17.6 Explicitly optional / not wired

- **CI workflow (GitHub Actions) for Playwright** — the PRD marks this "optional" (§10.1);
  the spec + config are ready and run locally (4/4), but no CI YAML is committed.
- **Langfuse self-host brought up live** — the overlay (`docker-compose.langfuse.yml`)
  exists and the app is verified to run with tracing **off** (the PRD's hard requirement);
  a live self-hosted Langfuse dashboard was not stood up in this session.

**Bottom line: 100% of the PRD's required and bonus scope is implemented and verified; the
only unwired items are the two the PRD itself labels optional.**

---

## 18. Reference-repo gap analysis (course repo vs this project)

The PRD models this project on **jamwithai/production-agentic-rag-course** — the "arXiv
Paper Curator" (MIT, ~7.3k★), a 7-week course that builds a production agentic RAG over
arXiv papers. Our §2 parity map shows the layers match; this section goes deeper.

**Focus:** the domain/scope swap (FDA vs arXiv) is intended and not the subject here — this
section is about the **tech stack** and the **engineering approach**: what the reference has
that we don't (with severity + mitigation, §18.1), what we add (§18.2), and — most
importantly for "how we built it" — the **architectural approach differences** (§18.3).
Reference details are drawn from the course's public README; where a specific
version/behavior is the course's, it is attributed as such.

### 18.1 What the reference repo has that this project does not (gaps + mitigation)

| # | Reference repo | This project | Gap severity | Mitigation / rationale |
|---|---|---|---|---|
| 1 | **Ollama local LLM** (:11434, privacy-preserving, offline) | **OpenAI `gpt-4.1-mini`** (cloud) | Low — intended swap | Provider-agnostic layer already ships an **Ollama impl**; switching is a one-line `.env` change (`LLM_PROVIDER=ollama`). We chose OpenAI for reliable cite/refuse instruction-following (PRD-intended). Trade-off: cloud dependency + cents of cost vs. local privacy. |
| 2 | **Docling scientific-PDF parsing** | Section extraction from **openFDA JSON** (no PDF) | None — N/A by domain | FDA labels are structured JSON prose, so there is no PDF to parse; Docling is the course's PDF-specific tool. If PDF sources were ever needed, Docling (or `unstructured`) would slot into `ingestion/`. |
| 3 | **Jina AI embeddings** | **OpenAI `text-embedding-3-large`** (3072-d) | Low — intended swap | PRD-intended; both are production embedders. Swappable via the provider layer. |
| 4 | **OpenSearch Dashboards** (:5601, search analytics/precision-recall UI) | Not exposed | **Medium** | We ship Langfuse + `/trace/{id}` + the live evidence panel for observability, but **no Kibana-style search dashboard**. Mitigation: add the `opensearch-dashboards` container + port `5601` to compose (single service, no code change). Listed as a roadmap item. |
| 5 | **Gradio UI** (:7861) | **Next.js + TypeScript** split-view + live evidence panel | None — richer swap | PRD-intended; our custom UI is arguably richer (stage timeline, PASS/FAIL evidence, citation→chunk highlight). |
| 6 | **Dev tooling: UV, Ruff, MyPy, pre-commit hooks** | pip/`pyproject.toml`, Pytest | **Medium** | We have tests (124) but **no linter/type-checker/pre-commit gating**. Mitigation: add `ruff` + `mypy` config and a `.pre-commit-config.yaml` (low effort, no runtime impact). Roadmap item. |
| 7 | **Apache Airflow 3.0** | **Airflow 2.9.3** | Low | We pin 2.9 and **sidestep its SQLAlchemy-1.4 clash by the single-writer delegation design** (Airflow does read-only fetch, backend owns writes) — so the version gap causes no functional loss. Mitigation: bump the image to 3.x; the delegation design is version-robust either way. |
| 8 | **OpenSearch 2.19** | **OpenSearch 2.13.0** | Low | Minor-version gap; kNN + BM25 APIs we use are stable across both. Mitigation: bump the image tag in compose. |
| 9 | **`notebooks/week1-7/` teaching curriculum** | None | None — not a product requirement | The course is pedagogical; this is a delivered product. Our docs (`PRD.md`, this report, `CHANGES_V3.md`, `DEMO.md`) cover design + operation. |
| 10 | **Prompt optimization** ("80% prompt reduction, 6x speed") | Prompts are compact but not formally optimized | Low | Our route/grade prompts are already single-purpose and small; a measured prompt-token pass is a cheap future win. Roadmap item. |
| 11 | **OpenSearch-native hybrid search pipeline** (server-side normalization/fusion) | **Client-side RRF** over a BM25 query + a kNN query (in `opensearch_store.py`) | Low | Our RRF is deterministic and **behaviorally identical to the Chroma fallback**, keeping the two stores consistent and testable. Mitigation: migrate to OpenSearch's `search pipeline` hybrid + score normalization for fewer round-trips. Roadmap item. |
| 12 | **Answer/response cache** ("150-400× speedup, exact-match") | ✅ **Implemented (v3.2).** A normalized-question + mode **final-answer cache** (Redis/memory, short TTL) — plus the existing query-embedding + retrieval-results cache | **Resolved** | Exact-repeat stateless questions now return the whole answer **cold ~14,079 ms → warm <1 ms**; history-bearing follow-ups are never cached. See §14 / `docs/metrics.md`. |

### 18.2 What this project adds beyond the reference repo

These are capabilities we implemented that the course repo does not emphasize — most driven
by the **safety-critical medical domain**:

- **Medical safety guardrail with intent taxonomy + refusal tones.** The course has a
  domain-boundary guardrail; ours additionally classifies **SELFHARM / MISUSE / ADVICE /
  SAFE** and answers self-harm with a **caring, help-seeking** refusal (points to 988) vs. a
  neutral decline for misuse/personalized-advice — a real medical-domain concern the arXiv
  domain doesn't face.
- **Two distinct, watchable refusal paths** — a safety *block* (before retrieval) and an
  *unanswerable* refusal (empty graded set) — surfaced as separate red/amber terminal states
  in the UI timeline.
- **Validated citations to exact label sections** with UI **citation→chunk highlight**
  (matched by `chunk_id`), not just source attribution.
- **Drug-aware grading** — a chunk about a *different* drug is graded irrelevant unless the
  question is about an interaction (prevents wrong-drug soft answers; see §15.3).
- **Graceful store fallback (Chroma)** — the app runs with zero external services offline;
  the course assumes OpenSearch is present.
- **Committed golden-set eval harness** — Hit@k / MRR / faithfulness / citation-accuracy /
  refusal-correctness with reproducible **before/after** tables (§14), beyond runtime
  analytics.
- **Browser e2e (Playwright 4/4)** exercising the real streaming UI, stages, and refusal
  states.

### 18.3 Engineering-approach differences (how it was built, not just what)

Beyond component swaps, several **architectural / engineering approaches** differ from the
course repo. These are decisions about *how the system is put together*:

- **Single-writer + HTTP write-delegation for ingestion.** The course's Airflow pipeline
  writes to OpenSearch/Postgres itself. **Our approach makes the FastAPI backend the sole
  owner/writer of both stores**; the Airflow DAG does only read-only fetch/dedupe in-worker
  and **delegates every write to the backend over HTTP** (`POST /ingest/fda`, `/ingest/fda/grow`).
  *Why:* it removes concurrent-writer races and sidesteps the Airflow-vs-app dependency
  clash. It also let us keep the read-only worker dependency-light (see the lazy-import
  point). This is the single biggest structural difference from the course.
- **Store abstraction with a probed, graceful fallback.** The course assumes OpenSearch is
  always present. **We put retrieval behind a seam** (`get_opensearch_store()` probed once;
  `retrieve_node` picks OpenSearch when reachable, else Chroma+rank-bm25) so the same code
  runs full-stack in docker *and* offline with zero services. This "degrade-gracefully"
  approach is applied uniformly — cache (Redis→memory), tracing (Langfuse→no-op), memory
  and DB all **fail soft**, so no single subsystem outage breaks a chat.
- **Client-side RRF for cross-store consistency.** Rather than rely on OpenSearch's
  server-side hybrid pipeline, **we compute Reciprocal Rank Fusion in Python** over a BM25
  query + a kNN query. *Why:* it is deterministic and **behaviorally identical to the Chroma
  fallback's fusion**, so both stores rank the same way and the same tests cover both. (The
  trade-off — an extra round-trip — is noted as a roadmap item, §18.1 #11.)
- **Streaming approach: loop-to-decision, then stream + additive event model.** We run the
  grade/decide loop to a grounded decision *first* (a defensible answer must exist before we
  stream), then stream only the final generation — reusing the exact node functions, no
  duplicated logic. On top of `token`/`done` we added **additive `stage` and `evidence` SSE
  events** so the UI animates the agent's reasoning live without changing the core contract.
- **Lazy package imports (PEP 562).** `app.ingestion` / `app.retrieval` `__init__` load heavy
  submodules (chromadb, sentence-transformers) **on first attribute access**, so the
  read-only Airflow worker imports `openfda`/`loader` with **no store driver at all** — an
  engineering choice that fell out of the single-writer design (and fixed a real DAG failure,
  §15.5).
- **Provider-agnostic LLM seam.** All agent/retrieval code calls `get_provider()`; OpenAI /
  Gemini / Groq / Ollama / local are one `.env` switch. The course is built around Ollama;
  our approach keeps the model a configuration detail.
- **Offline-deterministic test approach.** The suite runs with **no API key**: a `FakeProvider`
  (real local MiniLM embeddings + rule-based LLM replies keyed on prompt phrases) drives the
  real graph against a temp store, so all 255 tests are deterministic and CI-friendly,
  complemented by live e2e (Playwright) against the running stack.
- **Config approach: one Pydantic-settings source, bare `.env`.** A single `Settings` object
  loads config regardless of CWD; values are kept comment-free after we learned docker's
  `env_file` does not strip inline comments (§15.1).

### 18.4 Net assessment

Every **architectural layer** of the reference repo is present (OpenSearch hybrid, Airflow
daily sync + growth, Postgres, Redis, Langfuse, Telegram, FastAPI SSE) — see the §2 parity
map, verified live in §13. The genuine gaps are **peripheral, not architectural**: OpenSearch
Dashboards (#4) and lint/type/pre-commit tooling (#6) are the remaining **medium** items,
each with a low-effort mitigation already scoped (the answer cache, #12, is now **done** in
v3.2). The remaining differences
are **intended swaps** (LLM, embeddings, UI, domain/parsing) or **minor version bumps**. In
exchange, this project adds a **stronger safety posture, validated + highlighted citations,
a richer reasoning-visible UI, and a committed evaluation harness** — a net trade well-suited
to the FDA drug-information domain.

---

## 19. Pros / strengths

- **Genuinely agentic + safety-first:** an explicit safety guardrail *before* retrieval,
  plus rewrite/iterate/grade/refuse — two distinct refusal moments (unsafe vs uncovered).
- **Trustworthy citations:** validated against graded chunk ids, mapped to exact FDA label
  sections, clickable and chunk-highlighting in the UI.
- **Course-matched production depth:** OpenSearch hybrid RRF, Airflow daily sync with
  continuous growth, Postgres, Redis, Langfuse, and a second (Telegram) client — each real
  and each degrading gracefully when absent.
- **Watchable reasoning:** live stage timeline + PASS/FAIL evidence panel turn grading,
  re-retrieval, and refusal into visible moments — the strongest way to demonstrate "agentic".
- **Measurable quality:** committed golden set with section-level Hit@k/MRR + faithfulness/
  citation/refusal, reproduced live; honest before/after with no fabricated delta.
- **Resilience by design:** OpenSearch↔Chroma fallback, Redis↔memory cache, Langfuse no-op,
  memory/DB fail-soft — a subsystem outage never breaks a chat.
- **Correct data architecture:** single writer for the stores; read-only Airflow worker with
  lazy imports; idempotent, watermark-driven growth.
- **Well-tested:** 255 backend tests + 6 Playwright e2e, run offline/deterministically and
  against the live stack.

## 20. Cons / limitations & mitigations

| Gap / limitation | Impact | Mitigation / status |
|---|---|---|
| **Hybrid+rerank doesn't beat dense on this corpus** | Measured on the grown 332-label index: optimized Hit@1 0.720 vs baseline 0.800, MRR 0.750 vs 0.812 (§14). FDA labels share identical section names, so BM25 fusion + a general reranker pull the wrong drug's same-named section up; dense embeddings encode drug identity | Reported honestly, root-caused with a retrieval-only diagnostic; **dense-only is the right default here**. Hybrid mode retained (selectable) for heterogeneous corpora; a drug-aware reranker or a drug-ID metadata filter on BM25 would be the principled fix (roadmap) |
| ~~**Grading = one LLM call per candidate**~~ ✅ **fixed (v3.2)** | was up to `top_k` calls/iteration | **Batched into a single LLM call** (drug-aware logic unchanged, degrade-safe): ~12,438 → ~2,080 ms/grading step (**5.98×**). `grade_top_n` caps candidates too |
| **End-to-end latency ~10–14 s (cold)** | Dominated by generation (uncached) | Token-streamed; batched grading cut ~10 s off the grade step; **answer cache** makes exact repeats instant (<1 ms). A smaller grading model is the remaining lever |
| **Reranker cold start** | First optimized query loads the cross-encoder (~seconds) | Bake `BAAI/bge-reranker-base` into the image or a named volume for reproducible starts |
| **Store-switch dedupe coupling (§15.2)** | Switching stores while reusing the label registry can leave the new index empty | Reset store + registry together; or key dedupe on store contents |
| **openFDA `effective_time` can be sparse/odd** | Growth watermark may see future-dated labels | Paging fallback keeps growth demonstrable; watermark is advisory, dedupe is authoritative |
| **No authentication / multi-tenant** | Not publicly deployable as-is (PRD non-goal) | Add API auth + per-user session isolation before deployment |
| **Medical-domain risk** | Wrong/oversimplified drug info is harmful | Guardrail + disclaimer + retrieval-only answers + refusal; **not** clinical software |

---

## 21. How to run

```bash
# 1. env — bare values only (docker env_file does NOT strip inline # comments)
cp .env.example .env        # set OPENAI_API_KEY; EMBED_MODEL=text-embedding-3-large; EMBED_DIM=3072

# 2. full stack (backend :8000, frontend :3000, OpenSearch :9200, Postgres, Airflow :8080, telegram-bot)
docker compose up -d --build
#    Redis overlay (recommended): add -f docker-compose.redis.yml
#    Langfuse overlay:            add -f docker-compose.langfuse.yml

# 3. build the FDA index (or let the @daily Airflow DAG do it)
curl -X POST http://localhost:8000/ingest/fda
curl -X POST http://localhost:8000/ingest/fda/grow    # one continuous-growth batch

# 4. evaluate (against OpenSearch + 3-large)
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.run --mode baseline
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.run --mode optimized

# 5. tests
cd backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q          # 220 passed
cd frontend && npx tsc --noEmit && npm run build                               # clean
PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test                  # 4/4 (stack must be up)
```

- **Backend:** http://localhost:8000 · **Frontend:** http://localhost:3000 · **OpenSearch:**
  http://localhost:9200 · **Airflow:** http://localhost:8080 (admin/admin), DAG `fda_ingestion`.
- Leave `OPENSEARCH_URL` empty for the **Chroma fallback** (offline/local). Set
  `TELEGRAM__BOT_TOKEN` to activate the bot; without it the bot exits cleanly.

---

## 22. Traditional vs agentic RAG

| Dimension | Traditional RAG | Agentic RAG (this project) |
|---|---|---|
| Control flow | Fixed pipeline | Dynamic LangGraph, branching |
| Safety | None | Guardrail node *before* retrieval (blocks unsafe/off-limits) |
| Query handling | As-is | Rewritten + coreference-resolved from memory |
| Retrieval | Single pass | Iterative, re-retrieves (hard cap 3) |
| Quality control | None | Per-chunk, drug-aware relevance grading |
| Failure mode | Hallucinates | Refuses cleanly + disclaimer (two distinct refusal paths) |
| Best for | Simple FAQ | Ambiguous/multi-hop; safety-sensitive domains |

Traditional RAG is a straight line: embed → retrieve top-k → stuff → generate — fast but
brittle, with no recovery from a bad first retrieval and no notion of what it *must not*
answer. This project wraps retrieval in a reasoning loop that **guards** unsafe intent,
rewrites weak queries, retrieves iteratively, **grades** its own evidence (drug-aware), and
**answers or refuses** — embodied in `guardrail_node`, `decide_node` (loops on
insufficiency), and `refuse_node` (fires on a block or an empty graded set), not merely
described.

---

## 23. UI — "Monograph" redesign (ui-redesign)

The web UI (Next.js + TypeScript — the developer's primary stack) was redesigned from an
AI-generic soft-green "health assistant" look into a distinctive, subject-grounded identity:
**an FDA drug monograph rendered as a live clinical instrument.** The point of view is the
pharmacopoeia — official reference labels, clinical precision, analytical instruments, the ℞
mark — not a friendly chatbot. Full token system + rationale in **`docs/DESIGN.md`**.

- **Process (frontend-design skill):** brainstorm a token system → critique it against the
  three AI-generic defaults (cream+serif+terracotta / near-black+acid / broadsheet) *and* the
  old soft-green tell → build → self-critique (cut one accessory: emoji, rainbow trace colors,
  the pill cursor). Each palette/type decision derives from the documented tokens.
- **Palette (6 named roles):** cool paper/ink neutrals, one **cobalt** interactive accent, a
  role-restricted **cyan** instrument-live signal, serious **amber/red** safety signals — off
  soft-green, off all three defaults.
- **Type:** the **IBM Plex** superfamily (Sans UI/headings · Serif for monograph answer prose ·
  Mono for the reference-data layer), self-hosted via `next/font`.
- **Signature:** the evidence panel as a live instrument — a numbered "retrieval assay" log
  with a cyan LED/scan while reading, the preserved **Scope** stage as a cobalt reference tag,
  and graded chunks as `[DRUG · SECTION]` monograph citations with a serious kept/filtered
  verdict.
- **Quality floor:** WCAG-AA micro-label contrast, visible keyboard focus, responsive to
  mobile, `prefers-reduced-motion` honored. `tsc` + `next build` clean; all `data-testid`s
  preserved so Playwright stays green (a live screenshot wasn't possible — the browser
  extension is blocked from `localhost` by org policy — so the critique was code-level).
- **Mobile roadmap:** none built here (web app). A future client would be React Native /
  Flutter and reuse these framework-agnostic tokens.

---

## 24. Security posture (security-hardening)

A threat-model-driven hardening pass to a strong production posture. **Every control has a test
that proves the attack is blocked**; the full control→test matrix, the access-control model,
the secrets/prod contract, and the responsible-disclosure + known-limitations note live in
**`docs/SECURITY.md`**. Summary of what's enforced:

- **AuthN + rate limiting (item 1):** `X-API-Key` on every cost/mutating endpoint (401 on
  missing/bad; `/health` public); per-caller + per-IP fixed-window limits (Redis or memory;
  LLM 20 / ingest 5 / default 120 per minute → 429). Both default OFF for dev and ON in the
  prod compose. `test_security_auth.py`.
- **IDOR / access control (item 2):** ids are unguessable uuid4; a strict id-shape check runs
  before any lookup; sessions and traces are bound to the caller (`owner`, via a request
  contextvar), and non-owned/unknown/malformed ids all return **404** (no enumeration oracle).
  `test_security_idor.py`.
- **Input validation + injection (item 3):** oversized/empty questions → 422; a body-size cap →
  413; all SQL is parameterized SQLAlchemy (proven with a SQLi payload stored as inert data).
  `test_security_input.py`.
- **XSS-safe output + CSP (item 4):** no `dangerouslySetInnerHTML` — untrusted LLM/label text
  renders as escaped React text; strict CSP (no `unsafe-eval`) + `nosniff`/`DENY`/Referrer/
  Permissions headers on both the Next.js app and the FastAPI API; HSTS in prod.
  `test_security_headers.py` + a Playwright inert-`<script>` test.
- **Prompt-injection hardening (item 5):** the guardrail blocks instruction-override /
  reveal-system-prompt / key-exfiltration / jailbreak attempts (with drug-domain false-positive
  guards); the loop stays capped at 3; retrieved content is composed as inert DATA after the
  system instructions; the agent has no eval/exec/tool path from model text.
  `test_security_injection.py`.
- **Secrets, CORS, network, errors, containers (items 6–9):** secrets env-only and scrubbed
  from logs/`/health`/errors; explicit CORS allowlist (never `*`); a request-id middleware +
  catch-all that returns a generic 500; datastores internal-only in `docker-compose.prod.yml`
  (Redis password, no published ports); non-root Dockerfiles; and a CI workflow running
  **pip-audit + npm audit** + the security suite. `test_security_hardening.py`, CI.

**Backend suite: 246 tests pass** (26 new security tests). The access-control model today is
API-key-as-identity (a full per-user auth system is the documented next step); see
`docs/SECURITY.md` for the honest limitations.

---

## 25. Production readiness (production-hardening)

Where the project stands against the "great prototype → genuinely deployable" bar, after the
security (§24) + production passes. Full runbooks in **`docs/DEPLOYMENT.md`** and
**`docs/OPERATIONS.md`**.

| Concern | Status | Evidence |
|---|---|---|
| **AuthN + rate limiting** | ✅ enforced on all cost/mutating endpoints; frontend sends the key | §24; `test_security_auth.py`; `lib/stream.ts` |
| **CI/CD** | ✅ full backend suite + frontend `tsc`/`build` block every push; on-demand Playwright e2e; pip-audit + npm audit | `.github/workflows/ci.yml`, `security.yml` |
| **Observability** | ✅ structured JSON logs (`request_id`/latency/status), Prometheus `/metrics` (requests, p50/p95, refusal/cache rates), documented alert thresholds; Langfuse for tracing | `app/metrics.py`, `app/logging_config.py`, `test_metrics.py`, `docs/OPERATIONS.md` |
| **Secrets** | ✅ env-only, `.env` gitignored, `.env.example` placeholders, secrets-manager contract + rotation documented | `docs/OPERATIONS.md` / `SECURITY.md` |
| **Deployment** | ✅ `docker-compose.prod.yml` (auth+rate+HSTS+JSON-logs, internal-only datastores, healthchecks + resource limits + restart on every service); slim non-root images (backend `-slim`, frontend Next standalone multi-stage); registry + single-host + Kubernetes runbook | `docker-compose.prod.yml`, Dockerfiles, `docs/DEPLOYMENT.md` |

**One command** brings up the hardened stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.redis.yml -f docker-compose.prod.yml up --build -d
```

— authed, rate-limited, TLS-terminated at a proxy, healthchecked, JSON-logging, metrics-scraped.

**Documented roadmap (honest, not hidden):** a full per-user auth system (OIDC/JWT) beyond the
API-key identity; a shared trace store when scaling horizontally; wiring the alerter to a
notifier (the metrics + thresholds ship, the notifier is per-environment glue); and a Helm chart
/ managed datastores for a multi-node Kubernetes deploy. A future **mobile client** (React
Native / Flutter) must proxy auth through a token exchange — never embed the API key
(`docs/SECURITY.md`).

---

*Report produced 2026-07-04 after a full live `docker compose` verification of the v3.0
course-matched stack, including the five fixes in §15; extended through the v3.1/v3.2/
scoped-retrieval/UI-redesign/security-hardening/production-hardening passes (§1a–§1f), plus a
dynamic-catalog follow-up keeping scoping growth-safe (§14a). Current state: **255 backend tests
pass**, Playwright e2e 6/6, metrics reproduced live against OpenSearch + text-embedding-3-large.*
