"use client";

import { useState, useEffect } from "react";
import { fetchTrace, TraceStep } from "@/lib/stream";

interface TracePanelProps {
  traceId: string;
}

const NODE_COLORS: Record<string, string> = {
  safety: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
  route: "bg-purple-100 text-purple-800 dark:bg-purple-500/15 dark:text-purple-300",
  rewrite: "bg-yellow-100 text-yellow-800 dark:bg-yellow-500/15 dark:text-yellow-300",
  retrieve: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300",
  search: "bg-blue-100 text-blue-800 dark:bg-blue-500/15 dark:text-blue-300",
  rerank: "bg-indigo-100 text-indigo-800 dark:bg-indigo-500/15 dark:text-indigo-300",
  grade: "bg-green-100 text-green-800 dark:bg-green-500/15 dark:text-green-300",
  decide: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  generate: "bg-teal-100 text-teal-800 dark:bg-teal-500/15 dark:text-teal-300",
  refuse: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
};

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
        className="text-xs font-medium text-sage-500 hover:text-sage-700 hover:underline dark:text-sage-400 dark:hover:text-sage-200"
      >
        {isOpen ? "Hide" : "Show"} agent trace
      </button>
      {isOpen && (
        <div className="mt-2 rounded-lg border border-sage-100 bg-sage-50/60 p-3 dark:border-sage-800 dark:bg-sage-900/60">
          {loading ? (
            <div className="text-sm text-sage-400">Loading trace…</div>
          ) : steps.length === 0 ? (
            <div className="text-sm text-sage-400">No trace data</div>
          ) : (
            <div className="space-y-2">
              {steps.map((step, i) => (
                <div key={i} className="flex gap-2 text-sm">
                  <span
                    className={`whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium ${
                      NODE_COLORS[step.node] || "bg-sage-100 text-sage-800 dark:bg-sage-800 dark:text-sage-200"
                    }`}
                  >
                    {step.node}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-sage-500 dark:text-sage-400" title={step.input}>
                      In: {step.input.substring(0, 120)}
                    </div>
                    <div className="truncate text-sage-700 dark:text-sage-300" title={step.output}>
                      Out: {step.output.substring(0, 120)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
