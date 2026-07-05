"""
Invariant tests for the generation prompt (ENHANCE item 1: answer quality).

These lock the properties the rest of the system depends on so a future prompt
edit can't silently break them:
  - the offline FakeProvider keys off the substring "context chunks";
  - citation markers stay in the [n] form that `_extract_citations` parses;
  - answers stay strictly grounded in the provided context;
  - the exact medical-disclaimer line is always required;
  - only {question}/{context} placeholders exist, so `.format()` never raises.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.prompts import GENERATE_PROMPT

DISCLAIMER_LINE = (
    "Informational only, sourced from FDA labels — not medical advice. "
    "Consult a healthcare professional."
)


def test_generate_prompt_keeps_fakeprovider_hook():
    # The e2e FakeProvider routes the generation call on this lowercase substring.
    assert "context chunks" in GENERATE_PROMPT.lower()


def test_generate_prompt_asks_for_bracket_citations():
    # Must instruct [n] markers so citation extraction/validation still works.
    assert "[1]" in GENERATE_PROMPT and "[2]" in GENERATE_PROMPT


def test_generate_prompt_enforces_grounding():
    low = GENERATE_PROMPT.lower()
    assert "only" in low
    # Must forbid inventing facts not present in the chunks.
    assert "do not infer" in low or "not written in a chunk" in low


def test_generate_prompt_requires_exact_disclaimer():
    assert DISCLAIMER_LINE in GENERATE_PROMPT


def test_generate_prompt_asks_for_readable_structure():
    low = GENERATE_PROMPT.lower()
    # Item 1: well-organized + non-expert readable (direct opener + bullets).
    assert "plain-language" in low or "plain language" in low
    assert "bullet" in low


def test_generate_prompt_formats_with_only_expected_placeholders():
    # Any stray {placeholder} would make .format(question=..., context=...) raise.
    rendered = GENERATE_PROMPT.format(question="q?", context="[1] ctx")
    assert "q?" in rendered and "[1] ctx" in rendered
