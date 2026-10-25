import { defineConfig, devices } from "@playwright/test";

// UI acceptance tests (006 UI-AT-01–09). Starts the API on schema app_e2e_test and the Vite dev server.
export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:5173", trace: "off", screenshot: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn api.main:app --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      env: { DB_SCHEMA: "app_e2e_test", APP_ENV: "development", GROQ_API_KEY: "" },   // no Groq in UI tests: AI parts show their fallbacks
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npx vite --port 5173",
      url: "http://localhost:5173",
      env: { VITE_API_URL: "http://localhost:8000" },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
