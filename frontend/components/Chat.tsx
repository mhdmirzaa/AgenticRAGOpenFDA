"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  streamChat,
  triggerFdaIngest,
  fetchHealth,
  createSession,
  fetchMessages,
  Citation,
} from "@/lib/stream";
import Message from "./Message";
import Citations from "./Citations";
import TracePanel from "./TracePanel";
import Disclaimer from "./Disclaimer";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  traceId?: string;
  isRefusal?: boolean;
}

const SESSION_KEY = "maistorage_session_id";

const EXAMPLES = [
  "What are the warnings for ibuprofen?",
  "What is the dosage for amoxicillin?",
  "What are the contraindications of warfarin?",
];

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState<string>("Checking...");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Backend health / index status.
  useEffect(() => {
    fetchHealth()
      .then((h) => {
        const chromaDocs = h.chroma?.documents ?? 0;
        setStatus(chromaDocs > 0 ? `Ready (${chromaDocs} label chunks)` : "No labels indexed");
      })
      .catch(() => setStatus("Backend offline"));
  }, []);

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
  }, [isStreaming]);

  const handleIngest = async () => {
    setStatus("Fetching FDA labels...");
    try {
      const result = await triggerFdaIngest();
      setStatus(
        `Indexed ${result.chunks_indexed} chunks from ${result.labels_indexed} labels`
      );
    } catch (e: any) {
      setStatus(`FDA ingest failed: ${e.message}`);
    }
  };

  const send = async (question: string) => {
    if (!question.trim() || isStreaming) return;
    setInput("");
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
      (token) => patchLastAssistant((last) => ({ ...last, content: last.content + token })),
      (citations, traceId, refused) => {
        patchLastAssistant((last) => ({
          ...last,
          citations,
          traceId,
          isRefusal: refused || last.content.toLowerCase().includes("cannot answer"),
        }));
        setIsStreaming(false);
      },
      (errorMsg) => {
        patchLastAssistant((last) => ({ ...last, content: `Error: ${errorMsg}` }));
        setIsStreaming(false);
      },
      sessionId
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input.trim());
  };

  return (
    <div className="space-y-3">
      <Disclaimer />

      <div className="flex flex-col h-[calc(100vh-16rem)]">
        {/* Status bar */}
        <div className="flex items-center justify-between px-4 py-2 bg-white border rounded-t-lg">
          <span className="text-sm text-gray-600">Status: {status}</span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleNewChat}
              disabled={isStreaming}
              className="text-sm px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-50"
            >
              New chat
            </button>
            <button
              onClick={handleIngest}
              className="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Fetch FDA Labels
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white border-x">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-16">
              <p className="text-lg">Ask about an FDA-approved drug</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {EXAMPLES.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="text-sm px-3 py-1.5 border rounded-full text-gray-600 hover:bg-gray-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i}>
              <Message role={msg.role} content={msg.content} isRefusal={msg.isRefusal} />
              {msg.citations && msg.citations.length > 0 && (
                <Citations citations={msg.citations} />
              )}
              {msg.traceId && <TracePanel traceId={msg.traceId} />}
            </div>
          ))}
          {isStreaming && (
            <div className="flex items-center space-x-2 text-gray-400">
              <div className="animate-pulse">Thinking...</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex border rounded-b-lg bg-white">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a drug's warnings, dosage, interactions..."
            className="flex-1 px-4 py-3 outline-none"
            disabled={isStreaming}
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="px-6 py-3 bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 rounded-br-lg"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
