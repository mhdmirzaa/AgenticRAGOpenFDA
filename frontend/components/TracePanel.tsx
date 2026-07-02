"use client";

import { useState, useEffect } from "react";
import { fetchTrace, TraceStep } from "@/lib/stream";

interface TracePanelProps {
  traceId: string;
}

const NODE_COLORS: Record<string, string> = {
  route: "bg-purple-100 text-purple-800",
  rewrite: "bg-yellow-100 text-yellow-800",
  retrieve: "bg-blue-100 text-blue-800",
  rerank: "bg-indigo-100 text-indigo-800",
  grade: "bg-green-100 text-green-800",
  decide: "bg-orange-100 text-orange-800",
  generate: "bg-teal-100 text-teal-800",
  refuse: "bg-red-100 text-red-800",
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
    <div className="ml-4 mt-1 mb-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-sm font-medium text-gray-500 hover:text-gray-700 hover:underline"
      >
        {isOpen ? "Hide" : "Show"} Agent Trace
      </button>
      {isOpen && (
        <div className="mt-2 border rounded bg-gray-50 p-3">
          {loading ? (
            <div className="text-sm text-gray-400">Loading trace...</div>
          ) : steps.length === 0 ? (
            <div className="text-sm text-gray-400">No trace data</div>
          ) : (
            <div className="space-y-2">
              {steps.map((step, i) => (
                <div key={i} className="flex gap-2 text-sm">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${
                      NODE_COLORS[step.node] || "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {step.node}
                  </span>
                  <div className="min-w-0">
                    <div className="text-gray-500 truncate" title={step.input}>
                      In: {step.input.substring(0, 120)}
                    </div>
                    <div className="text-gray-700 truncate" title={step.output}>
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
