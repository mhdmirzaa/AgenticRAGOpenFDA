"""
Dynamic drug catalog — growth-safe scoping (dynamic-catalog).

Proves the CONDITION resolver reads the indexed-drug catalog from the LIVE store,
so a drug added by corpus growth becomes scopable automatically; NAMED is
unchanged; and a catalog-fetch failure degrades to NONE (never crashes).
"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _reset():
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
    from app.providers import base as pb
    pb.reset_provider()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("DRUG_CATALOG_TTL_SECONDS", None)
    from app.db import reset_engine
    reset_engine()
    _reset()


class _Label:
    """Minimal record accepted by db.record_labels."""
    def __init__(self, label_id, drug_name, brand_name=""):
        self.label_id = label_id
        self.drug_name = drug_name
        self.brand_name = brand_name
        self.source_url = ""


class _CondProvider:
    """Maps any CONDITION prompt to a fixed set of generic names (constrained by
    the catalog downstream)."""
    def __init__(self, names):
        self._names = names
        self.calls = 0

    async def complete(self, prompt):
        self.calls += 1
        return json.dumps(self._names)


def _use_db(tmp):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/dc.db"
    from app.config import get_settings
    get_settings.cache_clear()
    from app.db import reset_engine, init_db
    reset_engine()
    init_db()


def test_condition_scoping_is_growth_safe(tmp_path):
    _use_db(str(tmp_path))
    from app.db import record_labels
    from app.providers import base as pb
    from app.retrieval.scoping import (
        get_drug_catalog, resolve_scope_cached, reset_drug_catalog)

    # Corpus A: only lisinopril indexed. The condition LLM would map high blood
    # pressure -> [lisinopril, amlodipine], but amlodipine isn't in the corpus yet.
    record_labels([_Label("L1", "lisinopril")])
    pb._provider_instance = _CondProvider(["lisinopril", "amlodipine"])

    q = "what helps high blood pressure?"
    s1 = asyncio.run(resolve_scope_cached(q, get_drug_catalog(refresh=True)))
    assert s1.kind == "CONDITION"
    assert s1.drug_keys == {"lisinopril"}          # constrained to what exists now

    # Grow the corpus: add amlodipine, then invalidate (as an ingest would).
    record_labels([_Label("L2", "amlodipine")])
    reset_drug_catalog()

    # The SAME question now scopes to include the newly-ingested drug — no restart,
    # no code change. (Also proves the version-keyed scope cache didn't serve s1.)
    s2 = asyncio.run(resolve_scope_cached(q, get_drug_catalog()))
    assert s2.kind == "CONDITION"
    assert s2.drug_keys == {"lisinopril", "amlodipine"}


def test_ttl_auto_refresh_without_explicit_bust(tmp_path):
    _use_db(str(tmp_path))
    os.environ["DRUG_CATALOG_TTL_SECONDS"] = "0"   # expire immediately
    from app.config import get_settings
    get_settings.cache_clear()
    from app.db import record_labels
    from app.retrieval.scoping import get_drug_catalog

    record_labels([_Label("L1", "aspirin")])
    assert "aspirin" in get_drug_catalog(refresh=True).generic_keys

    # A newly-ingested drug appears on the next read once the TTL has elapsed,
    # even without an explicit reset (the passive growth path).
    record_labels([_Label("L2", "ibuprofen")])
    assert "ibuprofen" in get_drug_catalog().generic_keys


def test_named_scoping_unchanged(tmp_path):
    _use_db(str(tmp_path))
    from app.db import record_labels
    from app.retrieval.scoping import get_drug_catalog, resolve_scope

    record_labels([_Label("L1", "warfarin")])
    cat = get_drug_catalog(refresh=True)
    s = asyncio.run(resolve_scope("what are the warnings for warfarin?", cat))
    assert s.kind == "NAMED" and s.drug_keys == {"warfarin"}


def test_catalog_fetch_failure_degrades_to_none(monkeypatch):
    from app.retrieval import scoping

    def _boom():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("app.db.get_indexed_drug_names", _boom)
    scoping.reset_drug_catalog()

    cat = scoping.get_drug_catalog(refresh=True)
    assert cat.is_empty()                              # degraded, no crash
    s = asyncio.run(scoping.resolve_scope("what helps high blood pressure?", cat))
    assert s.kind == "NONE" and not s.is_filtered


def test_reset_bumps_version(tmp_path):
    from app.retrieval.scoping import catalog_version, reset_drug_catalog
    v0 = catalog_version()
    reset_drug_catalog()
    assert catalog_version() == v0 + 1
