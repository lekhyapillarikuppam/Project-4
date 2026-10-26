import { defineConfig, devices } from "@playwright/test";

// 008 live checks (DEP-AT-01) against the deployed app: no local servers, real Groq.
//   npx playwright test -c playwright.live.config.ts
// LIVE_URL overrides the Vercel URL. Each run signs up one new live-check-…@example.com user on the production API.
export default defineConfig({
  testDir: "./tests-live",
  timeout: 180_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: process.env.LIVE_URL ?? "https://tripwise-inky.vercel.app", trace: "off", screenshot: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
