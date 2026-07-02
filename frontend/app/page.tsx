"use client";

import Chat from "@/components/Chat";

export default function Page() {
  return (
    <main className="max-w-4xl mx-auto py-8 px-4">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-900">MaiStorage Agentic RAG</h1>
        <p className="text-gray-600 mt-2">
          Ask questions about MaiStorage policies, products, and procedures
        </p>
      </header>
      <Chat />
    </main>
  );
}
