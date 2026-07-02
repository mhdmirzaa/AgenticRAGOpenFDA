#!/bin/bash
# MaiStorage Agentic RAG — Quick Start Script

set -e

echo "============================================="
echo "  MaiStorage Agentic RAG — Setup & Run"
echo "============================================="

# Check Python
echo ""
echo "[1/4] Checking Python..."
python --version || python3 --version

# Install dependencies
echo ""
echo "[2/4] Installing Python dependencies..."
cd backend
pip install -e ".[dev]" 2>/dev/null || pip install fastapi uvicorn langgraph chromadb httpx pydantic pydantic-settings rank-bm25 pytest pytest-asyncio
cd ..

# Check .env
echo ""
echo "[3/4] Checking .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — please set your API key!"
fi

# Start backend
echo ""
echo "[4/4] Starting backend on port 8000..."
echo "  API: http://localhost:8000"
echo "  Health: http://localhost:8000/health"
echo "  Docs: http://localhost:8000/docs"
echo ""
echo "To ingest corpus: curl -X POST http://localhost:8000/ingest"
echo "To run Streamlit demo: pip install streamlit && streamlit run demo_app.py"
echo ""
cd backend
uvicorn app.main:app --reload --port 8000
