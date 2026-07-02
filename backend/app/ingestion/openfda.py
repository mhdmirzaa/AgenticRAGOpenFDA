"""
openFDA drug-label ingestion.  [production item 1]

Fetches FDA-approved drug LABELS from the openFDA API (rich prose sections),
turns them into clean per-section records, and feeds them into the EXISTING
chunk -> embed -> index pipeline so citations map back to a real label section.

Keyless by default (openFDA: 240 req/min, 1,000/day per IP). An optional
OPENFDA_API_KEY raises those limits.

Dedupe policy: labels are ADDED to an accumulating knowledge base and deduped by
a stable label id (openFDA `set_id`, falling back to `id`). Re-running never
double-indexes: chunk ids are deterministic and Chroma upserts.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings
from app.ingestion.loader import Document

logger = logging.getLogger(__name__)

OPENFDA_ENDPOINT = "https://api.fda.gov/drug/label.json"

# Prose label sections worth retrieving, in a sensible citation display order.
# These are the fields with real narrative text (not codes/tables).
LABEL_SECTIONS: list[str] = [
    "boxed_warning",
    "indications_and_usage",
    "dosage_and_administration",
    "warnings",
    "warnings_and_cautions",
    "contraindications",
    "adverse_reactions",
    "drug_interactions",
]

# Curated seed list of well-known drugs (stable/reproducible demo corpus).
SEED_DRUGS: list[str] = [
    "ibuprofen", "acetaminophen", "aspirin", "amoxicillin", "azithromycin",
    "warfarin", "metformin", "lisinopril", "atorvastatin", "omeprazole",
    "amlodipine", "metoprolol", "losartan", "gabapentin", "sertraline",
    "hydrochlorothiazide", "prednisone", "albuterol", "ciprofloxacin",
    "levothyroxine", "simvastatin", "clopidogrel", "montelukast", "naproxen",
]

# Polite throttle between openFDA requests (limit is 240/min keyless).
_REQUEST_DELAY_S = 0.3


@dataclass
class DrugLabelRecord:
    """A clean, per-section representation of one FDA drug label."""
    label_id: str
    drug_name: str
    brand_name: str
    source_url: str
    sections: dict[str, str] = field(default_factory=dict)


def _first(value) -> str:
    """openFDA fields are usually lists; take the first non-empty string."""
    if isinstance(value, list):
        for v in value:
            if v:
                return str(v).strip()
        return ""
    return str(value).strip() if value else ""


def _clean_section_text(value) -> str:
    """Join a label field (list of strings) into clean prose."""
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if str(v).strip()]
        text = "\n\n".join(parts)
    else:
        text = str(value or "").strip()
    # collapse runs of blank lines / trailing spaces, keep paragraph breaks
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(lines).strip()


def _section_title(section_name: str) -> str:
    """Human-readable heading, e.g. indications_and_usage -> Indications And Usage."""
    return section_name.replace("_", " ").title()


def parse_label(result: dict) -> DrugLabelRecord | None:
    """Parse one openFDA label result into a DrugLabelRecord.

    Returns None if the label has a no stable id or no prose sections.
    """
    label_id = _first(result.get("set_id")) or _first(result.get("id"))
    if not label_id:
        openfda = result.get("openfda", {}) or {}
        label_id = _first(openfda.get("spl_set_id"))
    if not label_id:
        return None

    openfda = result.get("openfda", {}) or {}
    drug_name = _first(openfda.get("generic_name")) or _first(openfda.get("brand_name")) or "unknown"
    brand_name = _first(openfda.get("brand_name"))

    sections: dict[str, str] = {}
    for name in LABEL_SECTIONS:
        if name in result and result[name]:
            text = _clean_section_text(result[name])
            if text:
                sections[name] = text

    if not sections:
        return None

    # DailyMed is the human-facing home for an SPL set id -> real, clickable source.
    source_url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={label_id}"

    return DrugLabelRecord(
        label_id=label_id,
        drug_name=drug_name,
        brand_name=brand_name,
        source_url=source_url,
        sections=sections,
    )


def dedupe_records(
    records: list[DrugLabelRecord],
    known_label_ids: set[str] | frozenset[str] = frozenset(),
) -> list[DrugLabelRecord]:
    """Drop records whose label_id is already known or seen earlier in the batch."""
    seen: set[str] = set(known_label_ids)
    out: list[DrugLabelRecord] = []
    for rec in records:
        if rec.label_id in seen:
            continue
        seen.add(rec.label_id)
        out.append(rec)
    return out


def record_to_document(record: DrugLabelRecord) -> Document:
    """Render a label record as a markdown Document for the chunker.

    Each prose section becomes a `## Heading` so the structure-aware chunker
    emits one chunk per section (citations map to a real label section).
    """
    parts = [
        f"## {_section_title(name)}\n\n{text}"
        for name, text in record.sections.items()
    ]
    return Document(
        content="\n\n".join(parts),
        source=record.drug_name,  # citations display the drug name
        metadata={
            "label_id": record.label_id,
            "source_url": record.source_url,
            "drug_name": record.drug_name,
            "brand_name": record.brand_name,
        },
    )


async def fetch_label(
    generic_name: str,
    *,
    limit: int = 1,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Fetch raw label result(s) for one generic drug name.

    openFDA returns HTTP 404 (not an empty list) when nothing matches; we treat
    that as "no results" rather than an error.
    """
    params = {
        "search": f'openfda.generic_name:"{generic_name}"',
        "limit": limit,
    }
    if api_key:
        params["api_key"] = api_key

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.get(OPENFDA_ENDPOINT, params=params)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("results", [])
    finally:
        if own_client:
            await client.aclose()


async def fetch_drug_labels(
    drugs: list[str] | None = None,
    *,
    limit: int = 1,
    api_key: str | None = None,
) -> list[DrugLabelRecord]:
    """Fetch + parse labels for a list of drugs (throttled, keyless by default)."""
    drugs = drugs or SEED_DRUGS
    if api_key is None:
        api_key = getattr(get_settings(), "openfda_api_key", "") or None

    records: list[DrugLabelRecord] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, drug in enumerate(drugs):
            try:
                results = await fetch_label(
                    drug, limit=limit, api_key=api_key, client=client
                )
            except Exception as e:  # one bad drug must not sink the batch
                logger.warning("openFDA fetch failed for %s: %s", drug, e)
                continue
            for result in results:
                rec = parse_label(result)
                if rec is not None:
                    records.append(rec)
            if i < len(drugs) - 1:
                await asyncio.sleep(_REQUEST_DELAY_S)
    return records


async def ingest_records(
    records: list[DrugLabelRecord],
    *,
    known_label_ids: set[str] | frozenset[str] = frozenset(),
) -> dict:
    """Dedupe, chunk, embed, and index label records into Chroma.

    Idempotent: re-running the same label produces the same deterministic chunk
    ids and Chroma upserts, so the collection never grows on a repeat.
    Returns {labels_indexed, chunks_indexed, skipped}.
    """
    from app.ingestion.chunker import chunk_documents
    from app.ingestion.indexer import index_chunks

    total = len(records)
    fresh = dedupe_records(records, known_label_ids=known_label_ids)
    if not fresh:
        return {"labels_indexed": 0, "chunks_indexed": 0, "skipped": total}

    docs = [record_to_document(r) for r in fresh]
    chunks = chunk_documents(docs)
    count = await index_chunks(chunks)

    return {
        "labels_indexed": len(fresh),
        "chunks_indexed": count,
        "skipped": total - len(fresh),
    }


async def run_fda_ingestion(
    drugs: list[str] | None = None,
    *,
    limit: int = 1,
    known_label_ids: set[str] | frozenset[str] = frozenset(),
) -> dict:
    """Full job: fetch -> parse -> dedupe -> chunk+embed+index.

    Shared by the /ingest/fda endpoint and the Airflow DAG (item 3).
    """
    records = await fetch_drug_labels(drugs, limit=limit)
    stats = await ingest_records(records, known_label_ids=known_label_ids)
    stats["labels_fetched"] = len(records)
    return stats
