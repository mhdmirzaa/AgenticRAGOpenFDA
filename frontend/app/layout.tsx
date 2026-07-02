import "./globals.css";

export const metadata = {
  title: "MaiStorage Agentic RAG",
  description: "An agentic RAG system with self-grading retrieval and citations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  );
}
