"use client";

import type { Citation } from "@/lib/stream";

interface MessageProps {
  role: "user" | "assistant";
  content: string;
  isRefusal?: boolean;
  isBlocked?: boolean;
  streaming?: boolean;
  citations?: Citation[];
  /** Called with a chunk_id when a [n] citation chip is clicked. */
  onCitationClick?: (chunkId: string) => void;
}

const normalizeMarker = (m: string) => m.replace(/[[\]]/g, "").trim();

export default function Message({
  role,
  content,
  isRefusal,
  isBlocked,
  streaming,
  citations,
  onCitationClick,
}: MessageProps) {
  const isUser = role === "user";

  // Highlight citation markers [n] and, when we know the citation, make them
  // tappable chips that jump to the matching evidence chunk on the right.
  const renderContent = (text: string) => {
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      if (/^\[\d+\]$/.test(part)) {
        const num = normalizeMarker(part);
        const cit = citations?.find((c) => normalizeMarker(c.marker) === num);
        return (
          <button
            key={i}
            type="button"
            data-testid="citation-chip"
            data-chunk-id={cit?.chunk_id}
            disabled={!cit || !onCitationClick}
            onClick={() => cit && onCitationClick?.(cit.chunk_id)}
            title={cit ? `Jump to evidence: ${cit.source} · ${cit.section_title || cit.section}` : undefined}
            className="mx-0.5 inline-flex items-center justify-center rounded-md bg-sage-200 px-1.5 py-0.5 align-baseline text-xs font-semibold text-sage-800 transition hover:bg-sage-300 disabled:cursor-default disabled:opacity-70 dark:bg-sage-700/70 dark:text-sage-100 dark:hover:bg-sage-600"
          >
            {part}
          </button>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  const bubble = isUser
    ? "bg-sage-600 text-white rounded-br-sm"
    : isBlocked
    ? "bg-red-50 border border-red-200 text-red-900 rounded-bl-sm dark:bg-red-500/10 dark:border-red-500/40 dark:text-red-200"
    : isRefusal
    ? "bg-amber-50 border border-amber-200 text-amber-900 rounded-bl-sm dark:bg-amber-500/10 dark:border-amber-500/40 dark:text-amber-200"
    : "bg-white border border-sage-100 text-sage-900 rounded-bl-sm dark:bg-sage-900 dark:border-sage-800 dark:text-sage-50";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        data-testid={isUser ? "user-message" : "assistant-message"}
        className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${bubble}`}
      >
        {isBlocked && (
          <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-red-600 dark:text-red-300">
            <span aria-hidden>🛑</span> Blocked for safety
          </div>
        )}
        {isRefusal && !isBlocked && (
          <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-amber-600 dark:text-amber-300">
            <span aria-hidden>⚠️</span> Insufficient evidence
          </div>
        )}
        <div className="whitespace-pre-wrap leading-relaxed">
          {isUser ? content : renderContent(content)}
          {streaming && <span className="streaming-cursor" aria-hidden />}
        </div>
      </div>
    </div>
  );
}
