"use client";

import type { StageEvent } from "@/lib/stream";

type RowStatus = "pending" | "active" | "done" | "skipped";

interface StageTimelineProps {
  /** Accumulated stage events for the current turn, in arrival order. */
  stages: StageEvent[];
  /** True while the turn is still streaming (keeps the terminal node live). */
  live: boolean;
}

// The real, ordered agent pipeline — a numbered trail is honest here.
const PIPELINE: { key: string; label: string; icon: string }[] = [
  { key: "safety", label: "Safety check", icon: "🛡️" },
  { key: "route", label: "Understand", icon: "🧭" },
  { key: "scope", label: "Scope to drug", icon: "🎯" },
  { key: "search", label: "Search labels", icon: "🔎" },
  { key: "grade", label: "Grade evidence", icon: "⚖️" },
  { key: "decide", label: "Decide", icon: "💭" },
];

function Dot({ status, tone }: { status: RowStatus; tone: "emerald" | "danger" | "caution" }) {
  if (status === "active") {
    return (
      <span className="relative flex h-6 w-6 items-center justify-center" aria-hidden>
        <span className="absolute h-6 w-6 rounded-full bg-emerald-400/30 animate-pulse-dot" />
        <span className="relative h-2.5 w-2.5 rounded-full bg-emerald-500" />
      </span>
    );
  }
  const ring =
    status === "done"
      ? tone === "danger"
        ? "border-danger-400 bg-danger-100 text-danger-600 dark:bg-danger-500/20 dark:text-danger-300"
        : tone === "caution"
        ? "border-caution-400 bg-caution-100 text-caution-700 dark:bg-caution-500/20 dark:text-caution-300"
        : "border-emerald-400 bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300"
      : "border-dashed border-ink-200 bg-transparent text-ink-300 dark:border-ink-700 dark:text-ink-600";
  return (
    <span
      aria-hidden
      className={`flex h-6 w-6 items-center justify-center rounded-full border text-[0.7rem] ${ring}`}
    >
      {status === "done" ? "✓" : status === "skipped" ? "–" : "·"}
    </span>
  );
}

function Row({
  label, icon, status, detail, stageKey, tone = "emerald",
  testId = "stage-row", terminal = false, connector = false,
}: {
  label: string; icon: string; status: RowStatus; detail?: string;
  stageKey: string; tone?: "emerald" | "danger" | "caution";
  testId?: string; terminal?: boolean; connector?: boolean;
}) {
  const dim = status === "pending" || status === "skipped";

  const band =
    terminal && tone === "danger"
      ? "rounded-2xl bg-danger-50 px-3 py-2 dark:bg-danger-500/10"
      : terminal && tone === "caution"
      ? "rounded-2xl bg-caution-50 px-3 py-2 dark:bg-caution-500/10"
      : terminal
      ? "rounded-2xl bg-emerald-50 px-3 py-2 dark:bg-emerald-500/10"
      : "";

  const scopeValue =
    stageKey === "scope" && detail?.startsWith("Scope:")
      ? detail.replace(/^Scope:\s*/, "")
      : null;

  return (
    <li
      data-testid={testId}
      data-stage={stageKey}
      data-status={status}
      className={`relative flex items-start gap-3 ${band} ${dim ? "opacity-50" : ""}`}
    >
      {connector && (
        <span aria-hidden className="timeline-connector absolute bottom-0 left-[11px] top-7 w-0.5 rounded-full" />
      )}
      <div className="relative z-10 mt-0.5">
        <Dot status={status} tone={tone} />
      </div>
      <div className="min-w-0 flex-1 pb-3">
        <div
          className={`text-sm font-semibold ${
            terminal
              ? tone === "danger"
                ? "text-danger-700 dark:text-danger-300"
                : tone === "caution"
                ? "text-caution-700 dark:text-caution-300"
                : "text-emerald-700 dark:text-emerald-300"
              : dim
              ? "text-ink-400 dark:text-ink-600"
              : "text-ink-900 dark:text-ink-100"
          }`}
        >
          {label}
        </div>
        {status !== "pending" && status !== "skipped" && (scopeValue || detail) && (
          <div className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">
            {scopeValue ? (
              <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-100 px-1.5 py-0.5 font-mono text-[0.7rem] text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300">
                {scopeValue}
              </span>
            ) : (
              detail
            )}
          </div>
        )}
      </div>
    </li>
  );
}

export default function StageTimeline({ stages, live }: StageTimelineProps) {
  const byStage = new Map<string, StageEvent>();
  for (const e of stages) byStage.set(e.stage, e);

  const blocked = byStage.get("blocked");
  const refused = byStage.get("refuse");
  const generate = byStage.get("generate");
  const terminalReached = !!(blocked || refused || generate);

  const rowStatus = (key: string): RowStatus => {
    const e = byStage.get(key);
    if (e) return e.status === "done" ? "done" : "active";
    return terminalReached ? "skipped" : "pending";
  };
  const hasTerminal = terminalReached;

  return (
    <ol data-testid="stage-timeline" className="relative space-y-0">
      {PIPELINE.map((s, i) => (
        <Row
          key={s.key}
          stageKey={s.key}
          icon={s.icon}
          label={s.label}
          status={rowStatus(s.key)}
          detail={byStage.get(s.key)?.detail}
          connector={i < PIPELINE.length - 1 || hasTerminal}
        />
      ))}

      {blocked && (
        <Row
          testId="terminal-blocked" stageKey="blocked" icon="🛡️" label="Kept safe"
          tone="danger" terminal
          status={blocked.status === "done" ? "done" : "active"}
          detail={blocked.detail || "This request was declined to keep you safe."}
        />
      )}
      {refused && !blocked && (
        <Row
          testId="terminal-refuse" stageKey="refuse" icon="🍃" label="Not enough in the labels"
          tone="caution" terminal
          status={refused.status === "done" ? "done" : "active"}
          detail={refused.detail || "The FDA labels I have don't cover this."}
        />
      )}
      {generate && !blocked && !refused && (
        <Row
          testId="terminal-generate" stageKey="generate" icon="✍️" label="Writing the answer"
          tone="emerald" terminal
          status={generate.status === "done" || !live ? "done" : "active"}
          detail={generate.detail || "Composing a cited answer from the evidence."}
        />
      )}
    </ol>
  );
}
