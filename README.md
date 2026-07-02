# MaiStorage — Agentic RAG System

An **Agentic Retrieval-Augmented Generation** system that goes beyond traditional RAG by adding an intelligent agent loop with self-grading, re-retrieval, citations, and graceful refusal.

## Architecture

```
User Question → Route → Rewrite → Retrieve → Rerank → Grade → Decide → Generate/Refuse
                                      ↑                           |
                                      └── retry (max 3 iterations)┘
```

### Key Components
- **Backend**: FastAPI + LangGraph + ChromaDB
- **Frontend**: Next.js + TypeScript (primary streaming chat UI). An optional Streamlit app (`demo_app.py`) is provided as a no-Node fallback.
- **LLM**: Provider-agnostic (Gemini/OpenAI/Groq/Ollama via config switch)
- **Retrieval**: Hybrid (Dense + BM25) with cross-encoder reranking
- **Evaluation**: Golden-set harness with Hit@k, MRR, citation accuracy

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY (free tier: https://aistudio.google.com/)
```

### 3. Run the Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 4. Ingest the Corpus
```bash
curl -X POST http://localhost:8000/ingest
```

### 5. Run the Frontend

**Primary UI — Next.js + TypeScript** (the frontend specified by the PRD):
```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```
Streaming tokens, inline clickable citations, the agent trace panel, and a
refusal state all render here.

### Optional: Streamlit fallback (`demo_app.py`)

`demo_app.py` is an **optional, single-process demo fallback** — **not** the
primary UI. It imports the same backend agent code in-process (so it always
stays in sync) and needs **no Node.js / npm**. Use it only when:
- Node isn't available or `npm install` fails on the demo machine, or
- the browser can't reach `localhost:3000` (some managed environments block it).

```bash
pip install streamlit          # if not already installed
streamlit run demo_app.py      # from the maistorage/ root
```

> The assessment names Streamlit/Gradio only as *examples* of a demo prototype;
> this project's committed UI is Next.js. The Streamlit app exists purely as a
> resilient backup for live demos.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/ingest` | POST | Ingest corpus documents |
| `/chat` | POST | Agentic RAG with SSE streaming |
| `/trace/{id}` | GET | Agent decision trace |

## Project Structure

```
maistorage/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangGraph agent (state, nodes, prompts, graph)
│   │   ├── api/            # FastAPI endpoints (health, ingest, chat, trace)
│   │   ├── ingestion/      # Document loading, chunking, indexing
│   │   ├── providers/      # LLM providers (Gemini, Ollama, OpenAI, Groq)
│   │   ├── retrieval/      # Vectorstore, hybrid search, reranker
│   │   ├── config.py       # Settings and environment config
│   │   ├── models.py       # Pydantic schemas
│   │   └── main.py         # FastAPI app entry point
│   └── tests/              # Unit and integration tests
├── frontend/               # Next.js chat UI
├── corpus/                 # Knowledge base documents
├── eval/                   # Golden-set evaluation harness
│   ├── golden.jsonl        # 20 test questions (single-hop, multi-hop, refusal)
│   ├── metrics.py          # Hit@k, MRR, citation accuracy, refusal correctness
│   └── run.py              # Evaluation runner
├── demo_app.py             # OPTIONAL Streamlit fallback UI (not the primary frontend)
├── docs/
│   ├── PRD.md              # Product Requirements Document
│   └── DEMO.md             # 15-20 min demo script
└── .env.example            # Environment template
```

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

## Running Evaluation

```bash
cd eval
python run.py --mode baseline
python run.py --mode optimized
```

## Traditional RAG vs Agentic RAG

| Aspect | Traditional RAG | Agentic RAG |
|--------|----------------|-------------|
| Retrieval | Single pass | Multi-pass (up to 3) |
| Query handling | Direct embedding | Rewrite + optimize |
| Quality control | None | Grade each chunk |
| Out-of-scope | Hallucinate | Graceful refusal |
| Citations | Basic or none | Validated citations |
| Transparency | Black box | Full decision trace |

## Milestones

- **M1**: Infrastructure + LLM provider abstraction
- **M2**: Ingestion pipeline (load, chunk, embed, index)
- **M3**: Baseline RAG + SSE streaming
- **M4**: Citations system with validation
- **M5**: Golden-set evaluation harness (20 questions)
- **M6**: Agentic loop with LangGraph
- **M7**: Hybrid retrieval + cross-encoder reranking
- **M8**: Frontend UI + trace panel + demo polish
