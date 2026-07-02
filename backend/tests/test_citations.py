"""
Citations carry FDA source metadata (drug + section + label URL).  [item 4]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.nodes import _extract_citations


def test_citation_includes_source_url_and_section_title():
    graded = [{
        "chunk_id": "ibuprofen#warnings:abc",
        "source": "ibuprofen",
        "section": "warnings",
        "text": "Do not exceed the recommended dose.",
        "source_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=xyz",
        "section_title": "Warnings",
    }]
    cits = _extract_citations("You should not exceed the dose [1].", graded)
    assert len(cits) == 1
    c = cits[0]
    assert c.source == "ibuprofen"
    assert c.section == "warnings"
    assert c.section_title == "Warnings"
    assert c.source_url.startswith("https://dailymed")


def test_citation_defaults_when_metadata_absent():
    graded = [{
        "chunk_id": "handbook.md#x:1", "source": "handbook.md",
        "section": "x", "text": "t",
    }]
    c = _extract_citations("answer [1]", graded)[0]
    assert c.source_url == ""
    assert c.section_title == ""
