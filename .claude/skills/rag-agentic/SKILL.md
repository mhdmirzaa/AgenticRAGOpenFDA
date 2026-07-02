---
name: rag-agentic
description: "Build an agentic RAG system with LangGraph over Chroma: chunking, retrieval, self-grading, re-retrieval loops, citations, and graceful refusal. Use when building or debugging a RAG pipeline, agentic retrieval, LangGraph retrieval graph, chunking strategy, chunk grading, query rewriting, re-retrieval, RAG citations, or when retrieval returns wrong/irrelevant chunks. Triggers: 'agentic rag', 'rag pipeline', 'langgraph retrieval', 'retrieve chunks', 'chunk grading', 'query rewrite', 're-retrieve', 'rag citations', 'chroma retrieval', 'retrieval loop', 'grade relevance', 'rag refusal'."
---

# Agentic RAG (LangGraph + Chroma)

IRON LAW: The agent must never answer from chunks it graded as insufficient. Refuse instead of hallucinate. A clean "I don't have enough information" is a correct answer.

## What this skill delivers

An agentic RAG that (1) retrieves correct chunks, (2) grades its own evidence, (3) re-retrieves when weak, (4) answers with citations or refuses. This is the difference between traditional RAG (one linear pass) and agentic RAG (a loop that self-corrects).

## Workflow

```
- [ ] 1. Chunk the corpus correctly (chunking is 80% of retrieval quality)
- [ ] 2. Index into Chroma with metadata (source, section, chunk_id)
- [ ] 3. Build the LangGraph state + nodes
- [ ] 4. Wire the loop with a HARD iteration cap
- [ ] 5. Generate with inline citations OR refuse
- [ ] 6. Expose a retrieval trace for every answer
```

## Step 1: Chunking (do this right or nothing else matters)

Most "RAG retrieved garbage" bugs are chunking bugs, not model bugs.

- Token-aware chunks, ~512 tokens, ~64 overlap.
- Respect structure: never split mid-table, mid-list, or mid-section. Split on headings first, then size.
- Attach metadata to every chunk: `source` (file), `section` (heading path), `chunk_id` (stable, unique).
- Keep the raw text of each chunk retrievable by `chunk_id` — citations and the trace need it.

## Step 2: Chroma index

```python
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
col = client.get_or_create_collection("maistorage")
# embeddings come from the configured provider (see llm-provider skill), not Chroma's default
col.add(ids=ids, embeddings=vecs, documents=texts, metadatas=metas)
```

Persist to disk so re-runs don't re-embed. Chroma is local, no server — that is the point (least demo friction).

## Step 3: LangGraph state + nodes

State carries the query, working query, candidates, graded chunks, iteration count, and trace.

```python
from typing import TypedDict, List
class RagState(TypedDict):
    question: str
    query: str            # working (possibly rewritten) query
    candidates: List[dict]
    graded: List[dict]     # chunks that passed grading
    iterations: int
    answer: str
    trace: List[dict]      # every decision, for the /trace endpoint
```

Nodes (each independently testable — keep the LLM's job small per node):
- `route` — needs retrieval? (yes/no)
- `rewrite` — sharpen a vague query (skip on first pass if query is already specific)
- `retrieve` — hybrid: dense (Ollama embed → Chroma) + keyword (BM25 over same corpus), merge
- `rerank` — local cross-encoder (e.g. bge-reranker) re-orders; keep top-n
- `grade` — per chunk: "does this help answer the question? yes/no" — binary is reliable on 8B
- `decide` — enough graded chunks? → generate; else → rewrite (loop)
- `generate` — answer with citations, or refuse

## Step 4: The loop (HARD cap)

```python
MAX_ITERS = 3
def decide(state):
    if len(state["graded"]) >= 1:      # tune threshold
        return "generate"
    if state["iterations"] >= MAX_ITERS:
        return "refuse"
    return "rewrite"
```

Uncapped loops = infinite demos and latency disasters. The cap is non-negotiable.

## Step 5: Generate with citations OR refuse

- Prompt the LLM with ONLY graded chunks, each tagged `[chunk_id]`.
- Instruct: cite the `[chunk_id]` inline for each claim; if the chunks don't answer it, say so.
- Post-check: every citation must map to a real graded chunk. Drop hallucinated citations.
- Refusal path: if `decide` returned "refuse", emit a fixed "insufficient evidence" answer + the trace. Do NOT let the LLM improvise an answer here.

## Step 6: Trace

Record every node's input/output into `state["trace"]`: query rewrites, candidate ids, rerank order, per-chunk grades, final decision. Serve it from `/api/trace/{id}`. This is your strongest demo artifact — the audience *sees* the agent think.

## Anti-patterns
- ❌ Feeding ungraded candidates to `generate`. → Only graded chunks reach generation.
- ❌ Uncapped re-retrieval. → Always `MAX_ITERS`.
- ❌ Chunking by fixed character count ignoring structure. → Structure-aware first.
- ❌ Letting the LLM cite freely. → Post-validate citations against graded chunk_ids.
- ❌ Rewriting an already-specific query on pass 1. → Route/skip to save a loop.
- ❌ Answering when graded set is empty. → Refuse.

## Pre-delivery checklist
- [ ] Retrieval returns correct chunks on the golden set (see rag-eval-goldenset)
- [ ] Loop provably terminates (cap enforced)
- [ ] Every answer carries valid citations OR is an explicit refusal
- [ ] Trace populated for every request
- [ ] Grading is a separate, unit-tested function
