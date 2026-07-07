"""
Golden-set runner.  [M5 baseline; M7 optimized].
Runs golden.jsonl through the system and reports metrics.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from eval.metrics import hit_at_k, mrr, citation_accuracy, refusal_correctness, answer_contains

_FAITHFULNESS_PROMPT = """You are a fact-checker. Given a QUESTION, an ANSWER, and the CONTEXT the answer was based on, decide whether every factual claim in the ANSWER is supported by the CONTEXT.

QUESTION: {question}

ANSWER: {answer}

CONTEXT:
{context}

Judging rules:
- A claim counts as SUPPORTED if the CONTEXT states the same fact, even if the ANSWER paraphrases or rewords it. Exact wording is not required.
- The CONTEXT may contain multiple numbers/figures; a claim is supported if it matches the figure the CONTEXT gives for THAT specific situation.
- Only answer NO if the ANSWER contains a claim that has NO support anywhere in the CONTEXT (a genuine hallucination or contradiction).

If every claim is supported, respond with exactly: YES
Otherwise respond with exactly: NO

Respond with exactly one word: YES or NO"""


async def judge_faithfulness(question: str, answer: str, graded: list) -> float:
    """LLM-as-judge: is the answer fully grounded in the graded context? 1.0/0.0."""
    from app.providers.base import get_provider

    if not answer.strip() or not graded:
        return 0.0
    context = "\n\n---\n\n".join(
        f"{c.get('source','')}#{c.get('section','')}\n{c.get('text','')}" for c in graded
    )
    provider = get_provider()
    verdict = await provider.complete(
        _FAITHFULNESS_PROMPT.format(question=question, answer=answer, context=context)
    )
    return 1.0 if "YES" in verdict.strip().upper() else 0.0


async def run_golden_set(mode: str = "baseline", scoped: bool | None = None) -> dict:
    """Run all golden set questions and compute metrics.

    baseline  -> dense-only retrieval, score-truncate (no BM25, no cross-encoder)
    optimized -> hybrid dense+BM25 (RRF) + cross-encoder rerank

    `scoped` toggles metadata-scoped retrieval so the four configs
    (dense/optimized × scoped/unscoped) can be measured independently and
    scoping's effect isolated (item 5). None -> the config default.
    """
    from app.agent.graph import run_agent

    use_hybrid = mode == "optimized"
    if scoped is None:
        from app.config import get_settings
        scoped = get_settings().enable_scoping
    scope_tag = "scoped" if scoped else "unscoped"

    golden_path = Path(__file__).parent / "golden.jsonl"
    questions = []
    with open(golden_path) as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))

    results = []
    for q in questions:
        print(f"\nRunning {q['id']}: {q['question']}")

        try:
            state = await run_agent(q["question"], use_hybrid=use_hybrid,
                                    use_scoping=scoped)

            answer = state.get("answer", "")
            citations = state.get("citations", [])
            refused = state.get("refused", False)
            graded = state.get("graded", [])

            # Extract retrieved sources
            retrieved_sources = []
            for chunk in graded:
                src = chunk.get("source", "")
                sec = chunk.get("section", "")
                retrieved_sources.append(f"{src}#{sec}")

            # Convert citations for metrics
            cit_dicts = []
            for c in citations:
                if hasattr(c, "model_dump"):
                    cit_dicts.append(c.model_dump())
                elif isinstance(c, dict):
                    cit_dicts.append(c)

            # Faithfulness (LLM-as-judge) only for answered (non-refused) questions.
            if refused or not q.get("expected_sources"):
                faith = None  # not applicable to refusals / unanswerable
            else:
                faith = await judge_faithfulness(q["question"], answer, graded)

            result = {
                "id": q["id"],
                "question": q["question"],
                "answer": answer,
                "refused": refused,
                "scope": state.get("scope", {}),
                "scope_path": state.get("scope_path", ""),
                "retrieved_sources": retrieved_sources,
                "citations": cit_dicts,
                "expected_sources": q.get("expected_sources", []),
                "answer_contains_terms": q.get("answer_contains", []),
                # Metrics
                "hit_at_1": hit_at_k(retrieved_sources, q.get("expected_sources", []), 1),
                "hit_at_3": hit_at_k(retrieved_sources, q.get("expected_sources", []), 3),
                "hit_at_5": hit_at_k(retrieved_sources, q.get("expected_sources", []), 5),
                "mrr": mrr(retrieved_sources, q.get("expected_sources", [])),
                "citation_accuracy": citation_accuracy(cit_dicts, q.get("expected_sources", [])),
                "refusal_correctness": refusal_correctness(answer, q.get("expected_sources", []), refused),
                "answer_match": answer_contains(answer, q.get("answer_contains", [])),
                "faithfulness": faith,
            }
            results.append(result)

            print(f"  Answer: {answer[:100]}...")
            print(f"  Refused: {refused}")
            print(f"  Hit@1: {result['hit_at_1']}, MRR: {result['mrr']:.2f}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "id": q["id"],
                "question": q["question"],
                "error": str(e),
            })

    # Aggregate metrics
    valid = [r for r in results if "error" not in r]
    faith_vals = [r["faithfulness"] for r in valid if r.get("faithfulness") is not None]
    if valid:
        scoped_n = sum(1 for r in valid
                       if str(r.get("scope_path", "")).startswith("scoped"))
        agg = {
            "mode": mode,
            "scoped": scoped,
            "scope_tag": scope_tag,
            "scoped_questions": scoped_n,
            "total_questions": len(questions),
            "successful": len(valid),
            "avg_hit_at_1": sum(r["hit_at_1"] for r in valid) / len(valid),
            "avg_hit_at_3": sum(r["hit_at_3"] for r in valid) / len(valid),
            "avg_hit_at_5": sum(r["hit_at_5"] for r in valid) / len(valid),
            "avg_mrr": sum(r["mrr"] for r in valid) / len(valid),
            "avg_citation_accuracy": sum(r["citation_accuracy"] for r in valid) / len(valid),
            "avg_refusal_correctness": sum(r["refusal_correctness"] for r in valid) / len(valid),
            "avg_answer_match": sum(r["answer_match"] for r in valid) / len(valid),
            "avg_faithfulness": (sum(faith_vals) / len(faith_vals)) if faith_vals else 0.0,
            "faithfulness_n": len(faith_vals),
        }
    else:
        agg = {"mode": mode, "scoped": scoped, "scope_tag": scope_tag,
               "total_questions": len(questions), "successful": 0}

    # Print summary
    print("\n" + "=" * 60)
    print(f"GOLDEN SET RESULTS ({mode} / {scope_tag})")
    print("=" * 60)
    for k, v in agg.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    payload = {"aggregate": agg, "details": results}
    # Unscoped runs keep the legacy filename (last_run_baseline.json /
    # last_run_optimized.json) so existing tooling/reports still resolve; scoped
    # runs get a suffixed file so all four configs can coexist.
    suffix = "" if not scoped else "_scoped"
    out_path = Path(__file__).parent / f"last_run_{mode}{suffix}.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved detailed results -> {out_path}")

    return payload


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Run golden set evaluation")
    parser.add_argument("--mode", choices=["baseline", "optimized"], default="baseline")
    scope_grp = parser.add_mutually_exclusive_group()
    scope_grp.add_argument("--scoped", dest="scoped", action="store_true",
                           help="metadata-scoped retrieval ON")
    scope_grp.add_argument("--no-scoping", dest="scoped", action="store_false",
                           help="metadata-scoped retrieval OFF (baseline-honest)")
    parser.set_defaults(scoped=None)
    args = parser.parse_args()

    asyncio.run(run_golden_set(args.mode, scoped=args.scoped))


if __name__ == "__main__":
    main()
