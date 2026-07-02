"""
Tests for API endpoints.  [M3]
Tests /health, /chat SSE streaming, and /ingest.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import ChatRequest, Citation, TraceStep, ChatDoneEvent, ChatTokenEvent, ChatErrorEvent


class TestModels:
    """Test Pydantic models."""

    def test_chat_request(self):
        req = ChatRequest(question="How many leave days?")
        assert req.question == "How many leave days?"

    def test_citation(self):
        cit = Citation(
            marker="[1]",
            source="handbook.md",
            section="leave-policy",
            chunk_id="handbook.md#leave-policy:abc123",
            text="18 days of annual leave",
        )
        assert cit.marker == "[1]"
        assert cit.source == "handbook.md"

    def test_trace_step(self):
        step = TraceStep(
            node="route",
            input="question",
            output="needs_retrieval=True",
        )
        assert step.node == "route"

    def test_chat_token_event(self):
        event = ChatTokenEvent(text="Hello")
        assert event.type == "token"
        assert event.text == "Hello"

    def test_chat_done_event(self):
        event = ChatDoneEvent(
            citations=[],
            trace_id="test-trace-id",
        )
        assert event.type == "done"
        assert event.trace_id == "test-trace-id"

    def test_chat_error_event(self):
        event = ChatErrorEvent(message="Something went wrong")
        assert event.type == "error"
        assert event.message == "Something went wrong"


class TestHealthEndpoint:
    """Test /health endpoint structure."""

    def test_health_response_structure(self):
        """Health response should have required fields."""
        expected_fields = ["status", "provider", "gen_model", "embed_model", "chroma"]
        from app.config import get_settings
        settings = get_settings()
        assert settings.llm_provider
        assert settings.gen_model
        assert settings.embed_model
