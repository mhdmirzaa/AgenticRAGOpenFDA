"use client";

import type { EvidenceChunk, StageEvent } from "@/lib/stream";
import StageTimeline from "./StageTimeline";
import EvidenceChunkCard from "./EvidenceChunkCard";

interface EvidencePanelProps {
  stages: StageEvent[];
  chunks: EvidenceChunk[];
  live: boolean;
  hasActivity: boolean;
  highlightedChunkId: string | null;
  highlightNonce: number;
  corpusCount: number | null;
}

export default function EvidencePanel({
  stages,
  chunks,
  live,
  hasActivity,
  highlightedChunkId,
  highlightNonce,
  corpusCount,
}: EvidencePanelProps) {
  const passCount = chunks.filter((c) => c.grade === "PASS").length;
  const failCount = chunks.length - passCount;

  return (
    <section
      data-testid="evidence-panel"
      className="flex h-full flex-col overflow-hidden rounded-3xl border border-ink-100 bg-paper-sunken dark:border-ink-800 dark:bg-paper-dark"
    >
      {/* Header — a friendly live indicator */}
      <div className="flex items-center justify-between gap-2 border-b border-ink-100 bg-paper-raised px-4 py-3 dark:border-ink-800 dark:bg-paper-dark-raised">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className={`h-2.5 w-2.5 rounded-full ${
              live ? "bg-emerald-500 animate-pulse-dot" : "bg-ink-300 dark:bg-ink-600"
            }`}
          />
          <h2 className="font-display text-sm font-semibold text-ink-900 dark:text-ink-100">
            How we found this
          </h2>
        </div>
        <span
          data-testid="corpus-indicator"
          className="rounded-full bg-emerald-50 px-2.5 py-1 text-[0.68rem] font-semibold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300"
        >
          {corpusCount == null
            ? "connecting…"
            : `${corpusCount.toLocaleString()} chunks · grows daily`}
        </span>
      </div>

      <div className="soft-scroll flex-1 space-y-5 overflow-y-auto p-4">
        {!hasActivity && chunks.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-4 text-center">
            <div
              aria-hidden
              className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-xl text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400"
            >
              🔎
            </div>
            <p className="max-w-[15rem] text-sm leading-relaxed text-ink-500 dark:text-ink-400">
              Ask a question and watch it work — safety, scope, retrieval, and
              self-grading appear here live, then settle into the exact FDA-label
              evidence behind the answer.
            </p>
          </div>
        ) : (
          <>
            {hasActivity && (
              <div>
                <h3 className="label-mono mb-3 text-ink-400 dark:text-ink-500">
                  The trail
                </h3>
                <StageTimeline stages={stages} live={live} />
              </div>
            )}

            {chunks.length > 0 && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="label-mono text-ink-400 dark:text-ink-500">
                    Evidence
                  </h3>
                  <div className="flex items-center gap-1.5">
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[0.68rem] font-bold text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300">
                      {passCount} kept
                    </span>
                    {failCount > 0 && (
                      <span className="rounded-full bg-ink-100 px-2 py-0.5 text-[0.68rem] font-semibold text-ink-500 dark:bg-ink-800 dark:text-ink-400">
                        {failCount} filtered
                      </span>
                    )}
                  </div>
                </div>
                <div className="space-y-2.5">
                  {chunks.map((chunk, i) => (
                    <EvidenceChunkCard
                      key={chunk.chunk_id || i}
                      chunk={chunk}
                      index={i}
                      highlighted={highlightedChunkId === chunk.chunk_id}
                      nonce={highlightNonce}
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
