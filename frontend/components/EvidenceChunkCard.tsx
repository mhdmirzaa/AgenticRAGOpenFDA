"use client";

import { useEffect, useRef, useState } from "react";
import type { EvidenceChunk } from "@/lib/stream";

interface EvidenceChunkCardProps {
  chunk: EvidenceChunk;
  index: number;
  /** True when this chunk is the current citation-jump target. */
  highlighted: boolean;
  /** Increments on each jump request so a repeat click replays the flash/scroll. */
  nonce: number;
}

export default function EvidenceChunkCard({
  chunk,
  index,
  highlighted,
  nonce,
}: EvidenceChunkCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState(false);
  const pass = chunk.grade === "PASS";
  const section = chunk.section_title || chunk.section;

  useEffect(() => {
    if (!highlighted) return;
    ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 1400);
    return () => clearTimeout(t);
  }, [highlighted, nonce]);

  // A monograph citation: authoritative reference tag, verdict, source line.
  const edge = highlighted
    ? "border-cyan-400 ring-1 ring-cyan-400/70"
    : pass
    ? "border-ink-200 dark:border-ink-700"
    : "border-ink-100 opacity-60 dark:border-ink-800";

  return (
    <div
      ref={ref}
      data-testid="evidence-chunk"
      data-chunk-id={chunk.chunk_id}
      data-grade={chunk.grade}
      data-highlighted={highlighted ? "true" : "false"}
      style={{ animationDelay: `${Math.min(index, 6) * 45}ms` }}
      className={`animate-row-in rounded-md border bg-paper-raised p-2.5 transition-colors dark:bg-paper-dark-raised ${
        flash ? "animate-flash-cite" : ""
      } ${edge}`}
    >
      {/* Reference tag: [DRUG · SECTION] in the mono reference voice. */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 font-mono text-[0.7rem] leading-tight">
          <span className="font-semibold uppercase tracking-label text-ink-800 dark:text-ink-100">
            {chunk.source}
          </span>
          <span className="mx-1 text-ink-300 dark:text-ink-600">·</span>
          <span className="uppercase tracking-label text-ink-500 dark:text-ink-400">
            {section}
          </span>
        </div>
        <span
          data-testid="grade-badge"
          className={`label-mono shrink-0 rounded-sm px-1.5 py-0.5 ${
            pass
              ? "bg-cyan-100 text-cyan-800 dark:bg-cyan-500/20 dark:text-cyan-200"
              : "bg-ink-100 text-ink-500 dark:bg-ink-800 dark:text-ink-400"
          }`}
        >
          {pass ? "✓ pass" : "✗ filtered"}
        </span>
      </div>
      <p className="mt-2 line-clamp-4 font-serif text-xs leading-relaxed text-ink-700 dark:text-ink-300">
        {chunk.text}
      </p>
      {chunk.source_url && (
        <a
          href={chunk.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block font-mono text-[0.7rem] text-cobalt-600 hover:underline dark:text-cobalt-300"
        >
          FDA label ↗
        </a>
      )}
    </div>
  );
}
