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

  // Citation markers [n] become tappable reference chips that jump to the
  // matching monograph citation in the instrument panel.
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
            className="mx-0.5 inline-flex items-center justify-center rounded-sm bg-cobalt-100 px-1 py-px align-baseline font-mono text-[0.7rem] font-medium text-cobalt-700 transition-colors hover:bg-cobalt-200 disabled:cursor-default disabled:opacity-60 dark:bg-cobalt-400/20 dark:text-cobalt-200 dark:hover:bg-cobalt-400/30"
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
          className="max-w-[85%] rounded-lg rounded-br-sm bg-cobalt-600 px-4 py-2.5 text-[0.9rem] leading-relaxed text-white shadow-card"
        >
          <span className="whitespace-pre-wrap">{content}</span>
        </div>
      </div>
    );
  }

  // Assistant: a monograph card, keyed by state (answer / refusal / blocked).
  const tone = isBlocked
    ? "border-l-2 border-danger-500 bg-danger-50 dark:bg-danger-500/10"
    : isRefusal
    ? "border-l-2 border-caution-500 bg-caution-50 dark:bg-caution-400/10"
    : "border-l-2 border-ink-200 bg-paper-raised dark:border-ink-700 dark:bg-paper-dark-raised";

  return (
    <div className="flex justify-start">
      <div
        data-testid="assistant-message"
        className={`max-w-[88%] rounded-lg rounded-bl-sm px-4 py-3 shadow-card ${tone}`}
      >
        {isBlocked && (
          <div className="label-mono mb-2 flex items-center gap-1.5 text-danger-600 dark:text-danger-300">
            <span aria-hidden>■</span> Blocked · safety
          </div>
        )}
        {isRefusal && !isBlocked && (
          <div className="label-mono mb-2 flex items-center gap-1.5 text-caution-700 dark:text-caution-300">
            <span aria-hidden>▲</span> Declined · insufficient evidence
          </div>
        )}
        <div
          className={
            isBlocked
              ? "whitespace-pre-wrap text-sm leading-relaxed text-danger-900 dark:text-danger-200"
              : isRefusal
              ? "whitespace-pre-wrap text-sm leading-relaxed text-caution-900 dark:text-caution-200"
              : "monograph whitespace-pre-wrap text-ink-800 dark:text-ink-100"
          }
        >
          {renderContent(content)}
          {streaming && <span className="stream-caret" aria-hidden />}
        </div>
      </div>
    </div>
  );
}
