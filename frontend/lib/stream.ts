/**
 * SSE consumption + backend API client.
 * FDA drug-information assistant: streaming answers, live agent stages,
 * graded evidence, citations (drug + label section + source URL),
 * agent trace, and chat sessions/history.
 */

export interface Citation {
  marker: string;
  source: string;        // drug name (FDA) or filename
  section: string;       // label section slug, e.g. "warnings"
  chunk_id: string;
  text: string;
  source_url?: string;   // DailyMed / FDA label URL
  section_title?: string; // human-readable section, e.g. "Warnings"
}

/** A live pipeline-stage event, emitted as the agent runs. */
export interface StageEvent {
  stage: string;                 // safety | route | search | grade | decide | generate | refuse | blocked
  status: "active" | "done";
  detail?: string;
}

/** A retrieved-and-graded evidence chunk, emitted once after grading. */
export interface EvidenceChunk {
  chunk_id: string;
  source: string;                // drug name
  section: string;               // section slug
  section_title?: string;        // human-readable section
  text: string;
  source_url?: string;
  grade: "PASS" | "FAIL";
}

export interface TraceStep {
  node: string;
  input: string;
  output: string;
}

export interface StoredMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  trace_id: string | null;
  created_at: string | null;
}

/** Callback bag for a streaming /chat turn. */
export interface StreamChatHandlers {
  onToken: (text: string) => void;
  onDone: (
    citations: Citation[],
    traceId: string,
    refused: boolean,
    blocked: boolean
  ) => void;
  onStage?: (stage: StageEvent) => void;
  onEvidence?: (chunks: EvidenceChunk[]) => void;
  onError?: (message: string) => void;
}

export interface StreamChatOptions {
  sessionId?: string | null;
  optimized?: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Stream a /chat turn, surfacing live pipeline stages + graded evidence
 * alongside answer tokens. `optimized` defaults to true (agentic path).
 */
export async function streamChat(
  question: string,
  handlers: StreamChatHandlers,
  options: StreamChatOptions = {}
): Promise<void> {
  const { onToken, onDone, onStage, onEvidence, onError } = handlers;
  const { sessionId, optimized = true } = options;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        optimized,
        session_id: sessionId ?? undefined,
      }),
    });
  } catch (e: any) {
    onError?.(e?.message || "Network error — is the backend running?");
    return;
  }

  if (!res.ok) {
    const err = await res.text();
    onError?.(err || `HTTP ${res.status}`);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const evt = JSON.parse(line.slice(6));
        switch (evt.type) {
          case "stage":
            onStage?.({
              stage: evt.stage,
              status: evt.status,
              detail: evt.detail,
            });
            break;
          case "evidence":
            onEvidence?.(evt.chunks || []);
            break;
          case "token":
            onToken(evt.text);
            break;
          case "done":
            onDone(
              evt.citations || [],
              evt.trace_id || "",
              evt.refused === true,
              evt.blocked === true
            );
            break;
          case "error":
            onError?.(evt.message || "Unknown error");
            break;
        }
      } catch {
        // skip malformed JSON
      }
    }
  }
}

export async function fetchTrace(
  traceId: string
): Promise<{ trace_id: string; steps: TraceStep[] }> {
  const res = await fetch(`${API_BASE}/trace/${traceId}`);
  if (!res.ok) throw new Error(`Trace fetch failed: ${res.status}`);
  return res.json();
}

/** Trigger openFDA ingestion (accumulates + dedupes by label_id). */
export async function triggerFdaIngest(): Promise<any> {
  const res = await fetch(`${API_BASE}/ingest/fda`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`FDA ingest failed: ${res.status}`);
  return res.json();
}

/** Grow the corpus by one incremental batch of FDA labels. */
export async function growCorpus(): Promise<{
  labels_indexed: number;
  chunks_indexed: number;
  skip_next: number;
}> {
  const res = await fetch(`${API_BASE}/ingest/fda/grow`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`Corpus growth failed: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

/**
 * Live corpus size (indexed label chunks). Reads chroma document count from
 * /health; returns null if the backend is unreachable.
 */
export async function fetchCorpusCount(): Promise<number | null> {
  try {
    const h = await fetchHealth();
    return h?.chroma?.documents ?? h?.store?.documents ?? 0;
  } catch {
    return null;
  }
}

/** Create a new chat session; returns its id (or null if persistence is down). */
export async function createSession(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/sessions`, { method: "POST" });
    if (!res.ok) return null;
    return (await res.json()).session_id ?? null;
  } catch {
    return null;
  }
}

/** Load a session's message history. */
export async function fetchMessages(sessionId: string): Promise<StoredMessage[]> {
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
    if (!res.ok) return [];
    return (await res.json()).messages ?? [];
  } catch {
    return [];
  }
}
