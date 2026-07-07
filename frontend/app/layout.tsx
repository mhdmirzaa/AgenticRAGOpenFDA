import "./globals.css";
import { IBM_Plex_Sans, IBM_Plex_Serif, IBM_Plex_Mono } from "next/font/google";

// The IBM Plex superfamily — engineered, clinical typography (see docs/DESIGN.md).
// Self-hosted by next/font at build time: no runtime request to Google.
const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});
const serif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-serif",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata = {
  title: "Formulary — FDA Drug Reference",
  description:
    "A live clinical reference over official FDA drug labels. Agentic RAG with cited answers, a real-time assay of the agent's retrieval and self-grading, and an honest refusal when the labels don't cover it. Informational only, not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-paper text-ink-900 antialiased dark:bg-paper-dark dark:text-ink-50">
        {children}
      </body>
    </html>
  );
}
