# Format B — Phase-by-phase prompts (M1–M8)

Paste one block per milestone. After each, Claude stops at a checkpoint; review, then paste the next. This gives you clean fallback points — if you run out of time, whatever milestone you last completed is a coherent deliverable (demo-safe from M3 onward).

Each prompt assumes `.claude/skills/` and `docs/PRD.md` are present. Reference the relevant domain skill explicitly.

---

## M1 — Infra + scaffold
```
Read docs/PRD.md sections 4 and 9, STRUCTURE.md (the file tree is already scaffolded with stub files — fill them in, don't recreate the layout), and the llm-provider skill. Complete the project skeleton for MaiStorage:
- backend/ (FastAPI), frontend/ (Next.js + TS), eval/, corpus/, chroma_db/ (gitignored).
- Python venv + requirements (fastapi, uvicorn, langgraph, chromadb, httpx, sentence-transformers, rank-bm25, pytest).
- A provider-agnostic LLM layer selected by LLM_PROVIDER (default gemini; ollama fallback). A /health endpoint and a startup warm-up (throwaway generate+embed) plus a Chroma check.
- A README with exact run commands.
Do NOT build retrieval yet. Verify /health returns green with Ollama running, then STOP and report.
```

## M2 — Ingestion
```
Use the rag-agentic skill (Step 1–2) and llm-provider skill. Build the ingestion pipeline:
- Generate the synthetic company-handbook corpus from the PRD (leave policy, public holidays, product specs, FAQ; include one multi-hop fact spanning leave policy + public holidays; include material that some questions genuinely cannot answer).
- Structure-aware chunking (~512 tokens, ~64 overlap, split on headings, never mid-table).
- Embed chunks via the configured provider (text-embedding-005 or nomic-embed-text); upsert into Chroma with metadata (source, section, chunk_id).
- POST /api/ingest to (re)build the index; persist to disk.
Write unit tests for chunking + upsert (mock the embed call). Verify the index builds and a raw similarity query returns sensible chunks, then STOP and report.
```

## M3 — Baseline RAG + streaming  ⟵ first demo-safe point
```
Use fastapi-streaming + llm-provider skills. Build single-pass RAG (NO agent loop yet):
- Retrieve top-k from Chroma for a question, stuff into prompt, generate.
- Stream the answer token-by-token over SSE from POST /api/chat, following the event contract in the fastapi-streaming skill (token/done/error).
- curl must show incremental data: lines.
Write a test that asserts streaming yields multiple chunks. Verify end-to-end with a known question, then STOP and report. This is your first fallback demo.
```

## M4 — Citations (bonus 1)
```
Use rag-agentic (Step 5) + nextjs-chat-ui skills. Add citations:
- Tag chunks with [chunk_id] in the generation prompt; instruct inline citation per claim.
- Post-validate: drop any citation not matching a retrieved chunk_id.
- The done event carries citations [{marker, source, section, chunk_id, text}].
- Build the Next.js chat UI: stream tokens live, render inline [n] markers, clickable citations that expand the source chunk.
Test citation-accuracy (cited chunk actually contains support). Verify in the browser end-to-end, then STOP and report.
```

## M5 — Golden set + metrics (test deliverable)
```
Use the rag-eval-goldenset skill. Build the eval harness:
- eval/golden.jsonl with 15–30 pairs incl. multi-hop and unanswerable questions.
- eval/run.py computing Hit@1/3/5, MRR, faithfulness (local LLM judge), citation accuracy.
- --mode baseline flag (current single-pass system).
Run it, commit golden.jsonl, output a metrics report. Identify which questions are demo-safe (pass). STOP and report the baseline numbers.
```

## M6 — Agentic loop (core requirement)
```
Use the rag-agentic skill (Steps 3–6) in full. Convert single-pass into a LangGraph agent:
- State + nodes: route, rewrite, retrieve, grade (binary per chunk), decide, generate/refuse.
- HARD iteration cap of 3. Only graded chunks reach generation. Empty graded set → refuse.
- Populate a trace of every decision; serve GET /api/trace/{id}.
Write agent tests asserting: re-retrieval happens on a hard question, refusal happens on an unanswerable one, loop terminates. Re-run eval (still --mode baseline vs the loop) and confirm no regression. STOP and report.
```

## M7 — Optimize: hybrid + rerank (bonus 2)
```
Use rag-agentic (retrieve/rerank) + rag-eval-goldenset skills. Add:
- Hybrid retrieval: dense (Ollama+Chroma) + BM25 keyword, merged.
- Local cross-encoder reranker over merged candidates; keep top-n.
- Caching of embeddings/results for performance.
Add --mode optimized to eval/run.py. Run BOTH modes on the SAME golden set and generate the before/after table programmatically (docs/metrics.md). STOP and report the delta.
```

## M8 — Polish + trace view + demo prep
```
Use nextjs-chat-ui skill. Finish:
- Retrieval trace panel in the UI (query rewrites, retrieved ids, rerank order, per-chunk grades, decision), loaded from /api/trace/{id}.
- Clear refusal state in the UI.
- docker-compose or a single run script; update README.
- A docs/DEMO.md walking the 15–20 min script from the PRD, listing the exact demo-safe questions (incl. one multi-hop and one refusal).
Run sp-verification-before-completion across the whole system and the full test suite. STOP and report readiness.
```
