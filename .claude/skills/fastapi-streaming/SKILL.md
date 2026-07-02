---
name: fastapi-streaming
description: "Build a FastAPI backend that streams LLM output token-by-token over SSE, with async endpoints for an agentic RAG. Use when building a streaming REST endpoint, Server-Sent Events, token-by-token streaming, FastAPI SSE, async LLM endpoint, or a /chat streaming contract. Triggers: 'fastapi streaming', 'stream tokens', 'server-sent events', 'sse endpoint', 'streaming response', 'token by token', 'streaming llm api', 'async fastapi', 'stream rag answer'."
---

# FastAPI streaming (SSE)

IRON LAW: Stream the first token as early as possible. The user should see motion within seconds even while the agent is still retrieving. Never buffer the whole answer then send it at once.

## What this delivers

A FastAPI backend exposing `/ingest`, `/chat` (SSE stream), `/trace/{id}`, `/health` for the agentic RAG. The `/chat` endpoint streams the answer token-by-token plus a final citations/trace event.

## SSE streaming pattern

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, asyncio

app = FastAPI()

class ChatReq(BaseModel):
    question: str

async def event_stream(question: str):
    # agent yields tokens as they are generated
    async for token in run_agent_streaming(question):   # from rag-agentic
        yield f"data: {json.dumps({'type':'token','text':token})}\n\n"
    # final event carries citations + trace id
    yield f"data: {json.dumps({'type':'done','citations':cites,'trace_id':tid})}\n\n"

@app.post("/api/chat")
async def chat(req: ChatReq):
    return StreamingResponse(event_stream(req.question),
                             media_type="text/event-stream")
```

### Event contract (frontend depends on this)
- `{"type":"token","text":"..."}` — one token/chunk of the answer.
- `{"type":"done","citations":[...],"trace_id":"..."}` — end of stream.
- `{"type":"error","message":"..."}` — recoverable error.

Keep this contract stable; the nextjs-chat-ui skill parses exactly these.

## Async correctness
- The whole path must be `async`. A single sync/blocking call (e.g. a blocking Ollama call) stalls the event loop and kills streaming.
- Use an async Ollama client or run blocking calls in a threadpool (`asyncio.to_thread`).
- Cap concurrency if needed; a demo machine has one model instance.

## Health + warm-up
- `/health` checks: Chroma reachable, Ollama up, models pulled.
- Add a startup warm-up that sends one dummy generation so the first real request isn't cold. Cold-start is the #1 demo-latency surprise.

## CORS (Next.js dev)
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])
```

## Anti-patterns
- ❌ Returning the full answer as one JSON blob. → Stream tokens.
- ❌ Blocking model calls in an async route. → threadpool/async client.
- ❌ No warm-up. → First demo query is painfully slow.
- ❌ Changing the event shape ad hoc. → Honor the contract above.

## Pre-delivery checklist
- [ ] `/chat` streams tokens visibly (curl shows incremental `data:` lines)
- [ ] Final `done` event includes citations + trace_id
- [ ] No blocking calls on the async path
- [ ] Warm-up runs on startup
- [ ] `/health` reports model + DB status
