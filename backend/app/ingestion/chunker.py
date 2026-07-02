"""
Structure-aware chunking.  [M2]  rag-agentic Step 1.
~512 tokens, ~64 overlap; split on headings first, never mid-table/section.
Attach metadata: source, section, chunk_id (stable, unique).
Chunking quality = 80% of retrieval quality -- get this right.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A text chunk with metadata for retrieval."""
    text: str
    source: str          # e.g. "handbook.md"
    section: str         # e.g. "leave-policy"
    chunk_id: str        # stable unique identifier
    metadata: dict = field(default_factory=dict)


# Approximate tokens per char ratio (conservative for English)
CHARS_PER_TOKEN = 4
TARGET_TOKENS = 512
OVERLAP_TOKENS = 64
TARGET_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN  # ~2048
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN  # ~256


def chunk_documents(documents: list) -> list[Chunk]:
    """Chunk all documents using structure-aware splitting.

    Strategy:
    1. Split by top-level headings (##) into sections
    2. If a section exceeds target size, split by sub-headings (###)
    3. If still too large, split by paragraphs with overlap
    4. Never split mid-table or mid-list-item
    """
    all_chunks: list[Chunk] = []

    for doc in documents:
        if not doc.content.strip():
            continue

        # Doc-level metadata (e.g. label_id, source_url for FDA labels) rides
        # along on every chunk so citations can point back to the exact source.
        base_meta = dict(getattr(doc, "metadata", {}) or {})

        sections = _split_by_headings(doc.content, level=2)
        doc_chunks: list[Chunk] = []

        for section_title, section_text in sections:
            if not section_text.strip():
                continue

            section_slug = _slugify(section_title) if section_title else "intro"

            if len(section_text) <= TARGET_CHARS:
                chunk_id = _make_chunk_id(doc.source, section_slug, 0)
                doc_chunks.append(Chunk(
                    text=section_text.strip(),
                    source=doc.source,
                    section=section_slug,
                    chunk_id=chunk_id,
                    metadata={"section_title": section_title},
                ))
            else:
                doc_chunks.extend(_split_large_section(
                    section_text, doc.source, section_slug, section_title
                ))

        for chunk in doc_chunks:
            # base_meta first so chunk-specific keys (section_title) win.
            chunk.metadata = {**base_meta, **chunk.metadata}
        all_chunks.extend(doc_chunks)

    return all_chunks


def _split_by_headings(text: str, level: int = 2) -> list[tuple[str, str]]:
    """Split markdown text by headings of the given level."""
    pattern = r'^(#{' + str(level) + r'})\s+(.+)$'
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        match = re.match(pattern, line, re.MULTILINE)
        if match:
            if current_lines:
                sections.append((current_title, "\n".join(current_lines)))
            current_title = match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_title, "\n".join(current_lines)))

    return sections


def _split_large_section(
    text: str, source: str, section_slug: str, section_title: str
) -> list[Chunk]:
    """Split a large section into chunks, respecting structure."""
    sub_sections = _split_by_headings(text, level=3)

    if len(sub_sections) > 1:
        chunks = []
        for i, (sub_title, sub_text) in enumerate(sub_sections):
            sub_slug = f"{section_slug}/{_slugify(sub_title)}" if sub_title else f"{section_slug}/part-{i}"
            if len(sub_text) <= TARGET_CHARS:
                chunk_id = _make_chunk_id(source, sub_slug, 0)
                chunks.append(Chunk(
                    text=sub_text.strip(),
                    source=source,
                    section=sub_slug,
                    chunk_id=chunk_id,
                    metadata={"section_title": sub_title or section_title},
                ))
            else:
                chunks.extend(_paragraph_split(
                    sub_text, source, sub_slug, sub_title or section_title
                ))
        return chunks

    return _paragraph_split(text, source, section_slug, section_title)


def _paragraph_split(
    text: str, source: str, section_slug: str, section_title: str
) -> list[Chunk]:
    """Split text by paragraphs with overlap, never mid-table."""
    paragraphs = _split_paragraphs(text)
    chunks: list[Chunk] = []
    current_text = ""
    chunk_idx = 0

    for para in paragraphs:
        if len(current_text) + len(para) + 1 > TARGET_CHARS and current_text:
            chunk_id = _make_chunk_id(source, section_slug, chunk_idx)
            chunks.append(Chunk(
                text=current_text.strip(),
                source=source,
                section=section_slug,
                chunk_id=chunk_id,
                metadata={"section_title": section_title},
            ))
            chunk_idx += 1
            overlap_text = current_text[-OVERLAP_CHARS:] if len(current_text) > OVERLAP_CHARS else ""
            current_text = overlap_text + "\n\n" + para
        else:
            current_text = current_text + "\n\n" + para if current_text else para

    if current_text.strip():
        chunk_id = _make_chunk_id(source, section_slug, chunk_idx)
        chunks.append(Chunk(
            text=current_text.strip(),
            source=source,
            section=section_slug,
            chunk_id=chunk_id,
            metadata={"section_title": section_title},
        ))

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs, keeping tables and lists intact."""
    blocks: list[str] = []
    current_block: list[str] = []
    in_table = False
    in_list = False

    for line in text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("|") or stripped.startswith("+-"):
            in_table = True
            current_block.append(line)
            continue
        elif in_table and not stripped.startswith("|") and not stripped.startswith("+-"):
            in_table = False

        if re.match(r'^[\-\*\d]+[\.\)]\s', stripped):
            in_list = True
            current_block.append(line)
            continue
        elif in_list and stripped and not re.match(r'^[\-\*\d]+[\.\)]\s', stripped) and not stripped.startswith("  "):
            in_list = False

        if not stripped and not in_table and not in_list:
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
        else:
            current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block))

    return blocks


def _slugify(text: str) -> str:
    """Convert heading text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def _make_chunk_id(source: str, section: str, index: int) -> str:
    """Create a stable, unique chunk ID."""
    raw = f"{source}#{section}#{index}"
    short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"{source}#{section}:{short_hash}"
