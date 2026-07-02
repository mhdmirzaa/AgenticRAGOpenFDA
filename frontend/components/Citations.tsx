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
        {expanded.size > 0 ? "Hide" : "Show"} Citations ({citations.length})
      </button>
      <div className="mt-1 space-y-1">
        {citations.map((cit) => (
          <div key={cit.marker} className="border rounded p-2 bg-gray-50">
            <button
              onClick={() => toggle(cit.marker)}
              className="flex items-center gap-2 text-sm w-full text-left"
            >
              <span className="font-semibold text-blue-700">{cit.marker}</span>
              <span className="text-gray-600">
                {cit.source} &gt; {cit.section}
              </span>
            </button>
            {expanded.has(cit.marker) && (
              <div className="mt-2 text-sm text-gray-700 bg-white p-2 rounded border">
                {cit.text}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
