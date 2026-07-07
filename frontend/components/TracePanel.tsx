"use client";

import { useState, useEffect } from "react";
import { fetchTrace, TraceStep } from "@/lib/stream";

interface TracePanelProps {
  traceId: string;
}

// Two terminal nodes carry weight (a refusal is worth seeing); everything else
// reads in one quiet ink tag — an instrument log, not a rainbow.
const NODE_TONE: Record<string, string> = {
  refuse: "bg-danger-100 text-danger-700 dark:bg-danger-500/15 dark:text-danger-300",
  generate: "bg-cobalt-100 text-cobalt-700 dark:bg-cobalt-400/20 dark:text-cobalt-200",
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
        className="label-mono text-ink-400 hover:text-ink-600 hover:underline dark:text-ink-500 dark:hover:text-ink-200"
      >
        {isOpen ? "Hide" : "Show"} agent trace
      </button>
      {isOpen && (
        <div className="mt-2 rounded-md border border-ink-100 bg-paper-sunken p-3 dark:border-ink-800 dark:bg-paper-dark-sunken">
          {loading ? (
            <div className="label-mono text-ink-400">loading trace…</div>
          ) : steps.length === 0 ? (
            <div className="label-mono text-ink-400">no trace data</div>
          ) : (
            <ol className="space-y-2">
              {steps.map((step, i) => (
                <li key={i} className="flex gap-2 text-sm">
                  <span
                    className={`label-mono h-fit whitespace-nowrap rounded-sm px-1.5 py-0.5 ${
                      NODE_TONE[step.node] || NODE_DEFAULT
                    }`}
                  >
                    {step.node}
                  </span>
                  <div className="min-w-0 font-mono text-[0.72rem]">
                    <div className="truncate text-ink-400 dark:text-ink-500" title={step.input}>
                      in&nbsp; {step.input.substring(0, 120)}
                    </div>
                    <div className="truncate text-ink-700 dark:text-ink-300" title={step.output}>
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
