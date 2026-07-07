"use client";

import { useState, useEffect } from "react";
import { fetchTrace, TraceStep } from "@/lib/stream";

interface TracePanelProps {
  traceId: string;
}

// Two terminal nodes carry weight; everything else reads in one quiet tag.
const NODE_TONE: Record<string, string> = {
  refuse: "bg-danger-100 text-danger-700 dark:bg-danger-500/15 dark:text-danger-300",
  generate: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
};
const NODE_DEFAULT = "bg-ink-100 text-ink-600 dark:bg-ink-800 dark:text-ink-300";

export default function TracePanel({ traceId }: TracePanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && steps.length === 0) {
      setLoading(true);
      fetchTrace(traceId)
        .then((data) => setSteps(data.steps || []))
        .catch(() => setSteps([]))
        .finally(() => setLoading(false));
    }
  }, [isOpen, traceId, steps.length]);

  return (
    <div className="ml-1 mt-1">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-xs font-medium text-ink-400 hover:text-emerald-600 hover:underline dark:text-ink-500 dark:hover:text-emerald-400"
      >
        {isOpen ? "Hide" : "Show"} the full trail
      </button>
      {isOpen && (
        <div className="mt-2 rounded-2xl border border-ink-100 bg-paper-sunken p-3 dark:border-ink-800 dark:bg-paper-dark-sunken">
          {loading ? (
            <div className="text-sm text-ink-500">Loading…</div>
          ) : steps.length === 0 ? (
            <div className="text-sm text-ink-500">No trace data</div>
          ) : (
            <ol className="space-y-2">
              {steps.map((step, i) => (
                <li key={i} className="flex gap-2 text-sm">
                  <span
                    className={`h-fit whitespace-nowrap rounded-lg px-2 py-0.5 font-mono text-[0.68rem] ${
                      NODE_TONE[step.node] || NODE_DEFAULT
                    }`}
                  >
                    {step.node}
                  </span>
                  <div className="min-w-0 text-[0.78rem]">
                    <div className="truncate text-ink-600 dark:text-ink-400" title={step.input}>
                      in&nbsp; {step.input.substring(0, 120)}
                    </div>
                    <div className="truncate text-ink-600 dark:text-ink-300" title={step.output}>
                      out {step.output.substring(0, 120)}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
