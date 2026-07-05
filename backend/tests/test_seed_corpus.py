"""
Seed-corpus integrity (GROW_AND_REMEASURE item 1).

The corpus grew to ~300 drugs to un-saturate retrieval. These tests guard the
invariants the golden set depends on: the original 24 stay first + intact, the
list is de-duplicated (case-insensitive), and it's ~300.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.openfda import SEED_DRUGS, SEED_CORE, SEED_EXPANSION

ORIGINAL_24 = [
    "ibuprofen", "acetaminophen", "aspirin", "amoxicillin", "azithromycin",
    "warfarin", "metformin", "lisinopril", "atorvastatin", "omeprazole",
    "amlodipine", "metoprolol", "losartan", "gabapentin", "sertraline",
    "hydrochlorothiazide", "prednisone", "albuterol", "ciprofloxacin",
    "levothyroxine", "simvastatin", "clopidogrel", "montelukast", "naproxen",
]


def test_original_core_preserved_and_first():
    assert SEED_CORE == ORIGINAL_24
    assert SEED_DRUGS[:24] == ORIGINAL_24  # evergreen core stays first, intact


def test_grown_to_roughly_300():
    assert 280 <= len(SEED_DRUGS) <= 340, len(SEED_DRUGS)


def test_seed_list_is_case_insensitively_unique():
    low = [d.lower().strip() for d in SEED_DRUGS]
    assert len(low) == len(set(low))  # de-duped even though SEED_EXPANSION repeats


def test_seed_names_are_clean_lowercase_query_terms():
    for d in SEED_DRUGS:
        assert d == d.lower(), d          # openFDA generic_name queries are lowercased
        assert d.strip() == d and d, d    # no stray whitespace / empties


def test_expansion_is_additive_not_a_rewrite():
    # Growth is additive: the core is not duplicated inside the expansion.
    core = {d.lower() for d in SEED_CORE}
    assert not (core & {d.lower() for d in SEED_EXPANSION})
