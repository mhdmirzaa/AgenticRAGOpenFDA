"use client";

import { useState } from "react";
import type { Citation } from "@/lib/stream";

interface CitationsProps {
  citations: Citation[];
}

export default function Citations({ citations }: CitationsProps) {
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
    <div className="ml-4 mt-2 mb-2">
      <button
        onClick={() => setExpanded(expanded.size > 0 ? new Set() : new Set(citations.map((c) => c.marker)))}
        className="text-sm font-medium text-blue-600 hover:underline"
      >
        {expanded.size > 0 ? "Hide" : "Show"} Sources ({citations.length})
      </button>
      <div className="mt-1 space-y-1">
        {citations.map((cit) => {
          const section = cit.section_title || cit.section;
          return (
            <div key={cit.marker} className="border rounded p-2 bg-gray-50">
              <div className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => toggle(cit.marker)}
                  className="flex items-center gap-2 text-left flex-1 min-w-0"
                >
                  <span className="font-semibold text-blue-700">{cit.marker}</span>
                  <span className="text-gray-800 font-medium capitalize truncate">
                    {cit.source}
                  </span>
                  <span className="text-gray-400">·</span>
                  <span className="text-gray-600 truncate">{section}</span>
                </button>
                {cit.source_url && (
                  <a
                    href={cit.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline whitespace-nowrap"
                    title="View the official FDA label on DailyMed"
                  >
                    FDA label ↗
                  </a>
                )}
              </div>
              {expanded.has(cit.marker) && (
                <div className="mt-2 text-sm text-gray-700 bg-white p-2 rounded border">
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
