"use client";

import { useEffect, useRef, useState } from "react";
import type { EvidenceChunk } from "@/lib/stream";

interface EvidenceChunkCardProps {
  chunk: EvidenceChunk;
  index: number;
  highlighted: boolean;
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

  const edge = highlighted
    ? "border-emerald-400 ring-2 ring-emerald-300/70"
    : pass
    ? "border-emerald-100 dark:border-emerald-500/20"
    : "border-ink-100 opacity-70 dark:border-ink-800";

  return (
    <div
      ref={ref}
      data-testid="evidence-chunk"
      data-chunk-id={chunk.chunk_id}
      data-grade={chunk.grade}
      data-highlighted={highlighted ? "true" : "false"}
      style={{ animationDelay: `${Math.min(index, 6) * 55}ms` }}
      className={`animate-rise-in rounded-2xl border bg-paper-raised p-3 shadow-card transition-colors dark:bg-paper-dark-raised ${
        flash ? "animate-flash-cite" : ""
      } ${edge}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold capitalize text-ink-900 dark:text-ink-100">
            {chunk.source}
          </div>
          <div className="truncate font-mono text-[0.7rem] uppercase tracking-label text-ink-500 dark:text-ink-400">
            {section}
          </div>
        </div>
        <span
          data-testid="grade-badge"
          className={`shrink-0 rounded-full px-2 py-0.5 text-[0.68rem] font-bold ${
            pass
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
              : "bg-ink-100 text-ink-500 dark:bg-ink-800 dark:text-ink-400"
          }`}
        >
          {pass ? "✓ Kept" : "Filtered"}
        </span>
      </div>
      <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-ink-600 dark:text-ink-300">
        {chunk.text}
      </p>
      {chunk.source_url && (
        <a
          href={chunk.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-xs font-semibold text-emerald-600 hover:underline dark:text-emerald-400"
        >
          Open FDA label ↗
        </a>
      )}
    </div>
  );
}
