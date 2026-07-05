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

  useEffect(() => {
    if (!highlighted) return;
    ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 1400);
    return () => clearTimeout(t);
  }, [highlighted, nonce]);

  return (
    <div
      ref={ref}
      data-testid="evidence-chunk"
      data-chunk-id={chunk.chunk_id}
      data-grade={chunk.grade}
      data-highlighted={highlighted ? "true" : "false"}
      style={{ animationDelay: `${Math.min(index, 6) * 45}ms` }}
      className={`animate-fade-in-up rounded-xl border border-l-4 p-3 transition-shadow ${
        flash ? "animate-highlight-flash" : ""
      } ${
        highlighted
          ? "border-sage-400 border-l-sage-500 ring-2 ring-sage-400/70 dark:border-sage-500"
          : pass
          ? "border-sage-100 border-l-emerald-400 dark:border-sage-800 dark:border-l-emerald-500/70"
          : "border-sage-100 border-l-sage-200 opacity-70 dark:border-sage-800 dark:border-l-sage-700"
      } bg-white dark:bg-sage-900`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold capitalize text-sage-900 dark:text-sage-100">
            {chunk.source}
          </div>
          <div className="truncate text-xs text-sage-500 dark:text-sage-400">
            {chunk.section_title || chunk.section}
          </div>
        </div>
        <span
          data-testid="grade-badge"
          className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${
            pass
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
              : "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300"
          }`}
        >
          {pass ? "✓ Pass" : "✗ Fail"}
        </span>
      </div>
      <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-sage-700 dark:text-sage-300">
        {chunk.text}
      </p>
      {chunk.source_url && (
        <a
          href={chunk.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-xs font-medium text-sage-600 hover:underline dark:text-sage-300"
        >
          FDA label ↗
        </a>
      )}
    </div>
  );
}
