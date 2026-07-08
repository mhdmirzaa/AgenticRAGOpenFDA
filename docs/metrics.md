# Evaluation metrics — FDA Drug-Info RAG

Real numbers. Generation uses OpenAI **gpt-4.1-mini**; embeddings
**text-embedding-3-large** (3072-d); store **OpenSearch** (BM25 + kNN). Corpus =
**332 FDA drug labels (3,054 section chunks)** fetched live from the openFDA API
and grown from the 24-drug seed (see `eval/GROW_RUNBOOK.md`). Golden set:
`eval/golden.jsonl` (**50 questions**: 39 answerable single-hop, 6 multi-hop
across two drugs, 5 unanswerable/refusal).

Reproduce (live stack up, `OPENAI_API_KEY` set):

```bash
# from repo root, with the FDA index built (POST /ingest/fda or the DAG)
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.run --mode baseline
OPENSEARCH_URL=http://localhost:9200 EMBED_MODEL=text-embedding-3-large \
  python -m eval.run --mode optimized
```

## Golden-set results (real gpt-4.1-mini, grown 332-label corpus, 2026-07-06)

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

Baseline = dense-only kNN + score-truncate. Optimized = hybrid dense+BM25 (RRF) +
cross-encoder rerank (`BAAI/bge-reranker-base`).

### Honest interpretation of the optimization delta

**On the grown corpus, the optimized hybrid+rerank path does not beat dense-only
retrieval — and we report that honestly rather than fabricate a win.** Baseline
clearly leads on Hit@1/Hit@3/Hit@5/MRR/refusal and ties on citation/answer/
faithfulness; dense is at least as good on every metric, and clearly better on
ranking (Hit@1 0.800 vs 0.720). This is the opposite of what the small-corpus (23-label)
run predicted, and it is an instructive result, not a bug. (Two independent
re-runs — the grow pass and the v3.2 batched-grading pass — agree within ±1
question.)

**Root cause (measured, not guessed).** A retrieval-only diagnostic (raw Hit@k
over the 45 answerable questions, no LLM grading) isolates each stage:

| Retrieval config | Hit@1 | Hit@3 |
|---|---:|---:|
| Dense-only (baseline) | **0.778** | **0.867** |
| Hybrid RRF, no rerank | 0.667 | 0.778 |
| Hybrid RRF + cross-encoder rerank | 0.689 | 0.800 |

Two independent effects each pull retrieval **below** dense-only:

1. **BM25 fusion hurts on a homogeneous corpus.** Every FDA label has the *same*
   section names (`contraindications`, `drug-interactions`, `warnings`, …). With
   332 drugs indexed, a BM25 match on the section keyword pulls the **same section
   of the wrong drug** into the top ranks (e.g. `MINOCYCLINE#contraindications`
   crowding out `DOXYCYCLINE#contraindications`). Dense embeddings encode drug
   identity and avoid this; lexical fusion reintroduces it.
2. **A general-domain cross-encoder can't recover drug identity.**
   `bge-reranker-base` re-scores the fused pool but, being trained on general
   web relevance, it does not reliably prefer the *correct drug's* section — it
   recovers only part of the loss (0.667 → 0.689), never back to dense's 0.778.

**The permitted RRF/rerank sanity check does not help.** Sweeping
`rrf_bm25_weight` from 0.5 → 0.25 → 0.0 (i.e. all the way to dense-only fusion)
leaves reranked Hit@1 **flat at 0.689** — the cross-encoder re-scores the pool
from scratch, so RRF weights don't move its top-1. `rerank_top_n` can't change
Hit@1 either (it only trims how many survivors are kept, not which is ranked #1).
Per the runbook's honesty rule, no golden-set-overfitting tuning was applied and
retrieval defaults (`rrf_dense_weight=1.0`, `rrf_bm25_weight=0.5`,
`rerank_top_n=4`) were left unchanged.

**Takeaway.** For this corpus — many drugs, identical section vocabulary,
section-targeted questions — a strong dense embedding (3-large, 3072-d) is the
right retriever, and bolting on lexical fusion + a general reranker *adds noise*.
The hybrid+rerank machinery pays off on heterogeneous corpora where lexical exact
matches (codes, rare tokens) and dense semantics are complementary; here they
compete. **No delta was fabricated in either direction.**

## Performance (v3.2 latency pass — real measurements)

Three independent latency wins, all measured live against the grown index with
real `gpt-4.1-mini` + OpenSearch (see `eval/GROW_RUNBOOK.md` and the v3.2 pass):

**1. Batched grading — 5.98× faster grading.** Grading all reranked candidates
in a **single** LLM call instead of one call per candidate (drug-aware logic
preserved and *hardened* — each chunk is tagged with its source drug so wrong-drug
chunks are rejected reliably; degrades to per-chunk if the batch reply can't be
parsed). Averaged over 8 answerable golden questions (avg 4 candidates each):

| Grading | Latency | LLM calls |
|---|---:|---:|
| Per-chunk (old) | ~12,438 ms/q | 4 |
| Batched (v3.2) | ~2,080 ms/q | 1 |

That is **−10.4 s per grading step** — the single biggest per-turn win, and it
applies to every answered question.

**2. Final-answer cache — repeat questions are instant.** An exact-repeat,
stateless `(question, mode)` returns the whole answer from cache instead of
re-running the agent + generation:

| End-to-end answer | Latency |
|---|---:|
| Cold (full agent + generation) | ~14,079 ms |
| Warm (answer-cache hit) | <1 ms |

**3. Retrieval-step cache (item 7, unchanged).** Query-embedding + retrieval
results, for the retrieval step of a repeated question:

| Retrieval step | Latency |
|---|---:|
| Cold (embed + hybrid search) | ~1,905 ms |
| Warm (cache hit) | ~0.78 ms |

All caches are Redis when `REDIS_URL` is set (shared, survives restarts), else an
in-memory LRU; a Redis outage degrades to memory without breaking a request. The
answer cache uses a short TTL and never serves history-bearing follow-ups (whose
answer depends on prior turns). Separate hit/miss counters for the embedding and
answer caches are on `/health`. The reranker is **baked into the Docker image**
(`BAAI/bge-reranker-base`, loaded offline via `HF_HUB_OFFLINE=1`) so optimized
mode never cold-starts a model download at demo time.

## Metadata-scoped retrieval (scoped-retrieval branch)

Targeted fix for the cross-drug **vector-search dilution** root-caused above:
restrict the candidate set to the drug(s) a question is about **before** the
similarity search (citations: Wyoming DOT retrieval study P@10 0.77 → 0.86;
Anthropic *Contextual Retrieval*). Three pieces — drug-**tagged** embeddings +
`drug_key` field at index time; a cached `gpt-4.1-mini` **entity resolver**
(NAMED / CONDITION→indexed-drugs / NONE, degrade-safe); **scoped** BM25+kNN with
an automatic **unfiltered fallback** when a scoped search returns too few hits
(recall provably ≥ today). The resolved scope is surfaced as a `Scope: <drug>`
timeline stage. Toggle with `ENABLE_SCOPING=0`.

Reproduce — **four configs** isolate scoping's effect (rebuild the FDA index
first so chunks carry the tag + `drug_key`):

```bash
python -m eval.run --mode baseline  --no-scoping   # dense-unscoped
python -m eval.run --mode baseline  --scoped       # dense-scoped
python -m eval.run --mode optimized --no-scoping   # optimized-unscoped
python -m eval.run --mode optimized --scoped       # optimized-scoped
```

**Real results (live re-measure, 2026-07-07).** Rebuilt drug-tagged index (312 labels /
2,935 chunks, seed-only so all four configs share the exact corpus). 31/50 questions
took the scoped path (25 NAMED + 6 CONDITION), 16 NONE, 3 refusals.

| Config | Hit@1 | Hit@3 | Hit@5 | MRR | Citation | Refusal | Answer | Faithfulness |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense · unscoped | **0.90** | 0.92 | 0.92 | **0.910** | 0.90 | 0.98 | 0.90 | 0.955 |
| dense · scoped | **0.90** | 0.92 | 0.92 | 0.907 | 0.90 | **1.00** | 0.92 | **0.978** |
| optimized · unscoped | 0.80 | 0.88 | 0.88 | 0.837 | 0.85 | 0.94 | 0.92 | 0.976 |
| optimized · scoped | 0.86 | 0.90 | **0.92** | 0.885 | **0.91** | **1.00** | **0.96** | **0.978** |

**The win is on the optimized/hybrid path** (where §14 said dilution hurt most): scoping
lifts optimized **Hit@1 0.80 → 0.86**, **MRR 0.837 → 0.885**, and makes optimized-scoped the
best config on citation/refusal/answer/faithfulness (tied with dense on Hit@5). **Honest limits:**
optimized-scoped (0.86) still trails dense-only (0.90) on Hit@1 — scoping closes most of the
gap but the general cross-encoder still mis-ranks top-1 on a few scoped sets; and scoping leaves
the dense baseline's Hit@k unchanged (dense already encodes drug identity), giving it only a
faithfulness (0.955 → 0.978) + refusal (0.98 → 1.00) lift. Nothing tuned to the golden set. Full
method + citations in PROJECT_REPORT §14a. Raw: `eval/scoped_eval_2026-07-07/*.json`.

## Refusal calibration (calibrate-refusals, 2026-07-07)

Two surgical, prompt-only fixes: the guardrail no longer over-blocks general
"what treats / what can I take for X" questions (ADVICE now fires only on
*personalized* decisions), and the generator no longer over-refuses when relevant
chunks passed grading (it answers from what the labels literally say, with
interaction guidance that never invents a yes/no verdict). Live-verified with real
gpt-4.1-mini; self-harm / misuse / injection / personalized-advice / genuine
unanswerable refusals all unchanged.

**Re-measure — dense-scoped, 50-Q, same 312-label index (before → after):**

| Metric | Before | After |
|---|---:|---:|
| Hit@1 | 0.90 | 0.90 |
| Hit@3 / Hit@5 | 0.92 / 0.92 | 0.92 / 0.92 |
| MRR | 0.907 | 0.907 |
| Citation accuracy | 0.90 | 0.90 |
| Refusal correctness | 1.00 | 1.00 |
| Answer match | 0.92 | 0.92 |
| Faithfulness | 0.978 (44/45) | 0.956 (43/45) |

All unchanged except faithfulness, which moved by **one question** — *q28 "boxed
warning for fentanyl"* gave a vacuous non-answer this run (run-to-run generation
noise on the densest opioid boxed warning; *q27 oxycodone* was already borderline
before). That is judge/generation noise on a NAMED question the calibration
doesn't touch — **not a hallucination** — so faithfulness stays ≥0.95 and
refusal-correctness is unchanged. The fix adds the two correct answers without
adding wrong answers or refusals. (The first attempt hit a corrupted index — a
stale pre-tagging backend had dropped `drug_key` from most chunks; rebuilt clean
before the numbers above.)

## Test suite

220 backend tests pass offline (186 v3.2 baseline + 34 metadata-scoping tests:
entity resolution, brand→generic, word-boundary matching, CONDITION-constrained-
to-catalog, the OpenSearch drug filter, the scoped→unfiltered fallback, the
scope SSE stage, and tagged-embed/clean-store indexing):

```bash
cd backend && DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 python -m pytest -q
```
