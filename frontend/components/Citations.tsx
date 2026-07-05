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

  return (
    <div className="ml-1 mt-2">
      <button
        onClick={() =>
          setExpanded(expanded.size > 0 ? new Set() : new Set(citations.map((c) => c.marker)))
        }
        className="text-xs font-medium text-sage-600 hover:underline dark:text-sage-300"
      >
        {expanded.size > 0 ? "Hide" : "Show"} sources ({citations.length})
      </button>
      <div className="mt-1 space-y-1">
        {citations.map((cit) => {
          const section = cit.section_title || cit.section;
          return (
            <div
              key={cit.marker}
              className="rounded-lg border border-sage-100 bg-sage-50/60 p-2 dark:border-sage-800 dark:bg-sage-900/60"
            >
              <div className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => {
                    toggle(cit.marker);
                    onCitationClick?.(cit.chunk_id);
                  }}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                >
                  <span className="font-semibold text-sage-700 dark:text-sage-300">
                    {cit.marker}
                  </span>
                  <span className="truncate font-medium capitalize text-sage-900 dark:text-sage-100">
                    {cit.source}
                  </span>
                  <span className="text-sage-400">·</span>
                  <span className="truncate text-sage-600 dark:text-sage-400">{section}</span>
                </button>
                {cit.source_url && (
                  <a
                    href={cit.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="whitespace-nowrap text-xs text-sage-600 hover:underline dark:text-sage-300"
                    title="View the official FDA label on DailyMed"
                  >
                    FDA label ↗
                  </a>
                )}
              </div>
              {expanded.has(cit.marker) && (
                <div className="mt-2 rounded border border-sage-100 bg-white p-2 text-sm text-sage-700 dark:border-sage-800 dark:bg-sage-950 dark:text-sage-300">
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
