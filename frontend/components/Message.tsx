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

  // Citation markers [n] become tappable chips that jump to the evidence chunk.
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
            title={
              cit
                ? `Jump to evidence: ${cit.source} · ${cit.section_title || cit.section}`
                : undefined
            }
            className="mx-0.5 inline-flex items-center justify-center rounded-lg bg-emerald-100 px-1.5 py-px align-baseline text-[0.72rem] font-semibold text-emerald-700 transition-colors hover:bg-emerald-200 disabled:cursor-default disabled:opacity-60 dark:bg-emerald-500/20 dark:text-emerald-300 dark:hover:bg-emerald-500/30"
          >
            {num}
          </button>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          data-testid="user-message"
          className="max-w-[85%] rounded-2xl rounded-br-md bg-emerald-500 px-4 py-2.5 text-[0.92rem] leading-relaxed text-white shadow-card"
        >
          <span className="whitespace-pre-wrap">{content}</span>
        </div>
      </div>
    );
  }

  // Assistant: a soft card keyed by state (answer / declined / blocked).
  const tone = isBlocked
    ? "border-danger-200 bg-danger-50 dark:border-danger-500/30 dark:bg-danger-500/10"
    : isRefusal
    ? "border-caution-200 bg-caution-50 dark:border-caution-500/30 dark:bg-caution-500/10"
    : "border-ink-100 bg-paper-raised dark:border-ink-800 dark:bg-paper-dark-raised";

  return (
    <div className="flex justify-start">
      <div
        data-testid="assistant-message"
        className={`max-w-[88%] rounded-2xl rounded-bl-md border px-4 py-3 shadow-card ${tone}`}
      >
        {isBlocked && (
          <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-danger-600 dark:text-danger-300">
            <span aria-hidden>🛡️</span> Kept safe
          </div>
        )}
        {isRefusal && !isBlocked && (
          <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-caution-700 dark:text-caution-300">
            <span aria-hidden>🍃</span> Not in the labels I have
          </div>
        )}
        <div
          className={
            isBlocked
              ? "whitespace-pre-wrap text-sm leading-relaxed text-danger-900 dark:text-danger-200"
              : isRefusal
              ? "whitespace-pre-wrap text-sm leading-relaxed text-caution-900 dark:text-caution-200"
              : "answer-prose whitespace-pre-wrap text-ink-800 dark:text-ink-100"
          }
        >
          {renderContent(content)}
          {streaming && <span className="stream-caret" aria-hidden />}
        </div>
      </div>
    </div>
  );
}
