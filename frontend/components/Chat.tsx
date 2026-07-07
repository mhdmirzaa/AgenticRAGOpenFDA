"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  streamChat,
  triggerFdaIngest,
  growCorpus,
  fetchCorpusCount,
  createSession,
  fetchMessages,
  Citation,
  EvidenceChunk,
  StageEvent,
} from "@/lib/stream";
import Message from "./Message";
import Citations from "./Citations";
import TracePanel from "./TracePanel";
import Disclaimer from "./Disclaimer";
import EvidencePanel from "./EvidencePanel";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  traceId?: string;
  isRefusal?: boolean;
  isBlocked?: boolean;
}

const SESSION_KEY = "maistorage_session_id";

const EXAMPLES = [
  "What are the warnings for ibuprofen?",
  "What is the dosage for amoxicillin?",
  "What are the contraindications of warfarin?",
];

const toolbarBtn =
  "rounded-md border border-ink-200 px-2.5 py-1 font-mono text-[0.7rem] font-medium text-ink-600 transition-colors hover:border-ink-300 hover:bg-paper-sunken disabled:opacity-50 dark:border-ink-700 dark:text-ink-300 dark:hover:bg-ink-800";

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [corpusCount, setCorpusCount] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Current-turn live evidence state (drives the right-hand instrument panel).
  const [stages, setStages] = useState<StageEvent[]>([]);
  const [evidence, setEvidence] = useState<EvidenceChunk[]>([]);
  const [highlightedChunkId, setHighlightedChunkId] = useState<string | null>(null);
  const [highlightNonce, setHighlightNonce] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const refreshCorpus = useCallback(() => {
    fetchCorpusCount().then(setCorpusCount);
  }, []);

  // Live corpus size.
  useEffect(() => {
    refreshCorpus();
  }, [refreshCorpus]);

  // Restore or create a session, then load its history on mount.
  useEffect(() => {
    (async () => {
      let sid = typeof window !== "undefined" ? localStorage.getItem(SESSION_KEY) : null;
      if (sid) {
        const history = await fetchMessages(sid);
        if (history.length > 0) {
          setMessages(
            history.map((m) => ({
              role: m.role,
              content: m.content,
              citations: m.citations,
              traceId: m.trace_id ?? undefined,
              isRefusal:
                m.role === "assistant" &&
                m.content.toLowerCase().includes("cannot answer"),
            }))
          );
        }
      } else {
        sid = await createSession();
        if (sid) localStorage.setItem(SESSION_KEY, sid);
      }
      setSessionId(sid);
    })();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(scrollToBottom, [messages]);

  const handleNewChat = useCallback(async () => {
    if (isStreaming) return;
    const sid = await createSession();
    if (sid && typeof window !== "undefined") localStorage.setItem(SESSION_KEY, sid);
    setSessionId(sid);
    setMessages([]);
    setStages([]);
    setEvidence([]);
    setHighlightedChunkId(null);
    setStatusText(null);
  }, [isStreaming]);

  const handleIngest = async () => {
    setStatusText("Fetching FDA labels…");
    try {
      const result = await triggerFdaIngest();
      setStatusText(
        `Indexed ${result.chunks_indexed} chunks from ${result.labels_indexed} labels`
      );
      refreshCorpus();
    } catch (e: any) {
      setStatusText(`Couldn't fetch FDA labels — ${e.message}. Check the backend is running.`);
    }
  };

  const handleGrow = async () => {
    setStatusText("Growing the corpus…");
    try {
      const result = await growCorpus();
      setStatusText(
        `Grew by ${result.chunks_indexed} chunks from ${result.labels_indexed} labels`
      );
      refreshCorpus();
    } catch (e: any) {
      setStatusText(`Couldn't grow the corpus — ${e.message}. Check the backend is running.`);
    }
  };

  const handleCitationClick = useCallback((chunkId: string) => {
    setHighlightedChunkId(chunkId);
    setHighlightNonce((n) => n + 1);
  }, []);

  const send = async (question: string) => {
    if (!question.trim() || isStreaming) return;
    setInput("");
    setStatusText(null);
    // Reset the live panel for the new turn.
    setStages([]);
    setEvidence([]);
    setHighlightedChunkId(null);
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setIsStreaming(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    // Pure updaters only (Strict Mode double-invokes) — never mutate prev.
    const patchLastAssistant = (patch: (last: ChatMessage) => ChatMessage) =>
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return [...prev.slice(0, -1), patch(last)];
      });

    await streamChat(
      question,
      {
        onStage: (stage) => setStages((prev) => [...prev, stage]),
        onEvidence: (chunks) => setEvidence(chunks),
        onToken: (token) =>
          patchLastAssistant((last) => ({ ...last, content: last.content + token })),
        onDone: (citations, traceId, refused, blocked) => {
          patchLastAssistant((last) => ({
            ...last,
            citations,
            traceId,
            isBlocked: blocked,
            isRefusal:
              refused || last.content.toLowerCase().includes("cannot answer"),
          }));
          setIsStreaming(false);
        },
        onError: (errorMsg) => {
          patchLastAssistant((last) => ({ ...last, content: `Error: ${errorMsg}` }));
          setIsStreaming(false);
        },
      },
      { sessionId, optimized: true }
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input.trim());
  };

  const hasActivity = isStreaming || stages.length > 0 || evidence.length > 0;

  const evidencePanel = (
    <EvidencePanel
      stages={stages}
      chunks={evidence}
      live={isStreaming}
      hasActivity={hasActivity}
      highlightedChunkId={highlightedChunkId}
      highlightNonce={highlightNonce}
      corpusCount={corpusCount}
    />
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <Disclaimer />

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(340px,27rem)]">
        {/* LEFT — conversation */}
        <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-ink-200 bg-paper-raised shadow-card dark:border-ink-800 dark:bg-paper-dark-raised">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-100 px-4 py-2.5 dark:border-ink-800">
            <span className="label-mono text-ink-500 dark:text-ink-400">
              {statusText ??
                (corpusCount == null
                  ? "connecting to backend…"
                  : `${corpusCount.toLocaleString()} FDA label chunks indexed`)}
            </span>
            <div className="flex items-center gap-1.5">
              <button onClick={handleNewChat} disabled={isStreaming} className={toolbarBtn}>
                New session
              </button>
              <button onClick={handleIngest} disabled={isStreaming} className={toolbarBtn}>
                Sync labels
              </button>
              <button
                onClick={handleGrow}
                disabled={isStreaming}
                className="rounded-md bg-cobalt-600 px-2.5 py-1 font-mono text-[0.7rem] font-semibold text-white transition-colors hover:bg-cobalt-700 disabled:opacity-50"
              >
                Grow corpus
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="soft-scroll flex-1 space-y-4 overflow-y-auto p-4">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center px-4 text-center">
                <div
                  aria-hidden
                  className="mb-4 flex h-12 w-12 items-center justify-center rounded-md border border-ink-200 font-serif text-2xl text-cobalt-600 dark:border-ink-700 dark:text-cobalt-300"
                >
                  ℞
                </div>
                <p className="font-sans text-base font-semibold text-ink-900 dark:text-ink-100">
                  Look up a drug in the FDA labels
                </p>
                <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-ink-500 dark:text-ink-400">
                  Ask about indications, warnings, dosage, or interactions. Every
                  answer is grounded in official label text, with the retrieval
                  shown as a live assay on the right.
                </p>
                <div className="mt-5 flex flex-col items-stretch gap-1.5">
                  {EXAMPLES.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      className="group flex items-center gap-2 rounded-md border border-ink-200 px-3 py-2 text-left text-sm text-ink-700 transition-colors hover:border-cobalt-400 hover:bg-cobalt-50 dark:border-ink-700 dark:text-ink-200 dark:hover:border-cobalt-400/60 dark:hover:bg-cobalt-400/10"
                    >
                      <span className="font-mono text-xs text-cobalt-500 group-hover:text-cobalt-600 dark:text-cobalt-300">
                        ▸
                      </span>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((msg, i) => {
              const isLast = i === messages.length - 1;
              return (
                <div key={i}>
                  <Message
                    role={msg.role}
                    content={msg.content}
                    isRefusal={msg.isRefusal}
                    isBlocked={msg.isBlocked}
                    streaming={isStreaming && isLast && msg.role === "assistant"}
                    citations={msg.citations}
                    onCitationClick={handleCitationClick}
                  />
                  {msg.citations && msg.citations.length > 0 && (
                    <Citations
                      citations={msg.citations}
                      onCitationClick={handleCitationClick}
                    />
                  )}
                  {msg.traceId && <TracePanel traceId={msg.traceId} />}
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 border-t border-ink-100 p-3 dark:border-ink-800"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a drug's warnings, dosage, interactions…"
              className="flex-1 rounded-md border border-ink-200 bg-paper-sunken px-3.5 py-2.5 text-sm text-ink-900 outline-none transition-colors placeholder:text-ink-400 focus:border-cobalt-400 focus:bg-paper-raised dark:border-ink-700 dark:bg-paper-dark-sunken dark:text-ink-50 dark:focus:bg-paper-dark-raised"
              disabled={isStreaming}
            />
            <button
              type="submit"
              disabled={isStreaming || !input.trim()}
              className="rounded-md bg-cobalt-600 px-5 py-2.5 font-sans text-sm font-semibold text-white transition-colors hover:bg-cobalt-700 disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </div>

        {/* RIGHT — live instrument panel */}
        <div className="h-[27rem] min-h-0 lg:h-auto">{evidencePanel}</div>
      </div>
    </div>
  );
}
