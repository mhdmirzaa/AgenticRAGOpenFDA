"use client";

import Chat from "@/components/Chat";
import LeafMark from "@/components/LeafMark";

// Rename the product in ONE place (see docs/DESIGN.md).
const BRAND = "Leaflet";

export default function Page() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-6 lg:px-8">
      <header className="mb-6 flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-card">
          <LeafMark className="h-6 w-6" />
        </span>
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink-900 dark:text-ink-50">
            {BRAND}
          </h1>
          <p className="text-sm text-ink-500 dark:text-ink-400">
            Your friendly guide to official FDA drug labels
          </p>
        </div>
      </header>
      <Chat />
    </main>
  );
}
