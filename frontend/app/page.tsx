"use client";

import Chat from "@/components/Chat";

export default function Page() {
  return (
    <main className="max-w-4xl mx-auto py-8 px-4">
      <header className="mb-4 text-center">
        <h1 className="text-3xl font-bold text-gray-900">
          FDA Drug Information Assistant
        </h1>
        <p className="text-gray-600 mt-2">
          Ask about FDA-approved drugs — indications, warnings, dosage, adverse
          reactions, contraindications — grounded in official FDA label text
          with citations, or a clear refusal when the labels don&apos;t cover it.
        </p>
      </header>
      <Chat />
    </main>
  );
}
