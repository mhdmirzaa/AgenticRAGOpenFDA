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
      className="flex h-full flex-col overflow-hidden rounded-lg border border-ink-200 bg-paper-sunken dark:border-ink-800 dark:bg-paper-dark"
    >
      {/* Instrument header — an assay readout with a live LED. */}
      <div className="flex items-center justify-between gap-2 border-b border-ink-200 bg-paper-raised px-4 py-2.5 dark:border-ink-800 dark:bg-paper-dark-raised">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className={`h-2 w-2 rounded-full ${
              live
                ? "bg-cyan-500 animate-led-pulse"
                : "bg-ink-300 dark:bg-ink-600"
            }`}
          />
          <span className="label-mono text-ink-700 dark:text-ink-200">Assay</span>
          <span className="label-mono text-ink-400 dark:text-ink-500">
            {live ? "reading" : "idle"}
          </span>
        </div>
        <span
          data-testid="corpus-indicator"
          className="label-mono text-ink-500 dark:text-ink-400"
        >
          {corpusCount == null
            ? "corpus offline"
            : `${corpusCount.toLocaleString()} chunks`}
        </span>
      </div>

      <div className="soft-scroll flex-1 space-y-4 overflow-y-auto p-4">
        {!hasActivity && chunks.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-4 text-center">
            <div
              aria-hidden
              className="mb-3 flex h-11 w-11 items-center justify-center rounded-md border border-ink-200 font-mono text-lg text-ink-400 dark:border-ink-700 dark:text-ink-500"
            >
              ≣
            </div>
            <p className="max-w-[15rem] text-sm leading-relaxed text-ink-500 dark:text-ink-400">
              The assay runs here. Ask a question and watch each step — safety,
              scope, retrieval, self-grading — resolve in real time, then settle
              into the exact FDA-label citations behind the answer.
            </p>
          </div>
        ) : (
          <>
            {hasActivity && (
              <div>
                <h3 className="label-mono mb-2 text-ink-400 dark:text-ink-500">
                  Retrieval assay
                </h3>
                <StageTimeline stages={stages} live={live} />
              </div>
            )}

            {chunks.length > 0 && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="label-mono text-ink-400 dark:text-ink-500">
                    Monograph citations
                  </h3>
                  <div className="flex items-center gap-1.5">
                    <span className="label-mono rounded-sm bg-cyan-100 px-1.5 py-0.5 text-cyan-800 dark:bg-cyan-500/20 dark:text-cyan-200">
                      {passCount} kept
                    </span>
                    {failCount > 0 && (
                      <span className="label-mono rounded-sm bg-ink-100 px-1.5 py-0.5 text-ink-500 dark:bg-ink-800 dark:text-ink-400">
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
