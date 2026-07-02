# Project Structure — MaiStorage

Monorepo. Every source file is a **stub with a docstring** naming the skill it comes from and the milestone that fills it in. Claude Code implements them via the phase prompts (`commands/phases.md`) using TDD. Nothing is orphaned — each folder maps to a skill and a milestone.

```
maistorage/
├── README.md                     kit overview
├── STRUCTURE.md                  this file
├── .gitignore
├── .env.example                  provider switch + retrieval params
├── docker-compose.yml            full stack (M8)
│
├── docs/                         PRD + setup/monitoring/manifests (+ DEMO.md at M8)
├── commands/                     Claude Code prompts (3 formats)
├── .claude/skills/               59 skills (Superpowers + curated + ECC subset + domain + session-tracker)
├── corpus/                       synthetic handbook — GENERATED at M2
├── eval/                         golden set + metrics       [rag-eval-goldenset · M5/M7]
│
├── backend/                      FastAPI + LangGraph (Python, pyproject.toml)
│   └── app/
│       ├── main.py               app + CORS + warm-up       [fastapi-streaming · M1/M3]
│       ├── config.py             settings/env               [llm-provider · M1]
│       ├── models.py             schemas + SSE contract     [M3→M6]
│       ├── api/                  health,ingest,chat,trace   [fastapi-streaming · M1-M6]
│       ├── providers/            gemini/openai/groq/ollama  [llm-provider · M1]
│       ├── ingestion/            loader,chunker,indexer     [rag-agentic S1-2 · M2]
│       ├── retrieval/            vectorstore,hybrid,reranker[rag-agentic + bonus · M2/M7]
│       └── agent/                graph,state,nodes,prompts  [rag-agentic S3-6 · M6]
│   └── tests/                    chunker,indexer,agent,api  [sp-test-driven-development]
│
└── frontend/                     Next.js + TypeScript
    ├── app/                      layout,page                [nextjs-chat-ui · M4]
    ├── components/               Chat,Message,Citations,TracePanel [nextjs-chat-ui · M4/M8]
    └── lib/stream.ts             SSE fetch-reader            [nextjs-chat-ui · M4]
```

## Milestone → files touched
- **M1** infra: `config.py`, `providers/*`, `main.py`, `api/health.py`, root `.env.example`
- **M2** ingestion: `corpus/`, `ingestion/*`, `retrieval/vectorstore.py`, `api/ingest.py`, chunker/indexer tests
- **M3** baseline+stream: `api/chat.py`, `models.py`, `main.py` warm-up, `test_api.py`
- **M4** citations + UI: `agent/prompts.py` (cite), `frontend/*`
- **M5** eval: `eval/golden.jsonl`, `eval/metrics.py`, `eval/run.py --mode baseline`
- **M6** agentic loop: `agent/{state,nodes,graph,prompts}.py`, `api/trace.py`, `test_agent.py`
- **M7** optimize: `retrieval/{hybrid,reranker}.py`, `eval/run.py --mode optimized`, `docs/metrics.md`
- **M8** polish: `frontend/components/TracePanel.tsx`, `docker-compose.yml`, `docs/DEMO.md`

## How to run (after Claude Code implements)
```
# backend
cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload
# frontend
cd frontend && npm install && npm run dev
# eval
cd eval && python run.py --mode baseline
# or everything
docker compose up
```
