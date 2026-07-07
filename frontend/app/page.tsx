"use client";

import Chat from "@/components/Chat";

export default function Page() {
  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 lg:px-8">
      <header className="mb-5 flex items-center gap-3">
        {/* ℞ mark — the universal prescription/reference glyph, in cobalt ink. */}
        <div
          aria-hidden
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-cobalt-600 font-serif text-2xl leading-none text-white shadow-card"
        >
          ℞
        </div>
        <div className="min-w-0">
          <h1 className="font-sans text-xl font-semibold tracking-tight text-ink-900 dark:text-ink-50">
            Formulary
          </h1>
          <p className="label-mono mt-0.5 text-ink-400">
            FDA drug reference · agentic retrieval
          </p>
        </div>
      </header>
      <Chat />
    </main>
  );
}
