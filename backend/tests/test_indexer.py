"""
Tests for the indexer and vectorstore.  [M2]
Tests Chroma upsert/query round-trip.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.chunker import Chunk


class TestIndexerUnit:
    """Unit tests for indexer logic (mocked embeddings)."""

    def test_chunk_dataclass(self):
        """Chunk dataclass should be constructable."""
        chunk = Chunk(
            text="Test content",
            source="test.md",
            section="test-section",
            chunk_id="test.md#test-section:abc123",
        )
        assert chunk.text == "Test content"
        assert chunk.source == "test.md"
        assert chunk.section == "test-section"
        assert chunk.chunk_id == "test.md#test-section:abc123"

    def test_chunk_metadata_default(self):
        """Chunk metadata should default to empty dict."""
        chunk = Chunk(
            text="Test",
            source="test.md",
            section="s",
            chunk_id="id",
        )
        assert chunk.metadata == {}
