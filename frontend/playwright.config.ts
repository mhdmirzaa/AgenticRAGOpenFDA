import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the FDA drug-information assistant (PRD §10.1).
 * Streaming-tolerant timeouts; retries disabled for deterministic demos.
 * Base URL comes from PLAYWRIGHT_BASE_URL, else the local dev port 3005.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 90_000, // agentic turns stream through several stages
  expect: { timeout: 30_000 },
  reporter: "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3005",
    trace: "on-first-retry",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
