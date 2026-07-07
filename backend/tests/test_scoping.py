"""
Metadata-scoped retrieval (scoped-retrieval branch).

Covers the store-agnostic pieces offline + deterministic (no API key, no store):
  - index-time drug tagging (embed tagged, store clean) + drug_key;
  - entity resolution: NAMED (generic + brand->generic, word-boundary), CONDITION
    (cached LLM constrained to the catalog), NONE, and degrade-safe fallbacks;
  - OpenSearch drug filter construction + plumbing into BM25/kNN bodies;
  - the scoped-retrieval node's "too few -> retry unfiltered" safety fallback.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.retrieval.scoping import (
    DrugCatalog,
    Scope,
    normalize_drug_key,
    tag_text,
    _match_named,
    _parse_condition_names,
    resolve_scope,
)


def _reset():
    from app.providers import base as pb
    pb.reset_provider()
    from app.config import get_settings
    get_settings.cache_clear()
    from app.retrieval.cache import clear_cache
    clear_cache()
    from app.retrieval.scoping import reset_drug_catalog
    reset_drug_catalog()


@pytest.fixture(autouse=True)
def _clean():
    _reset()
    yield
    _reset()


def _catalog():
    return DrugCatalog(
        generic_keys={"ibuprofen", "aspirin", "amlodipine", "lisinopril",
                      "insulin glargine", "warfarin"},
        brand_to_generic={"advil": "ibuprofen", "lantus": "insulin glargine"},
        display={"ibuprofen": "ibuprofen", "insulin glargine": "insulin glargine"},
    )


# ------------------------------------------------------------- tagging (item 1)
def test_normalize_drug_key_lowercases_and_collapses():
    assert normalize_drug_key("  IBUPROFEN ") == "ibuprofen"
    assert normalize_drug_key("Insulin   Glargine") == "insulin glargine"
    assert normalize_drug_key("") == ""


def test_tag_text_prepends_drug_and_section():
    out = tag_text("doxycycline", "contraindications", "Do not use in pregnancy.")
    assert out == "[DRUG: doxycycline | SECTION: contraindications] Do not use in pregnancy."


def test_tag_text_handles_nested_section_slug():
    out = tag_text("warfarin", "warnings/bleeding", "Risk of bleeding.")
    assert out.startswith("[DRUG: warfarin | SECTION: bleeding]")


def test_tag_text_legacy_safe_when_no_drug():
    # No drug (e.g. a non-label corpus chunk) -> embed the text unchanged.
    assert tag_text("", "leave-policy", "text") == "text"


# --------------------------------------------------- NAMED matching (item 2)
def test_named_matches_generic():
    assert _match_named("is ibuprofen safe in pregnancy?", _catalog()) == {"ibuprofen"}


def test_named_normalizes_brand_to_generic():
    assert _match_named("what are Advil warnings?", _catalog()) == {"ibuprofen"}


def test_named_matches_multiword_generic():
    assert _match_named("insulin glargine dosing", _catalog()) == {"insulin glargine"}


def test_named_no_substring_false_positive():
    # "amoxicillin" must NOT match "amlodipine" (no shared whole word).
    assert _match_named("I took amoxicillin today", _catalog()) == set()


def test_named_multiple_drugs():
    got = _match_named("does aspirin interact with warfarin?", _catalog())
    assert got == {"aspirin", "warfarin"}


def test_named_empty_catalog():
    assert _match_named("ibuprofen", DrugCatalog()) == set()


# ------------------------------------------------ CONDITION parsing (item 2)
def test_parse_condition_names_constrains_to_catalog():
    cat = _catalog()
    # "tylenol" is not in the catalog -> dropped; lisinopril kept.
    got = _parse_condition_names('["lisinopril", "tylenol"]', cat)
    assert got == {"lisinopril"}


def test_parse_condition_names_maps_brand():
    got = _parse_condition_names('["Advil"]', _catalog())
    assert got == {"ibuprofen"}


def test_parse_condition_names_bad_json():
    assert _parse_condition_names("not json", _catalog()) == set()
    assert _parse_condition_names("[]", _catalog()) == set()


# --------------------------------------------------- resolve_scope (item 2)
class _Provider:
    def __init__(self, reply):
        self._reply = reply
        self.calls = 0

    async def complete(self, prompt):
        self.calls += 1
        return self._reply


def test_resolve_named_takes_precedence_no_llm_call():
    prov = _Provider('["amlodipine"]')
    scope = asyncio.run(resolve_scope("aspirin dosage?", _catalog(), provider=prov))
    assert scope.kind == "NAMED"
    assert scope.drug_keys == {"aspirin"}
    assert prov.calls == 0  # a named drug never needs the condition LLM call


def test_resolve_condition_maps_symptom_to_drugs():
    prov = _Provider('["lisinopril", "amlodipine"]')
    scope = asyncio.run(
        resolve_scope("what helps high blood pressure?", _catalog(), provider=prov))
    assert scope.kind == "CONDITION"
    assert scope.drug_keys == {"lisinopril", "amlodipine"}
    assert prov.calls == 1


def test_resolve_none_when_condition_empty():
    prov = _Provider("[]")
    scope = asyncio.run(resolve_scope("tell me a joke", _catalog(), provider=prov))
    assert scope.kind == "NONE"
    assert not scope.is_filtered


def test_resolve_degrades_to_none_on_llm_error():
    class _Boom:
        async def complete(self, prompt):
            raise RuntimeError("llm down")

    scope = asyncio.run(resolve_scope("high blood pressure", _catalog(), provider=_Boom()))
    assert scope.kind == "NONE"


def test_resolve_empty_catalog_is_none_without_calls():
    prov = _Provider('["ibuprofen"]')
    scope = asyncio.run(resolve_scope("ibuprofen", DrugCatalog(), provider=prov))
    assert scope.kind == "NONE"
    assert prov.calls == 0


def test_resolve_condition_disabled_skips_llm():
    prov = _Provider('["lisinopril"]')
    scope = asyncio.run(
        resolve_scope("high blood pressure", _catalog(), provider=prov,
                      enable_condition=False))
    assert scope.kind == "NONE"
    assert prov.calls == 0


def test_scope_display_lists_pretty_names():
    scope = asyncio.run(resolve_scope("aspirin and warfarin", _catalog(),
                                      provider=_Provider("[]")))
    assert scope.display == "aspirin, warfarin"


def test_scope_roundtrips_through_dict():
    s = Scope(kind="NAMED", drug_keys={"a", "b"}, display="a, b")
    assert Scope.from_dict(s.to_dict()).drug_keys == {"a", "b"}
