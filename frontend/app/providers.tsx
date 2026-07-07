"use client";

import { ThemeProvider } from "next-themes";

/**
 * Theme provider — LIGHT is the default on a fresh load (the developer's original
 * emerald-on-white spec). The header toggle flips to dark and the choice persists
 * (localStorage); next-themes injects a blocking script so there's no flash of the
 * wrong theme on load. System preference is intentionally NOT auto-applied, so the
 * first load is deterministically light.
 */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      {children}
    </ThemeProvider>
  );
}
