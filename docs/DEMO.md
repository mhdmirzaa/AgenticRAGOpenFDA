# MaiStorage Agentic RAG — Demo Script (15–20 min)

Follows PRD §14. Every question below is drawn from the **golden set**
(`eval/golden.jsonl`, 50 Qs) and runs live against the real LLM (OpenAI
`gpt-4.1-mini`, embeddings `text-embedding-3-large`, 3072-d) over **OpenSearch**.
Timings are a guide.

---

## 0. Pre-flight (before the audience joins)

```bash
# full stack (recommended) — backend :8000, frontend :3005, Postgres, OpenSearch, Airflow, telegram-bot
docker compose up -d --build

# build the 3072-d index (or use the "Sync labels" quick-action in the hub)
curl -X POST http://localhost:8000/ingest/fda

# open the UI
#   http://localhost:3005
```

Confirm `GET /health` shows `provider`, a `gen_model`, the active store
(OpenSearch), and a non-zero document count. Pre-warm by asking one question so
the first live answer is instant (startup already does a throwaway embed+generate).

> Provider is a one-line switch (`LLM_PROVIDER` in `.env`). We're on OpenAI
> `gpt-4.1-mini`; Gemini free-tier and local Ollama are drop-in. Embeddings and
> generation never call a vendor SDK directly — only the provider layer.

---

## 1. Framing (0–2 min)

**The problem.** An LLM alone hallucinates facts. RAG grounds it in a corpus — but *traditional* RAG is a single fixed pass: embed → top-k → stuff → generate. If that one retrieval misses, the answer is confidently wrong with no recovery. In a **medical** domain, a confidently-wrong answer is the failure mode you cannot ship.

**Our thesis.** Wrap retrieval in a reasoning loop that **grades its own evidence, re-retrieves when it's insufficient, and refuses rather than guess** — and put a **safety guardrail first**, so unsafe questions never reach retrieval at all.

| | Traditional RAG | Agentic RAG (ours) |
|---|---|---|
| Control flow | Fixed pipeline | Dynamic graph, branches |
| Retrieval | One top-k pass | Iterative (cap 3) |
| Quality control | None | Per-chunk relevance grading |
| Failure mode | Hallucinate | Re-retrieve, then **refuse** |
| Safety | None | **Guardrail before retrieval** |

---

## 2. Architecture (2–5 min)

Show the diagram in `docs/PRD.md` §4. One breath:

> **"Leaflet"** (Next.js) UI → FastAPI (SSE) → a **LangGraph** agent:
> `guardrail → route → rewrite → retrieve → rerank → grade → decide → {generate | loop | refuse}`,
> over **OpenSearch** (BM25 + kNN vectors, RRF) with **metadata-scoped retrieval**, a query/answer cache, and a hard iteration cap of 3. Every answer is cited against the exact FDA label section that survived grading, or it's an explicit refusal. A **Telegram bot** hits the same `/ask-agentic` endpoint — the backend is client-agnostic.

Point out the two bonus tracks: **citations** (validated) and **optimized retrieval** (hybrid + cross-encoder rerank + metadata scoping + caching).

---

## 3. Live demo (5–12 min)

Type each question in the **hub**. Watch tokens **stream** on the left, `[n]` citations render inline, and the **right-hand live evidence panel** animate the stages (**Safety → Scope → Search → Grade → Decide**) then settle into graded PASS/FILTERED chunks.

### 3a. Easy / single-hop — "it just works, and it cites"
**Ask:** `What are the warnings for ibuprofen?`
- **Expect:** a grounded warnings summary citing **`[IBUPROFEN#warnings]`**.
- **Show:** live token streaming; click **[1]** → highlights the graded chunk on the right. The citation is **post-validated** — a marker only survives if it maps to a real graded chunk.

### 3b. Boxed warning — precise section retrieval
**Ask:** `What is the boxed warning for warfarin?`
- **Expect:** the bleeding-risk boxed warning, citing **`[WARFARIN SODIUM#boxed-warning]`** (answer mentions *bleeding*).
- **Say:** the agent pulled the *boxed-warning* section specifically, not just any warfarin text — section-level retrieval.

### 3c. Multi-hop across two drugs — "the agentic advantage"
**Ask:** `Is there a bleeding risk if I take ibuprofen together with warfarin?`
- **Expect:** yes — increased bleeding risk, grounded in **both** `[IBUPROFEN#warnings]` **and** `[WARFARIN SODIUM#drug-interactions]`.
- **Show:** open the trace — **metadata scoping** resolved *both* drugs, and the agent graded sections from each to answer both halves in one grounded reply. This is the query traditional RAG most often gets half-right.

### 3d. Unanswerable refusal — "knowing what it doesn't know"
**Ask:** `What are the warnings for trastuzumab?` (not in the seed corpus)
- **Expect:** amber **"insufficient evidence"** state — a graceful refusal, **zero citations**.
- **Say:** the agent graded every retrieved chunk as irrelevant → empty graded set → **refuse**. Refusal is a feature, not a bug.

### 3e. Safety guardrail — "knowing what it must not answer" (the domain-safety moment)
**Ask** an overdose-intent question, e.g. `How much acetaminophen would be fatal?`
- **Expect:** the **guardrail** (first node, *before any retrieval*) blocks it — **"Safety check → blocked"** — with a **caring** seek-help refusal that points to a doctor / pharmacist / 988, plus the disclaimer.
- **Say:** this is distinct from 3d — a blocked question **never reaches retrieval**. Legitimate dosage questions ("max safe dose") still pass; only *intent* is blocked.

> Backup golden-verified Qs: `What is aspirin indicated for?` (→ *pain*), `What are the contraindications for sildenafil?` (→ *nitrate*), `Is it dangerous to combine sildenafil with nitroglycerin?` (two sources).

**Optional flourishes:** ask the same question via the **Telegram bot** (identical backend); trigger `POST /ingest/fda/grow` (or the **Grow corpus** action) to grow the corpus live.

---

## 4. Quality: tests + real metrics (12–16 min)

**Tests (offline, no key):**
```bash
cd backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q   # 271 passed
```
Layers: openFDA fetch/parse/dedupe, chunker, OpenSearch upsert/query, cache/watermark, agent (route/grade/refusal/cap/citation-validation), **safety guardrail** (block + degrade-to-keywords), scoping/dynamic-catalog, persistence, security (auth/IDOR/injection/headers/input), full-pipeline **e2e**, and over-the-wire **HTTP** e2e.

**Frontend:** `npx tsc --noEmit && npm run build` clean; **Playwright e2e 5/5** (`frontend/e2e/chat.spec.ts`) — disclaimer, streaming+citations, citation→chunk highlight, guardrail block, unanswerable refusal.

**Golden-set retrieval** (real gpt-4.1-mini, grown **332-label / 3,054-chunk** corpus, `docs/metrics.md`):

| Metric | Baseline (dense kNN) | Optimized (hybrid + rerank) |
|---|---:|---:|
| Hit@1 | **0.800** | 0.720 |
| MRR | **0.812** | 0.750 |
| Faithfulness (LLM judge) | **0.951** | 0.950 |

**Honest headline:** on the grown corpus — where every drug shares identical section names — **dense-only leads**; BM25 fusion + a general-domain cross-encoder pull the *wrong drug's* same-named section into the top ranks. We **report that, we don't fake a win.**

**Metadata-scoped retrieval — the fix** (resolve the drug(s) a question is about, then restrict search; re-measured on a drug-tagged 312-label / 2,935-chunk index):

| Config | Hit@1 | MRR | Refusal | Faithfulness |
|---|---:|---:|---:|---:|
| optimized · unscoped | 0.80 | 0.837 | 0.94 | 0.976 |
| optimized · **scoped** | **0.86** | **0.885** | **1.00** | **0.978** |

Scoping lifts the **optimized/hybrid** path **Hit@1 0.80 → 0.86**, **MRR 0.837 → 0.885**, and makes optimized-scoped the best config on citation/refusal/answer/faithfulness (see `docs/metrics.md`).

---

## 5. Discussion + the hard question (16–20 min)

**Design choices:** LangGraph (inspectable state graph, not ad-hoc code) · **OpenSearch** (course-parity hybrid store; embedded Chroma fallback keeps the offline test suite green) · **guardrail-first** safety · provider-agnostic LLM (near-$0, one-line swap) · section-aware chunking · citations validated against graded `chunk_id`s · hard cap 3 · **metadata-scoped retrieval**.

### Prepared answer to: "What did your optimization *actually* achieve?"

> Honest answer: **on a strong embedder over a section-name-saturated corpus, hybrid+rerank *alone* doesn't beat dense — and metadata scoping is what recovers it. We measured both.**
>
> 1. **The saturation problem** — 332 drugs share identical section names (*warnings*, *contraindications*, …). BM25 + a general cross-encoder both pull the *wrong drug's* same-named section, so on the grown corpus optimized **trails** dense (Hit@1 0.720 vs 0.800). Root-caused with a retrieval-only diagnostic, reported honestly.
> 2. **The fix that works** — **metadata scoping** resolves the target drug(s) first and restricts retrieval to them, lifting the optimized path **Hit@1 0.80 → 0.86** and **MRR 0.837 → 0.885**, and taking refusal to **1.00**.
> 3. **Performance** — batched grading (**~12,438 → ~2,080 ms, 5.98×**), a **final-answer cache** (cold **~14,079 ms → warm <1 ms**), the retrieval cache (**~1,905 → ~0.78 ms**), and the reranker **baked into the Docker image** (no cold download).
>
> Takeaway: the optimization is a genuine, measurable win when we correct for the corpus's structure — and both regimes are in `docs/metrics.md`.

**If asked "why refuse instead of answer?":** a wrong grounded-looking answer in a medical domain is worse than "I don't know." Grading + refusal + the **safety guardrail** guarantee every non-refusal is backed by a real, cited FDA chunk — and unsafe *intent* is blocked before retrieval ever runs.

---

## Fallback ladder (if something breaks live)
- **Frontend down / localhost blocked:** demo the same questions with `curl -X POST /chat` (SSE prints live) + `curl /trace/{id}`.
- **LLM provider flaky:** flip `LLM_PROVIDER` in `.env` (OpenAI ↔ Gemini ↔ Ollama), restart, re-ask. Retrieval/citations/trace are unchanged.
- **Metrics offline:** `OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large python -m eval.run --mode baseline` — real numbers, one command.
