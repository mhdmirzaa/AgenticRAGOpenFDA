"use client";

import type { StageEvent } from "@/lib/stream";

type RowStatus = "pending" | "active" | "done" | "skipped";

interface StageTimelineProps {
  /** Accumulated stage events for the current turn, in arrival order. */
  stages: StageEvent[];
  /** True while the turn is still streaming (keeps the terminal node live). */
  live: boolean;
}

// The real, ordered agent pipeline — a numbered sequence is honest here.
const PIPELINE: { key: string; label: string }[] = [
  { key: "safety", label: "Safety" },
  { key: "route", label: "Route" },
  { key: "scope", label: "Scope" },
  { key: "search", label: "Search" },
  { key: "grade", label: "Grade" },
  { key: "decide", label: "Decide" },
];

/** Status glyph — a precise instrument mark, not an emoji. */
function StatusMark({ status, tone }: { status: RowStatus; tone: "ink" | "danger" | "caution" | "cobalt" }) {
  if (status === "active") {
    return (
      <span className="relative flex h-2.5 w-2.5 items-center justify-center" aria-hidden>
        <span className="absolute h-2.5 w-2.5 rounded-full bg-cyan-500 animate-led-pulse" />
      </span>
    );
  }
  const toneClass =
    tone === "danger"
      ? "text-danger-500"
      : tone === "caution"
      ? "text-caution-600 dark:text-caution-400"
      : tone === "cobalt"
      ? "text-cobalt-600 dark:text-cobalt-300"
      : "text-cyan-600 dark:text-cyan-400";
  return (
    <span
      aria-hidden
      className={`flex h-2.5 w-2.5 items-center justify-center text-[0.7rem] leading-none ${
        status === "done" ? toneClass : "text-ink-300 dark:text-ink-600"
      }`}
    >
      {status === "done" ? "✓" : status === "skipped" ? "–" : "·"}
    </span>
  );
}

function Row({
  index,
  label,
  status,
  detail,
  stageKey,
  tone = "ink",
  testId = "stage-row",
  terminal = false,
}: {
  index?: string;
  label: string;
  status: RowStatus;
  detail?: string;
  stageKey: string;
  tone?: "ink" | "danger" | "caution" | "cobalt";
  testId?: string;
  terminal?: boolean;
}) {
  const dim = status === "pending" || status === "skipped";
  const labelColor = terminal
    ? tone === "danger"
      ? "text-danger-700 dark:text-danger-300"
      : tone === "caution"
      ? "text-caution-700 dark:text-caution-300"
      : "text-cobalt-700 dark:text-cobalt-200"
    : dim
    ? "text-ink-400 dark:text-ink-600"
    : "text-ink-800 dark:text-ink-100";

  const bandBg =
    terminal && tone === "danger"
      ? "bg-danger-50 dark:bg-danger-500/10"
      : terminal && tone === "caution"
      ? "bg-caution-50 dark:bg-caution-400/10"
      : terminal
      ? "bg-cobalt-50 dark:bg-cobalt-400/10"
      : "";

  // Special-case the Scope readout: render its resolved drug as a reference tag.
  const scopeValue =
    stageKey === "scope" && detail?.startsWith("Scope:")
      ? detail.replace(/^Scope:\s*/, "")
      : null;

  return (
    <li
      data-testid={testId}
      data-stage={stageKey}
      data-status={status}
      className={`relative flex items-center gap-2.5 overflow-hidden px-3 py-2 ${bandBg} ${
        status === "active" ? "animate-row-in" : ""
      } ${dim ? "opacity-55" : ""}`}
    >
      {status === "active" && (
        <span aria-hidden className="scan-line pointer-events-none absolute inset-0 animate-scan" />
      )}
      <span className="w-5 shrink-0 text-right font-mono text-[0.7rem] tabular-nums text-ink-300 dark:text-ink-600">
        {index}
      </span>
      <StatusMark status={status} tone={tone} />
      <span className={`label-mono w-16 shrink-0 ${labelColor}`}>{label}</span>
      <span className="min-w-0 flex-1 truncate font-mono text-[0.72rem] text-ink-500 dark:text-ink-400">
        {scopeValue ? (
          <span className="rounded-sm bg-cobalt-100 px-1.5 py-0.5 text-cobalt-700 dark:bg-cobalt-400/20 dark:text-cobalt-200">
            {scopeValue}
          </span>
        ) : status === "pending" ? (
          ""
        ) : (
          detail
        )}
      </span>
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
    return terminalReached ? "skipped" : "pending";
  };

  return (
    <ol
      data-testid="stage-timeline"
      className="divide-y divide-ink-100 overflow-hidden rounded-md border border-ink-100 bg-paper-sunken dark:divide-ink-800 dark:border-ink-800 dark:bg-paper-dark-sunken"
    >
      {PIPELINE.map((s, i) => (
        <Row
          key={s.key}
          stageKey={s.key}
          index={String(i + 1).padStart(2, "0")}
          label={s.label}
          status={rowStatus(s.key)}
          detail={byStage.get(s.key)?.detail}
        />
      ))}

      {blocked && (
        <Row
          testId="terminal-blocked"
          stageKey="blocked"
          label="Blocked"
          tone="danger"
          terminal
          status={blocked.status === "done" ? "done" : "active"}
          detail={blocked.detail || "Request blocked to keep you safe."}
        />
      )}
      {refused && !blocked && (
        <Row
          testId="terminal-refuse"
          stageKey="refuse"
          label="Declined"
          tone="caution"
          terminal
          status={refused.status === "done" ? "done" : "active"}
          detail={refused.detail || "The indexed FDA labels don't cover this."}
        />
      )}
      {generate && !blocked && !refused && (
        <Row
          testId="terminal-generate"
          stageKey="generate"
          label="Compose"
          tone="cobalt"
          terminal
          status={generate.status === "done" || !live ? "done" : "active"}
          detail={generate.detail || "Composing a cited answer from graded evidence."}
        />
      )}
    </ol>
  );
}
