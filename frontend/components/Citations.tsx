"use client";

import { useState } from "react";
import type { Citation } from "@/lib/stream";

interface CitationsProps {
  citations: Citation[];
  onCitationClick?: (chunkId: string) => void;
}

export default function Citations({ citations, onCitationClick }: CitationsProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (!citations.length) return null;

  const toggle = (marker: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(marker)) next.delete(marker);
      else next.add(marker);
      return next;
    });
  };

  const allOpen = expanded.size > 0;

  return (
    <div className="ml-1 mt-2">
      <button
        onClick={() => setExpanded(allOpen ? new Set() : new Set(citations.map((c) => c.marker)))}
        className="label-mono text-cobalt-600 hover:underline dark:text-cobalt-300"
      >
        {allOpen ? "Hide" : "Show"} sources · {citations.length}
      </button>
      <div className="mt-1.5 space-y-1">
        {citations.map((cit) => {
          const section = cit.section_title || cit.section;
          const open = expanded.has(cit.marker);
          return (
            <div
              key={cit.marker}
              className="rounded-md border border-ink-100 bg-paper-sunken px-2 py-1.5 dark:border-ink-800 dark:bg-paper-dark-sunken"
            >
              <div className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => {
                    toggle(cit.marker);
                    onCitationClick?.(cit.chunk_id);
                  }}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left font-mono text-[0.72rem]"
                >
                  <span className="font-semibold text-cobalt-600 dark:text-cobalt-300">
                    {cit.marker.replace(/[[\]]/g, "")}
                  </span>
                  <span className="truncate font-semibold uppercase tracking-label text-ink-800 dark:text-ink-100">
                    {cit.source}
                  </span>
                  <span className="text-ink-300 dark:text-ink-600">·</span>
                  <span className="truncate uppercase tracking-label text-ink-500 dark:text-ink-400">
                    {section}
                  </span>
                </button>
                {cit.source_url && (
                  <a
                    href={cit.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="whitespace-nowrap font-mono text-[0.7rem] text-cobalt-600 hover:underline dark:text-cobalt-300"
                    title="View the official FDA label on DailyMed"
                  >
                    FDA label ↗
                  </a>
                )}
              </div>
              {open && (
                <div className="mt-1.5 rounded-sm border border-ink-100 bg-paper-raised p-2 font-serif text-sm text-ink-700 dark:border-ink-800 dark:bg-paper-dark-raised dark:text-ink-300">
                  {cit.text}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
