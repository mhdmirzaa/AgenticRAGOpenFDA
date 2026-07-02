/**
 * SSE consumption via fetch + reader.  [M4]
 * streamChat(question, onToken, onDone): POST /api/chat, parse SSE lines
 */

export interface Citation {
  marker: string;
  source: string;
  section: string;
  chunk_id: string;
  text: string;
}

export interface TraceStep {
  node: string;
  input: string;
  output: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function streamChat(
  question: string,
  onToken: (text: string) => void,
  onDone: (citations: Citation[], traceId: string, refused: boolean) => void,
  onError?: (message: string) => void
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
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

export async function triggerIngest(): Promise<any> {
  const res = await fetch(`${API_BASE}/ingest`, { method: "POST" });
  if (!res.ok) throw new Error(`Ingest failed: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}
