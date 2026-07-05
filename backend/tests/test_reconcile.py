"""
Smoke test for the golden reconciliation helper (GROW_AND_REMEASURE item 3).

The OpenSearch-dependent path can't run offline, but the module must import
cleanly and its pure loader must parse the (grown) golden set. Loaded by file
path to avoid the `eval` namespace-package import quirk under pytest.
"""

import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_RECONCILE = (Path(__file__).resolve().parents[2] / "eval" / "reconcile_golden.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("reconcile_golden", _RECONCILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reconcile_module_imports_and_loads_golden():
    mod = _load_module()
    rows = mod._load_rows()
    assert 45 <= len(rows) <= 55
    assert all("id" in r and "expected_sources" in r for r in rows)


def test_reconcile_exposes_expected_helpers():
    mod = _load_module()
    for fn in ("reconcile", "_candidate_sources", "_source_has_section"):
        assert hasattr(mod, fn)
