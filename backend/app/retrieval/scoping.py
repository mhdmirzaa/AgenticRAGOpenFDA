"""
Metadata-scoped retrieval: drug tagging + entity resolution.  [scoped-retrieval]

Fixes vector-search dilution on a homogeneous FDA-label corpus. Every label
shares identical section names ("warnings", "contraindications", …), so as the
corpus grows the wrong drug's same-section chunk crowds out the right one
(cross-drug confusion, measured in PROJECT_REPORT §14). The published fix is
metadata scoping: restrict the candidate set to the relevant drug(s) BEFORE the
similarity search (Wyoming DOT: P@10 0.77 -> 0.86; multiple RAG papers concur).

This module holds the store-agnostic pieces:
  1. index-time tagging  — prepend "[DRUG: x | SECTION: y]" to the EMBEDDED text
     (contextual embeddings) so the vector itself encodes drug identity, and a
     normalized `drug_key` for exact metadata filtering;
  2. entity resolution   — which drug(s) is the question about?  NAMED (explicit
     drug, brand->generic), CONDITION (symptom -> candidate generics via one
     cached gpt-4.1-mini call, constrained to the indexed catalog), or NONE.

Everything degrades safely: any failure resolves to NONE (unfiltered), so
scoping can never make retrieval worse than today.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Normalization + index-time tagging (item 1)
# --------------------------------------------------------------------------- #
def normalize_drug_key(name: str) -> str:
    """Lowercase + collapse whitespace so filtering is case/spacing-insensitive.

    openFDA `generic_name` casing is inconsistent ("IBUPROFEN" vs "ibuprofen"),
    so both the stored `drug_key` and the resolved scope run through this to make
    the keyword `terms` filter reliable.
    """
    return " ".join((name or "").strip().lower().split())


def _pretty_section(section: str) -> str:
    """Slug -> readable section label for the embedded tag (doxycycline#contra…)."""
    base = (section or "").split("/")[-1]
    return base.replace("-", " ").replace("_", " ").strip()


def tag_text(drug_name: str, section: str, text: str) -> str:
    """Prepend a compact drug/section tag to a chunk's text before embedding.

    The tag makes drug identity an explicit, high-signal token in the embedded
    vector (contextual retrieval), reinforcing what text-embedding-3-large
    already encodes implicitly. Only the EMBEDDED text is tagged — the stored
    display text stays clean so citations and the evidence panel are unchanged.
    """
    drug = (drug_name or "").strip()
    if not drug:
        return text  # legacy-safe: nothing to tag with -> embed as-is
    sec = _pretty_section(section)
    header = f"[DRUG: {drug} | SECTION: {sec}]" if sec else f"[DRUG: {drug}]"
    return f"{header} {text}"


# --------------------------------------------------------------------------- #
# Drug catalog (what is actually indexed) + entity resolution (item 2)
# --------------------------------------------------------------------------- #
@dataclass
class DrugCatalog:
    """The drugs actually present in the index, for NAMED matching + CONDITION
    constraint. Keys are normalized (lowercase); `display` maps a key back to a
    human-friendly generic name for the UI scope label."""
    generic_keys: set[str] = field(default_factory=set)
    brand_to_generic: dict[str, str] = field(default_factory=dict)  # brand_key -> generic_key
    display: dict[str, str] = field(default_factory=dict)           # generic_key -> pretty name

    def is_empty(self) -> bool:
        return not self.generic_keys

    def pretty(self, key: str) -> str:
        return self.display.get(key, key)


@dataclass
class Scope:
    """Resolved retrieval scope for a question.

    kind: NAMED (explicit drug), CONDITION (mapped from a symptom), or NONE.
    drug_keys: normalized generic keys to filter on (empty for NONE).
    display: UI/trace label — pretty drug name(s) or "all".
    """
    kind: str = "NONE"                          # NAMED | CONDITION | NONE
    drug_keys: set[str] = field(default_factory=set)
    display: str = "all"

    @property
    def is_filtered(self) -> bool:
        return self.kind != "NONE" and bool(self.drug_keys)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "drug_keys": sorted(self.drug_keys),
                "display": self.display}

    @classmethod
    def from_dict(cls, d: dict) -> "Scope":
        return cls(kind=d.get("kind", "NONE"),
                   drug_keys=set(d.get("drug_keys", [])),
                   display=d.get("display", "all"))


def _pretty_scope(keys: set[str], catalog: DrugCatalog) -> str:
    names = sorted(catalog.pretty(k) for k in keys)
    return ", ".join(names) if names else "all"


def _match_named(question: str, catalog: DrugCatalog) -> set[str]:
    """Find every catalog drug (generic OR brand) named in the question.

    Whole-word / whole-phrase match (word boundaries) so "aspirin" matches but a
    substring like "cab" inside "carbamazepine" does not. Brands normalize to
    their generic key so the filter always targets the indexed `drug_key`.
    """
    if catalog.is_empty():
        return set()
    q = f" {normalize_drug_key(question)} "
    found: set[str] = set()

    # Longest names first so a multiword generic ("insulin glargine") is matched
    # as a whole before its parts.
    candidates: list[tuple[str, str]] = [(g, g) for g in catalog.generic_keys]
    candidates += [(b, gen) for b, gen in catalog.brand_to_generic.items()]
    for name, generic in sorted(candidates, key=lambda kv: len(kv[0]), reverse=True):
        if not name:
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])"
        if re.search(pattern, q):
            found.add(generic)
    return found


_CONDITION_PROMPT = """You map a health condition or symptom to the FDA drug(s) that treat it, chosen ONLY from an allowed list. The user's question names NO drug, only a condition.

Question: {question}

Allowed generic drug names (choose ONLY from these — never invent a name):
{catalog}

Return ONLY a JSON array of the generic names from the allowed list that are commonly indicated for the condition in the question (at most 6, most relevant first). If the question is not about a treatable condition, or no allowed drug fits, return [].
Example: ["lisinopril", "amlodipine"]"""


def _parse_condition_names(response: str, catalog: DrugCatalog) -> set[str]:
    """Parse the condition->drugs reply, keeping only names that are indexed."""
    if not response or not response.strip():
        return set()
    text = response.strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return set()
    try:
        arr = json.loads(text[start:end + 1])
    except Exception:
        return set()
    if not isinstance(arr, list):
        return set()
    out: set[str] = set()
    for item in arr:
        key = normalize_drug_key(str(item))
        if key in catalog.generic_keys:            # constrained to the index
            out.add(key)
        elif key in catalog.brand_to_generic:
            out.add(catalog.brand_to_generic[key])
    return out


async def _resolve_condition(question: str, catalog: DrugCatalog, provider) -> set[str]:
    """One cheap, cached gpt-4.1-mini call mapping a condition -> indexed drugs.

    Constrained to the catalog so the model can't invent a drug. Any failure
    returns an empty set (caller -> NONE / unfiltered).
    """
    if catalog.is_empty():
        return set()
    catalog_block = ", ".join(sorted(catalog.pretty(k) for k in catalog.generic_keys))
    prompt = _CONDITION_PROMPT.format(question=question, catalog=catalog_block)
    try:
        response = await provider.complete(prompt)
    except Exception:
        return set()
    return _parse_condition_names(response, catalog)


async def resolve_scope(
    question: str,
    catalog: DrugCatalog,
    *,
    provider=None,
    enable_condition: bool = True,
) -> Scope:
    """Resolve which indexed drug(s) a question is about.

    NAMED   — one or more catalog drugs (generic/brand) appear in the question.
    CONDITION — no drug named, but a symptom/condition maps to indexed drugs via
                a single cached LLM call constrained to the catalog.
    NONE    — nothing resolvable (unfiltered retrieval, unchanged behavior).

    Fully degrade-safe: an empty catalog or any error yields NONE.
    """
    if catalog.is_empty():
        return Scope()

    named = _match_named(question, catalog)
    if named:
        return Scope(kind="NAMED", drug_keys=named,
                     display=_pretty_scope(named, catalog))

    if enable_condition:
        if provider is None:
            from app.providers.base import get_provider
            provider = get_provider()
        cond = await _resolve_condition(question, catalog, provider)
        if cond:
            return Scope(kind="CONDITION", drug_keys=cond,
                         display=_pretty_scope(cond, catalog))

    return Scope()


# --------------------------------------------------------------------------- #
# Cached resolution (one small call per unique question) + catalog loading
# --------------------------------------------------------------------------- #
async def resolve_scope_cached(question: str, catalog: DrugCatalog) -> Scope:
    """resolve_scope memoized by normalized question (shares the cache backend).

    A repeated question skips the entity-resolution LLM call entirely. Any cache
    error just recomputes — the cache never breaks resolution.
    """
    from app.retrieval.cache import get_backend, _normalize

    key = f"scope:{_normalize(question)}"
    backend = get_backend()
    try:
        raw = backend.get(key)
    except Exception:
        raw = None
    if raw is not None:
        try:
            return Scope.from_dict(json.loads(raw))
        except Exception:
            pass

    scope = await resolve_scope(question, catalog)
    try:
        from app.config import get_settings
        backend.set(key, json.dumps(scope.to_dict()),
                    get_settings().cache_ttl_seconds)
    except Exception as e:
        logger.warning("scope cache store skipped: %s", e)
    return scope


_catalog: DrugCatalog | None = None


def get_drug_catalog(*, refresh: bool = False) -> DrugCatalog:
    """Load the indexed-drug catalog (best-effort, cached in-process).

    Sourced from the Postgres/SQLite `drug_labels` table (the DB is the record of
    what has been indexed). Any failure yields an empty catalog -> scoping simply
    no-ops (NONE for everything), never crashing retrieval.
    """
    global _catalog
    if _catalog is not None and not refresh:
        return _catalog
    catalog = DrugCatalog()
    try:
        from app.db import get_indexed_drug_names
        rows = get_indexed_drug_names()
        for generic, brand in rows:
            gkey = normalize_drug_key(generic)
            if not gkey:
                continue
            catalog.generic_keys.add(gkey)
            catalog.display.setdefault(gkey, (generic or "").strip().lower())
            bkey = normalize_drug_key(brand)
            if bkey and bkey != gkey:
                catalog.brand_to_generic.setdefault(bkey, gkey)
    except Exception as e:
        logger.warning("drug catalog load skipped: %s", e)
    _catalog = catalog
    return catalog


def reset_drug_catalog() -> None:
    """Drop the in-process catalog cache (tests / after re-ingest)."""
    global _catalog
    _catalog = None
