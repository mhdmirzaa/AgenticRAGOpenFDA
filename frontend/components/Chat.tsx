"use client";

import { useState, useRef, useEffect } from "react";
import { streamChat, triggerIngest, fetchHealth, Citation } from "@/lib/stream";
import Message from "./Message";
import Citations from "./Citations";
import TracePanel from "./TracePanel";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  traceId?: string;
  isRefusal?: boolean;
}

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState<string>("Checking...");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHealth()
      .then((h) => {
        const chromaDocs = h.chroma?.documents ?? 0;
        setStatus(chromaDocs > 0 ? `Ready (${chromaDocs} chunks)` : "No documents indexed");
      })
      .catch(() => setStatus("Backend offline"));
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleIngest = async () => {
    setStatus("Ingesting...");
    try {
      const result = await triggerIngest();
      setStatus(`Indexed ${result.chunks_indexed} chunks`);
    } catch (e: any) {
      setStatus(`Ingest failed: ${e.message}`);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setIsStreaming(true);

    // Add empty assistant message to stream into
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    // IMPORTANT: these state updaters must be PURE — never mutate the existing
    // message objects in `prev`. React Strict Mode invokes updaters twice in
    // dev; an impure `last.content += token` would then append each token twice
    // and render every word doubled. We always return new arrays/objects.
    const patchLastAssistant = (
      patch: (last: ChatMessage) => ChatMessage
    ) =>
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return [...prev.slice(0, -1), patch(last)];
      });

    await streamChat(
      question,
      (token) => {
        patchLastAssistant((last) => ({ ...last, content: last.content + token }));
      },
      (citations, traceId, refused) => {
        patchLastAssistant((last) => ({
          ...last,
          citations,
          traceId,
          // Prefer the explicit `refused` flag from the done event, with a
          // text-based fallback for safety.
          isRefusal: refused || last.content.toLowerCase().includes("cannot answer"),
        }));
        setIsStreaming(false);
      },
      (errorMsg) => {
        patchLastAssistant((last) => ({ ...last, content: `Error: ${errorMsg}` }));
        setIsStreaming(false);
      }
    );
  };

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)]">
      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border rounded-t-lg">
        <span className="text-sm text-gray-600">Status: {status}</span>
        <button
          onClick={handleIngest}
          className="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Ingest Corpus
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white border-x">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-lg">Ask a question about MaiStorage</p>
            <p className="text-sm mt-2">
              Try: &quot;How many annual leave days do full-time staff get?&quot;
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i}>
            <Message
              role={msg.role}
              content={msg.content}
              isRefusal={msg.isRefusal}
            />
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
          placeholder="Ask a question..."
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
  );
}
