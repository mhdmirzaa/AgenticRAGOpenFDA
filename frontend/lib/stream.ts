/**
 * SSE consumption + backend API client.
 * FDA drug-information assistant: streaming answers, citations (drug + label
 * section + source URL), agent trace, and chat sessions/history.
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function streamChat(
  question: string,
  onToken: (text: string) => void,
  onDone: (citations: Citation[], traceId: string, refused: boolean) => void,
  onError?: (message: string) => void,
  sessionId?: string | null
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId ?? undefined }),
  });

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
        if (evt.type === "token") {
          onToken(evt.text);
        } else if (evt.type === "done") {
          onDone(evt.citations || [], evt.trace_id || "", evt.refused === true);
        } else if (evt.type === "error") {
          onError?.(evt.message || "Unknown error");
        }
      } catch {
        // skip malformed JSON
      }
    }
  }
}

export async function fetchTrace(traceId: string): Promise<{ trace_id: string; steps: TraceStep[] }> {
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

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
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
