"""
Retrieval + answer metrics.  [M5]  rag-eval-goldenset skill.
hit_at_k, mrr, faithfulness, citation_accuracy, refusal_correctness.
"""

from __future__ import annotations


def hit_at_k(retrieved_sources: list[str], expected_sources: list[str], k: int) -> float:
    """Check if any expected source appears in the top-k retrieved sources.

    Returns 1.0 if hit, 0.0 if miss.
    """
    if not expected_sources:
        return 1.0  # No expected sources = vacuous truth

    top_k = retrieved_sources[:k]
    for expected in expected_sources:
        for retrieved in top_k:
            if _source_match(retrieved, expected):
                return 1.0
    return 0.0


def mrr(retrieved_sources: list[str], expected_sources: list[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of the first relevant result.

    Returns 0.0 if no expected source found.
    """
    if not expected_sources:
        return 1.0

    for rank, retrieved in enumerate(retrieved_sources, 1):
        for expected in expected_sources:
            if _source_match(retrieved, expected):
                return 1.0 / rank
    return 0.0


def citation_accuracy(
    citations: list[dict], expected_sources: list[str]
) -> float:
    """Fraction of expected sources that appear in the citations.

    Returns 1.0 if all expected sources are cited.
    """
    if not expected_sources:
        return 1.0

    cited_sources = set()
    for cit in citations:
        source = cit.get("source", "")
        section = cit.get("section", "")
        cited_sources.add(f"{source}#{section}")
        cited_sources.add(source)

    hits = 0
    for expected in expected_sources:
        for cited in cited_sources:
            if _source_match(cited, expected):
                hits += 1
                break

    return hits / len(expected_sources)


def refusal_correctness(
    answer: str,
    expected_sources: list[str],
    refused: bool,
) -> float:
    """Check if the system correctly refused or answered.

    - If expected_sources is empty -> should refuse -> return 1.0 if refused
    - If expected_sources is non-empty -> should answer -> return 1.0 if not refused
    """
    should_refuse = len(expected_sources) == 0

    if should_refuse and refused:
        return 1.0
    elif should_refuse and not refused:
        return 0.0
    elif not should_refuse and not refused:
        return 1.0
    else:
        return 0.0


def answer_contains(answer: str, expected_terms: list[str]) -> float:
    """Check what fraction of expected terms appear in the answer.

    Numbers are normalized (thousands separators stripped) so that e.g. an
    answer containing "$2,000" satisfies an expected term of either "2,000" or
    "2000" — these are the same value written two ways, not two facts.
    """
    if not expected_terms:
        return 1.0

    def norm(s: str) -> str:
        return s.lower().replace(",", "")

    answer_norm = norm(answer)
    hits = sum(1 for term in expected_terms if norm(term) in answer_norm)
    return hits / len(expected_terms)


def _source_match(retrieved: str, expected: str) -> bool:
    """Section-aware source matching.

    Expected sources are "file#section" (e.g. "handbook.md#leave-policy").
    Because the whole corpus lives in a single file, matching on the filename
    alone would make every retrieval a trivial hit. So when the expected source
    names a section, the retrieved source must match that section; a bare
    filename (no "#") falls back to filename matching.
    """
    r = retrieved.lower().strip()
    e = expected.lower().strip()

    if "#" in e:
        r_file, _, r_sec = r.partition("#")
        e_file, _, e_sec = e.partition("#")
        if e_file and r_file and r_file != e_file:
            return False
        # Section match is tolerant to minor formatting differences.
        return bool(e_sec) and (e_sec == r_sec or e_sec in r_sec or r_sec in e_sec)

    # No section specified in expectation -> filename-level match.
    return e in r or r in e or r.split("#")[0] == e.split("#")[0]
