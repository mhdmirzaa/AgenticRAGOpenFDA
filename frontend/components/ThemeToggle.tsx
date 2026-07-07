"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className="h-5 w-5">
      <circle cx="12" cy="12" r="4" fill="currentColor" />
      <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" />
      </g>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className="h-5 w-5">
      <path
        d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"
        fill="currentColor"
      />
    </svg>
  );
}

/** Clean light/dark switch. Default is light; the choice persists (next-themes). */
export default function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={mounted ? `Switch to ${isDark ? "light" : "dark"} theme` : "Toggle theme"}
      title={mounted ? `Switch to ${isDark ? "light" : "dark"} theme` : "Toggle theme"}
      className="flex h-10 w-10 items-center justify-center rounded-2xl border border-ink-200 bg-paper-raised text-ink-600 shadow-card transition-colors hover:border-emerald-300 hover:text-emerald-600 dark:border-ink-700 dark:bg-paper-dark-raised dark:text-ink-300 dark:hover:border-emerald-500/50 dark:hover:text-emerald-400"
    >
      {mounted ? (isDark ? <SunIcon /> : <MoonIcon />) : <span className="h-5 w-5" />}
    </button>
  );
}
