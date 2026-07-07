import "./globals.css";
import { Fraunces, Plus_Jakarta_Sans, DM_Mono } from "next/font/google";
import Providers from "./providers";

// "Leaflet" type system (see docs/DESIGN.md). Self-hosted by next/font at build:
// no runtime request to Google. Fraunces (editorial display) + Plus Jakarta Sans
// (friendly body) + DM Mono (technical data).
const display = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});
const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});
const mono = DM_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata = {
  title: "Leaflet — your FDA drug companion",
  description:
    "A warm, human guide to official FDA drug labels. Ask about any drug — indications, warnings, dosage, interactions — and see exactly how the cited answer is found. Informational only, not medical advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${display.variable} ${sans.variable} ${mono.variable}`}
    >
      <body className="min-h-screen bg-paper text-ink-900 antialiased dark:bg-paper-dark dark:text-ink-50">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
