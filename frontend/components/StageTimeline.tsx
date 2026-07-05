"use client";

import type { StageEvent } from "@/lib/stream";

type RowStatus = "pending" | "active" | "done" | "skipped";

interface StageTimelineProps {
  /** Accumulated stage events for the current turn, in arrival order. */
  stages: StageEvent[];
  /** True while the turn is still streaming (keeps the terminal node pulsing). */
  live: boolean;
}

const PIPELINE: { key: string; label: string; icon: string }[] = [
  { key: "safety", label: "Safety check", icon: "🛡️" },
  { key: "route", label: "Route question", icon: "🧭" },
  { key: "search", label: "Search labels", icon: "🔎" },
  { key: "grade", label: "Grade evidence", icon: "⚖️" },
  { key: "decide", label: "Decide", icon: "🤔" },
];

function StageRow({
  icon,
  label,
  detail,
  status,
  tone = "sage",
  testId,
  stageKey,
}: {
  icon: string;
  label: string;
  detail?: string;
  status: RowStatus;
  tone?: "sage" | "red" | "amber" | "teal";
  testId?: string;
  stageKey?: string;
}) {
  const toneRing =
    tone === "red"
      ? "border-red-400 bg-red-100 text-red-600 dark:bg-red-500/20 dark:text-red-300"
      : tone === "amber"
      ? "border-amber-400 bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-300"
      : tone === "teal"
      ? "border-teal-400 bg-teal-100 text-teal-600 dark:bg-teal-500/20 dark:text-teal-300"
      : "border-sage-400 bg-sage-100 text-sage-600 dark:bg-sage-500/20 dark:text-sage-300";

  return (
    <li
      data-testid={testId}
      data-stage={stageKey}
      data-status={status}
      className={`flex items-start gap-3 ${status === "skipped" ? "opacity-40" : ""}`}
    >
      <div className="relative mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center">
        {status === "active" && (
          <span
            className={`absolute inset-0 rounded-full ${
              tone === "red" ? "bg-red-400" : tone === "amber" ? "bg-amber-400" : "bg-sage-400"
            } animate-pulse-ring`}
          />
        )}
        <span
          className={`relative flex h-7 w-7 items-center justify-center rounded-full border text-xs ${
            status === "done" || status === "active"
              ? toneRing
              : "border-dashed border-sage-300 bg-transparent text-sage-400 dark:border-sage-700 dark:text-sage-600"
          }`}
        >
          {status === "done" ? "✓" : status === "skipped" ? "–" : icon}
        </span>
      </div>
      <div className="min-w-0 flex-1 pb-3">
        <div
          className={`text-sm font-semibold ${
            status === "pending"
              ? "text-sage-400 dark:text-sage-600"
              : "text-sage-900 dark:text-sage-100"
          } ${status === "active" ? "animate-pulse" : ""}`}
        >
          {label}
        </div>
        {detail && status !== "pending" && status !== "skipped" && (
          <div className="mt-0.5 text-xs text-sage-600 dark:text-sage-400">{detail}</div>
        )}
      </div>
    </li>
  );
}

export default function StageTimeline({ stages, live }: StageTimelineProps) {
  // Latest event per stage wins (active → done).
  const byStage = new Map<string, StageEvent>();
  for (const e of stages) byStage.set(e.stage, e);

  const blocked = byStage.get("blocked");
  const refused = byStage.get("refuse");
  const generate = byStage.get("generate");
  const terminalReached = !!(blocked || refused || generate);

  const rowStatus = (key: string): RowStatus => {
    const e = byStage.get(key);
    if (e) return e.status === "done" ? "done" : "active";
    // No event yet: pending while live/early, skipped once a terminal fired.
    return terminalReached ? "skipped" : "pending";
  };

  return (
    <ol data-testid="stage-timeline" className="relative">
      {PIPELINE.map((s) => (
        <StageRow
          key={s.key}
          stageKey={s.key}
          testId="stage-row"
          icon={s.icon}
          label={s.label}
          status={rowStatus(s.key)}
          detail={byStage.get(s.key)?.detail}
        />
      ))}

      {blocked && (
        <StageRow
          testId="terminal-blocked"
          stageKey="blocked"
          icon="🛑"
          label="Safety check → blocked"
          tone="red"
          status={blocked.status === "done" ? "done" : "active"}
          detail={blocked.detail || "This request was blocked to keep you safe."}
        />
      )}
      {refused && !blocked && (
        <StageRow
          testId="terminal-refuse"
          stageKey="refuse"
          icon="⚠️"
          label="Not enough evidence → declined"
          tone="amber"
          status={refused.status === "done" ? "done" : "active"}
          detail={refused.detail || "The indexed FDA labels don't cover this."}
        />
      )}
      {generate && !blocked && !refused && (
        <StageRow
          testId="terminal-generate"
          stageKey="generate"
          icon="✍️"
          label="Writing answer"
          tone="teal"
          status={generate.status === "done" || !live ? "done" : "active"}
          detail={generate.detail || "Composing a cited answer from graded evidence."}
        />
      )}
    </ol>
  );
}
