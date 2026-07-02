# MaiStorage Agentic RAG — Demo Script (15–20 min)

Follows PRD §12. Every question below is **golden-verified and was run live** against the real LLM (OpenAI `gpt-4.1-mini`, embeddings `text-embedding-3-small`). Timings are a guide.

---

## 0. Pre-flight (before the audience joins)

```bash
# 1. Backend (from the maistorage/ root, so .env loads)
python -m uvicorn app.main:app --app-dir backend --port 8000

# 2. Ingest the corpus (16 chunks)
curl -X POST http://localhost:8000/ingest        # -> {"chunks_indexed":16}

# 3. Frontend
cd frontend && npm install && npm run dev         # http://localhost:3000
```

Confirm `GET /health` shows `provider`, a `gen_model`, and `documents: 16`. Pre-warm by asking one question so the first live answer is instant (startup already does a throwaway embed+generate).

> Provider is a one-line switch (`LLM_PROVIDER` in `.env`). We're on OpenAI `gpt-4.1-mini`; Gemini free-tier and local Ollama are drop-in. Embeddings and generation never call a vendor SDK directly — only the provider layer.

---

## 1. Framing (0–2 min)

**The problem.** An LLM alone hallucinates facts. RAG grounds it in a corpus — but *traditional* RAG is a single fixed pass: embed → top-k → stuff → generate. If that one retrieval misses, the answer is confidently wrong with no recovery.

**Our thesis.** Wrap retrieval in a reasoning loop that **grades its own evidence, re-retrieves when it's insufficient, and refuses rather than guess.**

| | Traditional RAG | Agentic RAG (ours) |
|---|---|---|
| Control flow | Fixed pipeline | Dynamic graph, branches |
| Retrieval | One top-k pass | Iterative (cap 3) |
| Quality control | None | Per-chunk relevance grading |
| Failure mode | Hallucinate | Re-retrieve, then **refuse** |

---

## 2. Architecture (2–5 min)

Show the diagram in `docs/PRD.md` §4. One breath:

> Next.js UI → FastAPI (SSE) → a **LangGraph** agent:
> `route → rewrite → retrieve → rerank → grade → decide → {generate | loop | refuse}`,
> over **Chroma** (dense vectors) + **BM25** (keywords), with a query-embedding cache and a hard iteration cap of 3. Every answer is cited against the exact chunks that survived grading, or it's an explicit refusal.

Point out the two bonus tracks: **citations** (validated) and **optimized retrieval** (hybrid + cross-encoder rerank + caching).

---

## 3. Live demo (5–12 min)

Type each question in the UI. Watch tokens **stream**, `[n]` citations render inline, and the **Agent Trace** panel show the decision path.

### 3a. Easy / single-hop — "it just works, and it cites"
**Ask:** `How many annual leave days do full-time staff get?`
- **Expect:** *"Full-time staff get 18 days of paid annual leave per calendar year [1]."*
- **Show:** live token streaming; click **[1]** → expands the `leave-policy` chunk. Point out the citation is **post-validated** — a marker only survives if it maps to a real graded chunk.

### 3b. Keyword-exact — "where optimization earns its keep"
**Ask:** `What is the SKU code for MaiVault Pro?`
- **Expect:** *"The SKU code for MaiVault Pro is MV-8800 [1]."* (cites `product-skus-and-ordering-codes`)
- **Say:** rare tokens like `MV-8800` are exactly where pure vector search is weakest and **BM25 + rerank** pull the right chunk to the top. (Tie-in to the metrics in §4.)

### 3c. Multi-hop — "the agentic advantage"
**Ask:** `If I work on a public holiday, what compensation do I get, and can I also keep my leave day if I had leave approved?`
- **Expect:** replacement day off **or 1.5× daily rate** (manager's discretion), **and** the approved annual-leave day is **not deducted** — cited.
- **Show:** open the trace — the agent pulled and graded the `public-holidays` material to answer *both* halves in one grounded reply. This is the query traditional RAG most often gets half-right.

### 3d. Refusal — "knowing what it doesn't know"
**Ask:** `What is the WiFi password at the Tokyo office?`
- **Expect:** amber **"Insufficient evidence"** state — *"I cannot answer this question based on the available information…"*, **zero citations**.
- **Say:** it's plausible-sounding and *not* in the corpus. The agent graded every retrieved chunk as irrelevant → empty graded set → **refuse**. Refusal is a feature.

> Backup demo-safe questions (all golden-verified): "What encryption does MaiVault use for data at rest?" (AES-256), "Which error code means the API rate limit was throttled?" (ERR-6011), "How many public holidays does MaiStorage observe annually?" (11).

---

## 4. Quality: tests + real metrics (12–16 min)

**Tests (offline, no key):**
```bash
cd backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest    # 52 passed
```
Call out the layers: chunker units, citation-extraction/validation, **full-pipeline e2e** (answerable/refusal/cap/trace/streaming/hybrid), and **over-the-wire HTTP** e2e.

**Retrieval before/after — the bonus-2 proof** (`docs/metrics.md`, `eval/retrieval_benchmark.py`, section-level, 30 answerable Qs):

| Metric | Baseline (dense) | Optimized (hybrid+rerank) | Delta |
|---|---:|---:|---:|
| Hit@1 | 0.867 | **1.000** | **+0.133** |
| MRR | 0.933 | **1.000** | **+0.067** |
| Hit@3 / Hit@5 | 1.000 | 1.000 | +0.000 |

**Full agentic quality (real LLM, 35 Qs):** citation accuracy **1.000→0.971**, refusal correctness **0.971**, faithfulness (LLM-judge) **0.966**, answer-match **~0.97**.

---

## 5. Discussion + the hard question (16–20 min)

**Design choices:** LangGraph (inspectable state graph, not ad-hoc code) · Chroma (zero infra) · provider-agnostic LLM (near-$0, one-line swap) · structure-aware chunking · citations validated against graded chunk_ids · hard cap 3.

### Prepared answer to: "What did your optimization *actually* achieve?"

> Honest answer: **it depends on how good your embedder already is, and we measured both.**
>
> 1. **Accuracy** — On the retrieval benchmark with a modest local embedder (MiniLM), hybrid + cross-encoder rerank lifts **Hit@1 from 0.867 to 1.000 (+0.133)** and **MRR +0.067**. The wins are concentrated exactly where dense retrieval is weak: rare tokens and exact figures — SKU codes (`MV-8800`), error codes (`ERR-5023`), ports (`8443`). BM25 catches the literal token; the reranker orders it first.
> 2. **The honest caveat** — On top of a *strong* embedder (OpenAI `text-embedding-3-small`), dense retrieval is already near-ceiling (Hit@1 0.971), so hybrid has little to add and can even *perturb* rank-1 on **near-duplicate** sections we deliberately planted (e.g. regional leave variants). It still **fixed the hardest multi-hop** case that dense missed entirely. Net on that strong embedder: roughly a wash. We did **not** fake a delta — both numbers are in `docs/metrics.md`.
> 3. **Performance** — beyond accuracy, "optimized retrieval" also means: an **embedding cache** (repeated/retry queries are free), **startup warm-up** (no cold first token), **async SSE streaming** (first token fast), a **pre-built BM25 index**, and the **iteration cap** so the loop can't run away.
>
> Takeaway: the optimization is a genuine, measurable win when retrieval is the bottleneck, and a safe no-op when it isn't — and we can prove which regime we're in.

**If asked "why refuse instead of answer?":** a wrong grounded-looking answer is worse than "I don't know" in an enterprise knowledge base. Grading + refusal is how we guarantee every non-refusal is backed by a real, cited chunk.

---

## Fallback ladder (if something breaks live)
- **Frontend down / localhost blocked:** demo the same four questions with `curl -X POST /chat` (SSE prints live) + `curl /trace/{id}`.
- **LLM provider flaky:** flip `LLM_PROVIDER` in `.env` (OpenAI ↔ Gemini ↔ Ollama), restart, re-ask. Retrieval/citations/trace are unchanged.
- **No network at all:** run `python -m eval.retrieval_benchmark` — real retrieval numbers with local embeddings, zero keys.
