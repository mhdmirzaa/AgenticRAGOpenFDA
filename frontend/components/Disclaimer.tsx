"use client";

/** Persistent medical disclaimer (domain guardrail — must stay visible). */
export default function Disclaimer() {
  return (
    <div
      role="note"
      aria-label="Medical disclaimer"
      className="flex items-start gap-2.5 rounded-md border-l-2 border-caution-500 bg-caution-50 px-4 py-2.5 text-sm text-caution-900 dark:border-caution-400 dark:bg-caution-400/10 dark:text-caution-200"
    >
      <span aria-hidden className="label-mono mt-0.5 text-caution-600 dark:text-caution-300">
        ℞ note
      </span>
      <p className="leading-snug">
        <span className="font-semibold">Informational only — not medical advice.</span>{" "}
        Answers come solely from official FDA drug-label text and may be
        incomplete. Consult a qualified healthcare professional before any medical
        decision.
      </p>
    </div>
  );
}
