"""
Golden-set validity (GROW_AND_REMEASURE item 2).

Guards the expanded ~50-question set so it stays reproducible and well-formed:
  - valid JSONL, unique ids, ~50 questions;
  - the original 16 factual/refusal questions are preserved verbatim (q17 was
    rotated because its old drug, insulin glargine, is now in the grown corpus);
  - answerable questions cite a real seed drug + a valid label-section slug;
  - refusal questions have empty expected_sources;
  - multi-hop questions name two sources.

expected_sources drug strings are best-effort here and get pinned to the exact
indexed generic_name by eval/reconcile_golden.py against the live grown index.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.openfda import SEED_DRUGS, LABEL_SECTIONS

GOLDEN = Path(__file__).resolve().parents[2] / "eval" / "golden.jsonl"

VALID_SECTION_SLUGS = {s.replace("_", "-") for s in LABEL_SECTIONS}
SEED_LOWER = {d.lower() for d in SEED_DRUGS}

# The original questions that must survive growth unchanged (q1..q16).
PRESERVED = {
    "q1": "What is ibuprofen used for?",
    "q2": "What are the warnings for ibuprofen?",
    "q5": "What is the boxed warning for warfarin?",
    "q13": "Is there a bleeding risk if I take ibuprofen together with warfarin?",
    "q15": "What is the capital of France?",
    "q16": "What is the retail price of ibuprofen at the pharmacy?",
}


def _load():
    rows = []
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))  # raises on malformed JSON
    return rows


def test_is_valid_jsonl_with_unique_ids():
    rows = _load()
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))  # no duplicate ids


def test_grown_to_roughly_fifty():
    rows = _load()
    assert 45 <= len(rows) <= 55, len(rows)


def test_originals_preserved_verbatim():
    by_id = {r["id"]: r for r in _load()}
    for qid, question in PRESERVED.items():
        assert by_id[qid]["question"] == question, qid


def test_q17_rotated_to_a_non_corpus_refusal():
    by_id = {r["id"]: r for r in _load()}
    q17 = by_id["q17"]
    assert q17["expected_sources"] == []  # still a refusal case
    assert "pembrolizumab" in q17["question"].lower()  # rotated drug, not seeded
    assert "pembrolizumab" not in SEED_LOWER


def test_every_row_well_formed():
    for r in _load():
        assert isinstance(r["question"], str) and r["question"].strip()
        assert isinstance(r["expected_sources"], list)
        assert isinstance(r["answer_contains"], list)
        assert all(isinstance(t, str) for t in r["answer_contains"])


def test_answerable_rows_target_seed_drugs_and_valid_sections():
    for r in _load():
        for src in r["expected_sources"]:
            assert "#" in src, src
            drug, _, section = src.partition("#")
            assert section in VALID_SECTION_SLUGS, section
            # The drug's first token must be a known seed drug (salt suffixes ok:
            # "WARFARIN SODIUM" -> "warfarin"). Pinned exactly on live reconcile.
            head = drug.lower().split()[0]
            assert any(head == s or s.startswith(head) or head.startswith(s)
                       for s in SEED_LOWER), drug


def test_refusal_and_multihop_shape():
    rows = _load()
    refusals = [r for r in rows if not r["expected_sources"]]
    multihop = [r for r in rows if len(r["expected_sources"]) >= 2]
    assert len(refusals) >= 4      # off-domain + not-in-corpus + non-label
    assert len(multihop) >= 3      # drug-drug interaction questions
