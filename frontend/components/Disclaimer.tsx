"use client";

/** Persistent medical disclaimer (domain guardrail — must stay visible). */
export default function Disclaimer() {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <span aria-hidden className="mt-0.5 text-base">⚕️</span>
      <p>
        <span className="font-semibold">Informational only — not medical advice.</span>{" "}
        Answers are drawn solely from official FDA drug-label text and may be
        incomplete. Always consult a qualified healthcare professional before
        making any medical decision.
      </p>
    </div>
  );
}
