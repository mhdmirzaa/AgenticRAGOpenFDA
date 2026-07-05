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
      className="flex h-full flex-col overflow-hidden rounded-2xl border border-sage-200 bg-sage-50/70 dark:border-sage-800 dark:bg-sage-900/40"
    >
      {/* Header + live corpus indicator */}
      <div className="flex items-center justify-between gap-2 border-b border-sage-200 px-4 py-3 dark:border-sage-800">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              live ? "animate-pulse bg-sage-500" : "bg-sage-300 dark:bg-sage-600"
            }`}
          />
          <h2 className="text-sm font-semibold text-sage-900 dark:text-sage-100">
            Live evidence
          </h2>
        </div>
        <span
          data-testid="corpus-indicator"
          className="rounded-full bg-sage-100 px-2.5 py-1 text-[11px] font-medium text-sage-700 dark:bg-sage-800 dark:text-sage-300"
        >
          {corpusCount == null
            ? "corpus offline"
            : `${corpusCount.toLocaleString()} label chunks · growing daily`}
        </span>
      </div>

      <div className="soft-scroll flex-1 space-y-4 overflow-y-auto p-4">
        {!hasActivity && chunks.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center text-sage-500 dark:text-sage-400">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-sage-100 text-2xl dark:bg-sage-800">
              🔬
            </div>
            <p className="max-w-[15rem] text-sm leading-relaxed">
              Ask a question and watch the assistant think — safety check,
              retrieval, and self-grading appear here in real time, then settle
              into the exact FDA-label evidence behind the answer.
            </p>
          </div>
        ) : (
          <>
            {hasActivity && (
              <div>
                <StageTimeline stages={stages} live={live} />
              </div>
            )}

            {chunks.length > 0 && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-sage-500 dark:text-sage-400">
                    Graded evidence
                  </h3>
                  <div className="flex items-center gap-1.5">
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300">
                      {passCount} passed
                    </span>
                    {failCount > 0 && (
                      <span className="rounded-full bg-sage-100 px-2 py-0.5 text-[11px] font-medium text-sage-500 dark:bg-sage-800 dark:text-sage-400">
                        {failCount} filtered
                      </span>
                    )}
                  </div>
                </div>
                <div className="space-y-2">
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
