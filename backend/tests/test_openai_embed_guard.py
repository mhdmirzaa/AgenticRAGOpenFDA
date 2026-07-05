"""
OpenAI embedding-input guard (GROW_AND_REMEASURE: unblock ~300-drug growth).

A few FDA label sections exceed text-embedding-3-large's 8191-token limit once
the corpus grows, which returned a hard 400 and aborted ingestion. The provider
now clamps each embedding input to a safe, non-empty length.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.providers.openai import _prepare_embed_input, _MAX_EMBED_CHARS


def test_oversized_input_is_truncated():
    huge = "word " * 20_000  # ~100k chars, well over the 8191-token limit
    out = _prepare_embed_input(huge)
    assert len(out) <= _MAX_EMBED_CHARS


def test_empty_input_becomes_nonempty():
    # OpenAI 400s on an empty string; never send one.
    assert _prepare_embed_input("") == " "
    assert _prepare_embed_input("   ") == " "
    assert _prepare_embed_input(None) == " "  # defensive


def test_normal_input_unchanged():
    t = "Ibuprofen is used to relieve pain and reduce inflammation."
    assert _prepare_embed_input(t) == t


def test_char_budget_is_safe_for_8191_tokens():
    # ~24k chars ≈ ~6k tokens, comfortably under the 8191-token cap.
    assert _MAX_EMBED_CHARS <= 28_000
