---
name: nextjs-chat-ui
description: "Build a Next.js + TypeScript chat UI that consumes an SSE stream, renders tokens live, shows inline citations, and displays a retrieval trace. Use when building a streaming chat frontend, consuming Server-Sent Events in the browser, rendering RAG citations, a chat interface in Next.js, or a retrieval trace panel. Triggers: 'nextjs chat ui', 'streaming chat frontend', 'consume sse', 'render citations', 'chat interface react', 'trace panel', 'eventsource', 'stream tokens browser', 'rag frontend'."
---

# Next.js chat UI (streaming + citations + trace)

IRON LAW: The UI must show tokens as they arrive and make citations clickable back to source. A RAG demo lives or dies on whether the audience can SEE the grounding.

## What this delivers

A Next.js (App Router) + TypeScript single-page chat that: sends a question to `/api/chat`, renders the streamed answer token-by-token, shows inline citations that expand to the source chunk, and has a collapsible retrieval-trace panel.

## Consuming the SSE stream

`EventSource` only does GET; the `/chat` endpoint is POST, so use `fetch` + a stream reader.

```typescript
async function streamChat(question: string, onToken: (t: string) => void,
                          onDone: (c: Citation[], traceId: string) => void) {
  const res = await fetch("http://localhost:8000/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const evt = JSON.parse(line.slice(6));
      if (evt.type === "token") onToken(evt.text);
      else if (evt.type === "done") onDone(evt.citations, evt.trace_id);
    }
  }
}
```

Parse exactly the event contract from the fastapi-streaming skill (`token` / `done` / `error`).

## Layout (keep it clean, not fancy)
- Message list (user right, assistant left), assistant message grows as tokens stream.
- Inline citation markers like `[1]` in the answer; a citations block below maps `[1] → source · section`, click expands the chunk text.
- Collapsible "Retrieval trace" panel: fetch `/api/trace/{id}` on the `done` event; show query rewrites, retrieved ids, rerank order, per-chunk grades, final decision.
- A visible "insufficient evidence" state when the answer is a refusal.

## State
- Keep it in React state (`useState`/`useReducer`). No browser storage needed for a single session.
- Track: messages, streaming flag, current assistant buffer, citations, trace.

## Styling
- Tailwind is fine. Prioritize legibility and the citation/trace affordances over visual flourish. A clean, readable UI scores the "user-friendly interface" bonus; a flashy broken one does not.

## Anti-patterns
- ❌ Using `EventSource` for the POST endpoint. → fetch + reader.
- ❌ Waiting for the full response before rendering. → render per token.
- ❌ Citations as plain text. → clickable, expand to source chunk.
- ❌ Hiding the trace. → it's the best demo artifact; make it one click away.
- ❌ localStorage/sessionStorage. → React state only.

## Pre-delivery checklist
- [ ] Tokens render incrementally as they stream
- [ ] Citations clickable → show source chunk
- [ ] Trace panel loads from /trace and shows the agent's decisions
- [ ] Refusal state renders clearly
- [ ] Works against the running FastAPI backend end-to-end
