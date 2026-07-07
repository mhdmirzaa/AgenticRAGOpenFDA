"use client";

import LeafMark from "./LeafMark";
import Disclaimer from "./Disclaimer";

interface HubLandingProps {
  corpusCount: number | null;
  statusText: string | null;
  input: string;
  setInput: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onExample: (q: string) => void;
  onNewSession: () => void;
  onSync: () => void;
  onGrow: () => void;
  isStreaming: boolean;
  examples: string[];
}

const EXAMPLE_META: Record<string, { tag: string; icon: string }> = {
  warnings: { tag: "warnings", icon: "⚠" },
  dosage: { tag: "dosage", icon: "℞" },
  contraindications: { tag: "contraindications", icon: "⛔" },
  interactions: { tag: "interactions", icon: "⇄" },
};

function metaFor(q: string) {
  const l = q.toLowerCase();
  if (l.includes("dosage") || l.includes("dose")) return EXAMPLE_META.dosage;
  if (l.includes("contraindication")) return EXAMPLE_META.contraindications;
  if (l.includes("interact")) return EXAMPLE_META.interactions;
  return EXAMPLE_META.warnings;
}

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-paper-raised px-4 py-3.5 shadow-card dark:border-ink-800 dark:bg-paper-dark-raised">
      <div className="font-display text-2xl font-semibold text-emerald-600 dark:text-emerald-400">
        {value}
      </div>
      <div className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">{label}</div>
    </div>
  );
}

function ActionTile({
  label, hint, onClick, disabled, primary,
}: {
  label: string; hint: string; onClick: () => void; disabled?: boolean; primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`group flex flex-col items-start gap-0.5 rounded-2xl border px-4 py-3 text-left transition-all disabled:opacity-50 ${
        primary
          ? "border-emerald-500 bg-emerald-500 text-white hover:bg-emerald-600 hover:shadow-soft"
          : "border-ink-100 bg-paper-raised text-ink-800 hover:border-emerald-300 hover:shadow-card dark:border-ink-800 dark:bg-paper-dark-raised dark:text-ink-100 dark:hover:border-emerald-500/50"
      }`}
    >
      <span className="text-sm font-semibold">{label}</span>
      <span className={`text-xs ${primary ? "text-emerald-50/90" : "text-ink-500 dark:text-ink-400"}`}>
        {hint}
      </span>
    </button>
  );
}

export default function HubLanding({
  corpusCount, statusText, input, setInput, onSubmit, onExample,
  onNewSession, onSync, onGrow, isStreaming, examples,
}: HubLandingProps) {
  return (
    <div className="flex flex-col gap-6">
      {/* Hero — invitation + ask bar */}
      <section className="rounded-3xl border border-emerald-100 bg-gradient-to-br from-emerald-50 via-paper-raised to-paper-raised p-6 shadow-card dark:border-emerald-500/20 dark:from-emerald-500/10 dark:via-paper-dark-raised dark:to-paper-dark-raised sm:p-8">
        <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
          <LeafMark className="h-5 w-5" />
          <span className="label-mono">health companion</span>
        </div>
        <h2 className="mt-3 max-w-xl font-display text-2xl font-semibold leading-snug text-ink-900 dark:text-ink-50 sm:text-3xl">
          Ask about any FDA-labeled drug — and see exactly how the answer is found.
        </h2>
        <p className="mt-2 max-w-lg text-sm leading-relaxed text-ink-600 dark:text-ink-300">
          Indications, warnings, dosage, interactions — answered only from official
          label text, with citations you can open, and a live trail showing every step.
        </p>

        <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about a drug's warnings, dosage, interactions…"
            disabled={isStreaming}
            className="flex-1 rounded-2xl border border-ink-200 bg-paper-raised px-4 py-3 text-[0.95rem] text-ink-900 shadow-card outline-none transition-colors placeholder:text-ink-400 focus:border-emerald-400 dark:border-ink-700 dark:bg-paper-dark-raised dark:text-ink-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="rounded-2xl bg-emerald-500 px-6 py-3 font-semibold text-white shadow-card transition-all hover:bg-emerald-600 hover:shadow-soft disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </section>

      {/* Stat tiles */}
      <section className="grid grid-cols-3 gap-3">
        <StatTile
          value={corpusCount == null ? "—" : corpusCount.toLocaleString()}
          label="label chunks indexed"
        />
        <StatTile value="Daily" label="openFDA sync" />
        <StatTile value="100%" label="answers cited to labels" />
      </section>

      {/* Quick actions */}
      <section>
        <h3 className="label-mono mb-2 text-ink-600 dark:text-ink-400">Quick actions</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <ActionTile label="New session" hint="Start a fresh conversation"
            onClick={onNewSession} disabled={isStreaming} />
          <ActionTile label="Sync labels" hint="Fetch the latest FDA labels"
            onClick={onSync} disabled={isStreaming} />
          <ActionTile label="Grow corpus" hint="Add a new batch of drugs" primary
            onClick={onGrow} disabled={isStreaming} />
        </div>
        {statusText && (
          <p className="mt-2 text-xs text-ink-500 dark:text-ink-400">{statusText}</p>
        )}
      </section>

      {/* Example questions */}
      <section>
        <h3 className="label-mono mb-2 text-ink-600 dark:text-ink-400">Try asking</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {examples.map((q) => {
            const m = metaFor(q);
            return (
              <button
                key={q}
                onClick={() => onExample(q)}
                disabled={isStreaming}
                className="group flex flex-col gap-2 rounded-2xl border border-ink-100 bg-paper-raised p-4 text-left shadow-card transition-all hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-soft disabled:opacity-50 dark:border-ink-800 dark:bg-paper-dark-raised dark:hover:border-emerald-500/50"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400">
                  <span aria-hidden>{m.icon}</span>
                </span>
                <span className="text-sm font-medium leading-snug text-ink-800 dark:text-ink-100">
                  {q}
                </span>
                <span className="label-mono text-emerald-600/80 dark:text-emerald-400/80">
                  {m.tag}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <Disclaimer />
    </div>
  );
}
