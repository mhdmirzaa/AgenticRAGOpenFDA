---
name: rag-eval-goldenset
description: "Build a golden-set evaluation harness for RAG: Hit@k, MRR, faithfulness, and citation accuracy, plus before/after optimization tables. Use when creating RAG test cases, measuring retrieval quality, building a golden dataset, evaluating chunk retrieval, proving optimization worked, or generating a before/after metrics comparison. Triggers: 'golden set', 'rag eval', 'retrieval metrics', 'hit@k', 'mrr', 'faithfulness', 'citation accuracy', 'rag test cases', 'before after retrieval', 'measure retrieval', 'rag benchmark', 'regression test rag'."
---

# RAG Evaluation (golden set + metrics)

IRON LAW: If you can't measure retrieval, you can't claim it works. Every retrieval or optimization claim must be backed by a number on the golden set.

## Why this exists

Q1's core requirement is "retrieve chunks **correctly**." This harness turns that from a hope into a measurement, and it is simultaneously (a) the required test-case deliverable, (b) the safety net that tells you which questions are demo-safe, and (c) the source of the before/after table that proves the optimization bonus.

## Workflow

```
- [ ] 1. Build the golden set (question → expected source chunk(s))
- [ ] 2. Implement Hit@k and MRR
- [ ] 3. Add faithfulness + citation-accuracy (answer-level)
- [ ] 4. Run baseline, record metrics
- [ ] 5. Run optimized (hybrid+rerank), record metrics
- [ ] 6. Emit the before/after table
```

## Step 1: Golden set

15–30 pairs is plenty for a demo. Commit it to the repo (`eval/golden.jsonl`).

```jsonl
{"id":"q1","question":"How many annual leave days do full-time staff get?","expected_sources":["handbook.md#leave-policy"],"answer_contains":["18 days"]}
{"id":"q2","question":"Can I carry over unused leave into next year?","expected_sources":["handbook.md#leave-policy"],"answer_contains":["5 days","carry"]}
{"id":"q3","question":"If a public holiday falls on my leave day, do I lose the leave?","expected_sources":["handbook.md#leave-policy","handbook.md#public-holidays"],"answer_contains":["not deducted"]}
```

- Include at least a few **multi-hop** questions (expected_sources with 2+ entries) — they showcase the agentic advantage.
- Include 1–2 **unanswerable** questions (empty `expected_sources`) to test the refusal path.

## Step 2: Hit@k and MRR

```python
def hit_at_k(retrieved_ids, expected_ids, k):
    return int(any(e in retrieved_ids[:k] for e in expected_ids))

def mrr(retrieved_ids, expected_ids):
    for rank, rid in enumerate(retrieved_ids, 1):
        if rid in expected_ids:
            return 1.0 / rank
    return 0.0
```

Report Hit@1, Hit@3, Hit@5, and mean MRR across the set.

## Step 3: Answer-level metrics

- **Faithfulness** — LLM-as-judge (local Ollama): "Is every claim in the answer supported by the provided chunks? yes/no." Score = fraction yes.
- **Citation accuracy** — for each cited `chunk_id`, does that chunk actually contain the supporting text? Score = correct citations / total citations.
- **Refusal correctness** — on unanswerable questions, did the system refuse instead of inventing an answer?

## Step 4–5: Baseline vs optimized

Run the SAME golden set twice:
- **Baseline:** dense-only retrieval, no rerank, single pass.
- **Optimized:** hybrid (dense+BM25) + rerank + agentic loop.

Keep everything else fixed so the delta is attributable.

## Step 6: Before/after table (the money artifact)

```
| Metric          | Baseline | Optimized | Δ     |
|-----------------|----------|-----------|-------|
| Hit@1           | 0.62     | 0.85      | +0.23 |
| Hit@3           | 0.78     | 0.96      | +0.18 |
| MRR             | 0.71     | 0.90      | +0.19 |
| Faithfulness    | 0.80     | 0.95      | +0.15 |
| Citation acc.   | —        | 0.93      | —     |
```

This single table satisfies the test-case criterion, the optimization bonus, and half the discussion in one slide. Generate it programmatically (`eval/run.py --mode baseline|optimized`) so it's reproducible, not hand-typed.

## Anti-patterns
- ❌ Hand-typing metrics into slides. → Generate from `eval/run.py`.
- ❌ Golden set with only easy questions. → Include multi-hop + unanswerable.
- ❌ Changing corpus/chunking between baseline and optimized. → Hold everything else fixed.
- ❌ Improvising demo questions. → Demo only golden-verified ones.

## Pre-delivery checklist
- [ ] `eval/golden.jsonl` committed, includes multi-hop + unanswerable
- [ ] `eval/run.py` produces metrics for both modes
- [ ] Before/after table generated, not hand-written
- [ ] Demo question list = subset of golden set that passes
