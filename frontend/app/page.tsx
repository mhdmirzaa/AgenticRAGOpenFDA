"use client";

import Chat from "@/components/Chat";

export default function Page() {
  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 lg:px-8">
      <header className="mb-5 flex items-center gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-sage-400 to-sage-600 text-xl shadow-sm shadow-sage-900/10">
          <span aria-hidden>🌿</span>
        </div>
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-sage-900 dark:text-sage-50">
            Verdant
          </h1>
          <p className="text-sm text-sage-700 dark:text-sage-300">
            Your calm guide to official FDA drug-label information — cited,
            self-checking, and honest when it doesn&apos;t know.
          </p>
        </div>
      </header>
      <Chat />
    </main>
  );
}
