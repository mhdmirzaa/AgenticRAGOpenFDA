"""Load corpus files (md/txt/pdf) from corpus/.  [M2]  rag-agentic Step 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings


@dataclass
class Document:
    """A loaded document with its content and metadata."""
    content: str
    source: str  # filename, e.g. "handbook.md"
    metadata: dict = field(default_factory=dict)


def load_corpus(corpus_path: str | None = None) -> list[Document]:
    """Load all supported files from the corpus directory.
    
    Supported formats: .md, .txt, .pdf (pdf requires text extraction).
    Returns a list of Document objects.
    """
    if corpus_path is None:
        corpus_path = get_settings().corpus_path

    corpus_dir = Path(corpus_path)
    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    documents: list[Document] = []
    supported_extensions = {".md", ".txt", ".pdf"}

    for file_path in sorted(corpus_dir.iterdir()):
        if file_path.suffix.lower() not in supported_extensions:
            continue
        if file_path.name.startswith(".") or file_path.name == "README.md":
            continue

        content = _load_file(file_path)
        if content.strip():
            documents.append(Document(
                content=content,
                source=file_path.name,
                metadata={"path": str(file_path), "extension": file_path.suffix},
            ))

    if not documents:
        raise ValueError(f"No documents found in {corpus_dir}")

    return documents


def _load_file(path: Path) -> str:
    """Load content from a single file."""
    ext = path.suffix.lower()

    if ext in (".md", ".txt"):
        return path.read_text(encoding="utf-8")
    elif ext == ".pdf":
        return _load_pdf(path)
    else:
        return ""


def _load_pdf(path: Path) -> str:
    """Extract text from PDF. Falls back to empty string if no PDF library."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except ImportError:
        print(f"Warning: PyMuPDF not installed, skipping {path.name}")
        return ""
