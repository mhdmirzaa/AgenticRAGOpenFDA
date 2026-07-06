"""
Batched grading (v3.2 performance).  Grade all reranked candidates in ONE LLM
call; degrade to per-chunk grading if the batch reply can't be parsed.

Offline + deterministic: injects tiny fake providers, no API key, no store.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.nodes import grade_node, _parse_batch_verdicts


def _candidates(n=3):
    return [
        {"chunk_id": f"c{i}", "text": f"chunk {i} text about warfarin warnings",
         "source": "WARFARIN", "section": "warnings"}
        for i in range(1, n + 1)
    ]


class _CountingProvider:
    """Records how many LLM calls grade_node makes and returns a canned reply."""

    def __init__(self, reply):
        self._reply = reply
        self.calls = 0

    async def complete(self, prompt):
        self.calls += 1
        # Allow a callable reply so a test can vary output per call.
        return self._reply(prompt) if callable(self._reply) else self._reply


def _inject(provider):
    from app.providers import base as pb
    pb._provider_instance = provider


def _reset():
    from app.providers import base as pb
    pb.reset_provider()
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clean():
    _reset()
    yield
    _reset()


def test_batch_grades_all_in_a_single_call():
    """A valid JSON verdict list grades every chunk in exactly ONE call."""
    reply = '[{"index":1,"relevant":"YES"},{"index":2,"relevant":"NO"},{"index":3,"relevant":"YES"}]'
    prov = _CountingProvider(reply)
    _inject(prov)

    state = {"question": "warfarin warnings?", "candidates": _candidates(3), "trace": []}
    out = asyncio.run(grade_node(state))

    assert prov.calls == 1  # batched: one call, not one-per-chunk
    graded_ids = {c["chunk_id"] for c in out["graded"]}
    assert graded_ids == {"c1", "c3"}
    assert "via batch" in out["trace"][-1].input


def test_malformed_batch_falls_back_to_per_chunk():
    """Non-JSON batch reply => degrade to per-chunk grading (one call each)."""
    # First call (the batch attempt) returns junk; subsequent per-chunk calls
    # return YES. grade_node should still produce graded chunks and NOT crash.
    def reply(prompt):
        return "sorry, I can't do JSON" if "json array" in prompt.lower() else "YES"

    prov = _CountingProvider(reply)
    _inject(prov)

    state = {"question": "warfarin warnings?", "candidates": _candidates(3), "trace": []}
    out = asyncio.run(grade_node(state))

    # 1 failed batch call + 3 per-chunk calls.
    assert prov.calls == 4
    assert len(out["graded"]) == 3
    assert "via per-chunk" in out["trace"][-1].input


def test_wrong_length_batch_falls_back():
    """A verdict list that doesn't cover every chunk is rejected -> fallback."""
    def reply(prompt):
        return '[{"index":1,"relevant":"YES"}]' if "json array" in prompt.lower() else "NO"

    prov = _CountingProvider(reply)
    _inject(prov)

    state = {"question": "q", "candidates": _candidates(3), "trace": []}
    out = asyncio.run(grade_node(state))
    assert prov.calls == 4  # 1 batch (rejected) + 3 per-chunk
    assert "via per-chunk" in out["trace"][-1].input


def test_batch_call_exception_falls_back():
    """If the batch LLM call raises, we still grade via per-chunk (never crash)."""
    class _Flaky:
        def __init__(self):
            self.calls = 0

        async def complete(self, prompt):
            self.calls += 1
            if "json array" in prompt.lower():
                raise RuntimeError("batch down")
            return "YES"

    prov = _Flaky()
    _inject(prov)
    state = {"question": "q", "candidates": _candidates(2), "trace": []}
    out = asyncio.run(grade_node(state))
    assert len(out["graded"]) == 2


def test_empty_candidates_makes_no_calls():
    prov = _CountingProvider("[]")
    _inject(prov)
    out = asyncio.run(grade_node({"question": "q", "candidates": [], "trace": []}))
    assert prov.calls == 0
    assert out["graded"] == []


def test_grade_top_n_caps_the_batch():
    """grade_top_n limits how many reranked candidates are graded."""
    os.environ["GRADE_TOP_N"] = "2"
    from app.config import get_settings
    get_settings.cache_clear()

    reply = '[{"index":1,"relevant":"YES"},{"index":2,"relevant":"YES"}]'
    prov = _CountingProvider(reply)
    _inject(prov)
    try:
        state = {"question": "q", "candidates": _candidates(5), "trace": []}
        out = asyncio.run(grade_node(state))
        assert prov.calls == 1
        assert len(out["graded"]) == 2  # only top-2 graded
    finally:
        os.environ.pop("GRADE_TOP_N", None)
        get_settings.cache_clear()


class TestParseBatchVerdicts:
    def test_plain_array(self):
        v = _parse_batch_verdicts('[{"index":1,"relevant":"YES"},{"index":2,"relevant":"NO"}]', 2)
        assert v == {1: True, 2: False}

    def test_wrapped_in_prose_and_fences(self):
        raw = 'Sure!\n```json\n[{"index":1,"relevant":"yes"}]\n```\ndone'
        assert _parse_batch_verdicts(raw, 1) == {1: True}

    def test_bad_json_returns_none(self):
        assert _parse_batch_verdicts("not json", 2) is None

    def test_length_mismatch_returns_none(self):
        assert _parse_batch_verdicts('[{"index":1,"relevant":"YES"}]', 3) is None

    def test_missing_index_returns_none(self):
        assert _parse_batch_verdicts('[{"index":1,"relevant":"YES"},{"index":1,"relevant":"NO"}]', 2) is None
