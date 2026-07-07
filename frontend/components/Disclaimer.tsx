"use client";

/** Persistent medical disclaimer — warm, not a cold banner (must stay visible). */
export default function Disclaimer() {
  return (
    <div
      role="note"
      aria-label="Medical disclaimer"
      className="flex items-start gap-3 rounded-2xl border border-caution-200 bg-caution-50 px-4 py-3 text-sm text-caution-900 dark:border-caution-500/30 dark:bg-caution-500/10 dark:text-caution-200"
    >
      <span
        aria-hidden
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-caution-100 text-caution-700 dark:bg-caution-500/20 dark:text-caution-300"
      >
        ⚕
      </span>
      <p className="leading-snug">
        <span className="font-semibold">Informational only — not medical advice.</span>{" "}
        Answers come straight from official FDA drug-label text and may be
        incomplete. Please check with a pharmacist or doctor before making any
        decision about your health.
      </p>
    </div>
  );
}
