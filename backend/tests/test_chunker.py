"""
Tests for the structure-aware chunker.  [M2]
Tests chunk sizing, overlap, metadata, section preservation, and stability.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.chunker import (
    chunk_documents,
    Chunk,
    TARGET_CHARS,
    OVERLAP_CHARS,
    _split_by_headings,
    _slugify,
    _make_chunk_id,
    _split_paragraphs,
)
from app.ingestion.loader import Document


@pytest.fixture
def sample_document():
    """A sample document with known structure."""
    content = """# Test Handbook

## Leave Policy

### Annual Leave

Full-time employees are entitled to **18 days** of paid annual leave per calendar year.

Leave requests must be submitted at least 5 working days in advance through the HR portal.

Unused annual leave may be carried forward up to a maximum of 5 days.

### Sick Leave

Employees are entitled to 14 days of paid sick leave per year. A medical certificate is required for absences of 2 or more consecutive days.

## Public Holidays

The company observes **11 public holidays** annually.

**Important**: If a public holiday falls on a day that an employee has already been approved for annual leave, that annual leave day is **not deducted**.

## Product Specifications

### MaiVault

MaiVault provides automated, encrypted backup for enterprise data:

- Storage tiers: Hot (SSD), Warm (HDD), Cold (tape/archive)
- Encryption: AES-256 at rest, TLS 1.3 in transit
- RPO: 15 minutes for hot tier
- RTO: 4 hours for hot tier

### MaiSync

MaiSync enables seamless file synchronization:

- Sync speed: Delta sync with block-level differencing
- Platform support: Windows, macOS, Linux, iOS, Android, Web
- Maximum file size: 50 GB per file

## FAQ

### Q: Can I use annual leave during probation?

No. Annual leave can only be used after completing the 3-month probation period.

### Q: How do I request to work from home?

Submit a WFH request through the HR portal at least 1 day in advance.
"""
    return Document(content=content, source="test_handbook.md")


@pytest.fixture
def large_document():
    """A document with a very large section."""
    large_section = "This is a paragraph. " * 200
    content = f"""# Large Doc

## Small Section

Short content here.

## Large Section

{large_section}

## Another Small Section

More short content.
"""
    return Document(content=content, source="large_doc.md")


@pytest.fixture
def document_with_tables():
    """A document containing markdown tables."""
    content = """# Table Doc

## Data Table

| Name | Value | Description |
|------|-------|-------------|
| RPO  | 15min | Recovery Point Objective |
| RTO  | 4hrs  | Recovery Time Objective |
| SLA  | 99.9% | Service Level Agreement |

This table should not be split.
"""
    return Document(content=content, source="table_doc.md")


class TestChunkSize:

    def test_chunks_created(self, sample_document):
        chunks = chunk_documents([sample_document])
        assert len(chunks) > 0

    def test_chunk_size_within_limit(self, sample_document):
        chunks = chunk_documents([sample_document])
        for chunk in chunks:
            assert len(chunk.text) <= TARGET_CHARS * 1.5

    def test_no_empty_chunks(self, sample_document):
        chunks = chunk_documents([sample_document])
        for chunk in chunks:
            assert chunk.text.strip()


class TestChunkMetadata:

    def test_source_present(self, sample_document):
        chunks = chunk_documents([sample_document])
        for chunk in chunks:
            assert chunk.source == "test_handbook.md"

    def test_section_present(self, sample_document):
        chunks = chunk_documents([sample_document])
        for chunk in chunks:
            assert chunk.section

    def test_chunk_id_present(self, sample_document):
        chunks = chunk_documents([sample_document])
        for chunk in chunks:
            assert chunk.chunk_id

    def test_unique_chunk_ids(self, sample_document):
        chunks = chunk_documents([sample_document])
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))


class TestSectionPreservation:

    def test_heading_sections(self, sample_document):
        chunks = chunk_documents([sample_document])
        sections = set(c.section for c in chunks)
        assert len(sections) >= 4

    def test_leave_policy_chunk(self, sample_document):
        chunks = chunk_documents([sample_document])
        leave_chunks = [c for c in chunks if "leave" in c.section.lower()]
        assert len(leave_chunks) > 0
        leave_text = " ".join(c.text for c in leave_chunks)
        assert "18 days" in leave_text


class TestTablePreservation:

    def test_table_intact(self, document_with_tables):
        chunks = chunk_documents([document_with_tables])
        for chunk in chunks:
            if "| Name |" in chunk.text:
                assert "| RPO" in chunk.text
                assert "| SLA" in chunk.text


class TestLargeDocuments:

    def test_large_section_split(self, large_document):
        chunks = chunk_documents([large_document])
        large_chunks = [c for c in chunks if "large-section" in c.section]
        assert len(large_chunks) >= 2


class TestStability:

    def test_stable_chunk_ids(self, sample_document):
        chunks1 = chunk_documents([sample_document])
        chunks2 = chunk_documents([sample_document])
        ids1 = [c.chunk_id for c in chunks1]
        ids2 = [c.chunk_id for c in chunks2]
        assert ids1 == ids2

    def test_stable_chunk_count(self, sample_document):
        chunks1 = chunk_documents([sample_document])
        chunks2 = chunk_documents([sample_document])
        assert len(chunks1) == len(chunks2)


class TestEdgeCases:

    def test_empty_document(self):
        doc = Document(content="", source="empty.md")
        chunks = chunk_documents([doc])
        assert len(chunks) == 0

    def test_no_headings(self):
        doc = Document(content="Just plain text.", source="plain.md")
        chunks = chunk_documents([doc])
        assert len(chunks) >= 1

    def test_multiple_documents(self, sample_document):
        doc2 = Document(content="# Doc 2\n\n## Section A\n\nContent.", source="doc2.md")
        chunks = chunk_documents([sample_document, doc2])
        sources = set(c.source for c in chunks)
        assert "test_handbook.md" in sources
        assert "doc2.md" in sources


class TestHelperFunctions:

    def test_slugify(self):
        assert _slugify("Leave Policy") == "leave-policy"
        assert _slugify("Product Specifications") == "product-specifications"

    def test_make_chunk_id(self):
        cid = _make_chunk_id("handbook.md", "leave-policy", 0)
        assert "handbook.md" in cid
        assert "leave-policy" in cid

    def test_split_by_headings(self):
        text = "Intro\n## Section A\nContent A\n## Section B\nContent B"
        sections = _split_by_headings(text, level=2)
        assert len(sections) >= 2
