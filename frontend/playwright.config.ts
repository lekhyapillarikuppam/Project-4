import { defineConfig, devices } from "@playwright/test";

// UI acceptance tests (006 UI-AT-01–09). Starts the API on schema app_e2e_test and the Vite dev server.
export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  // en-IN: date inputs read dd-mm-yyyy, so keyboard-typed dates (UI-AT-08) don't depend on the machine's locale
  use: { baseURL: "http://localhost:5173", trace: "off", screenshot: "off", locale: "en-IN", timezoneId: "Asia/Kolkata" },
  // every spec at 1280 px and at 360 px (UI-FR-08); specs that set their own viewport keep it
  projects: [
    { name: "chromium-1280", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
    { name: "chromium-360", use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 800 } } },
  ],
  webServer: [
    {
      command: "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn api.main:app --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      // No Groq in UI tests (AI parts show their fallbacks) unless E2E_LIVE_GROQ=1 runs the live chat spec.
      env: { DB_SCHEMA: "app_e2e_test", APP_ENV: "development", ...(process.env.E2E_LIVE_GROQ ? {} : { GROQ_API_KEY: "" }) },
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
