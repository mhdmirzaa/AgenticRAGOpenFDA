import "./globals.css";

export const metadata = {
  title: "FDA Drug Information Assistant",
  description:
    "Agentic RAG over official FDA drug labels — cited answers, self-grading retrieval, and graceful refusal. Informational only, not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  );
}
