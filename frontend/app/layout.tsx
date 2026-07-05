import "./globals.css";

export const metadata = {
  title: "Verdant — FDA Drug Information Assistant",
  description:
    "A warm, transparent health assistant. Agentic RAG over official FDA drug labels — cited answers, live self-grading retrieval, and graceful refusal. Informational only, not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-sage-50 text-sage-950 dark:bg-sage-950 dark:text-sage-50">
        {children}
      </body>
    </html>
  );
}
