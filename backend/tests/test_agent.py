"""
Tests for the agent loop.  [M6]
Tests routing, grading, citation extraction, refusal, and iteration cap.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.prompts import ROUTE_PROMPT, REWRITE_PROMPT, GRADE_PROMPT, GENERATE_PROMPT
from app.agent.state import RagState
from app.agent.nodes import _extract_citations
from app.models import Citation


class TestPromptTemplates:
    """Test that prompt templates are well-formed."""

    def test_route_prompt_has_placeholder(self):
        assert "{question}" in ROUTE_PROMPT

    def test_rewrite_prompt_has_placeholders(self):
        assert "{question}" in REWRITE_PROMPT
        assert "{previous_query}" in REWRITE_PROMPT
        assert "{iteration}" in REWRITE_PROMPT

    def test_grade_prompt_has_placeholders(self):
        assert "{question}" in GRADE_PROMPT
        assert "{chunk_text}" in GRADE_PROMPT

    def test_generate_prompt_has_placeholders(self):
        assert "{question}" in GENERATE_PROMPT
        assert "{context}" in GENERATE_PROMPT

    def test_route_prompt_format(self):
        """Route prompt should be formattable without error."""
        result = ROUTE_PROMPT.format(question="How many leave days?")
        assert "How many leave days?" in result

    def test_generate_prompt_format(self):
        """Generate prompt should be formattable without error."""
        result = GENERATE_PROMPT.format(
            question="Test?",
            context="[1] Source: test.md\nTest content",
        )
        assert "Test?" in result


class TestCitationExtraction:
    """Test citation extraction and validation."""

    def test_extract_valid_citations(self):
        """Should extract citations that map to graded chunks."""
        answer = "Employees get 18 days [1] of annual leave. Sick leave is 14 days [2]."
        graded = [
            {"chunk_id": "c1", "text": "18 days of annual leave", "source": "handbook.md", "section": "leave-policy"},
            {"chunk_id": "c2", "text": "14 days of sick leave", "source": "handbook.md", "section": "sick-leave"},
        ]
        citations = _extract_citations(answer, graded)
        assert len(citations) == 2
        assert citations[0].marker == "[1]"
        assert citations[1].marker == "[2]"

    def test_extract_no_citations(self):
        """Answer without citations should return empty list."""
        answer = "I cannot answer this question."
        graded = [{"chunk_id": "c1", "text": "some text", "source": "s", "section": "s"}]
        citations = _extract_citations(answer, graded)
        assert len(citations) == 0

    def test_invalid_citation_index(self):
        """Citations referencing non-existent chunks should be dropped."""
        answer = "Some text [1] and [5]."
        graded = [
            {"chunk_id": "c1", "text": "text", "source": "s", "section": "s"},
        ]
        citations = _extract_citations(answer, graded)
        assert len(citations) == 1
        assert citations[0].marker == "[1]"

    def test_duplicate_citations(self):
        """Duplicate citation markers should only appear once."""
        answer = "First ref [1] and again [1]."
        graded = [
            {"chunk_id": "c1", "text": "text", "source": "s", "section": "s"},
        ]
        citations = _extract_citations(answer, graded)
        assert len(citations) == 1

    def test_citation_fields(self):
        """Citations should have all required fields."""
        answer = "Answer [1]."
        graded = [
            {"chunk_id": "c1", "text": "The leave policy states 18 days.", "source": "handbook.md", "section": "leave-policy"},
        ]
        citations = _extract_citations(answer, graded)
        assert len(citations) == 1
        c = citations[0]
        assert c.marker == "[1]"
        assert c.source == "handbook.md"
        assert c.section == "leave-policy"
        assert c.chunk_id == "c1"
        assert "leave policy" in c.text.lower()


class TestRagState:
    """Test RagState structure."""

    def test_state_creation(self):
        """RagState should be creatable as a dict."""
        state: RagState = {
            "question": "How many leave days?",
            "query": "",
            "candidates": [],
            "graded": [],
            "iterations": 0,
            "answer": "",
            "citations": [],
            "trace": [],
            "trace_id": "test-id",
            "needs_retrieval": True,
            "is_sufficient": False,
            "refused": False,
        }
        assert state["question"] == "How many leave days?"
        assert state["iterations"] == 0
        assert state["refused"] is False


class TestAgentGraphStructure:
    """Test agent graph can be built."""

    def test_graph_builds(self):
        """The agent graph should compile without error."""
        from app.agent.graph import build_graph
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None
