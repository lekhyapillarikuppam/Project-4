import { expect, test } from "@playwright/test";
import { fillTrip, isoInDays, signUp } from "./helpers";

// UI-AT-01: sign up → new trip → feasible trip shows 1–3 cards in < 8 s locally.
test("UI-AT-01 feasible trip comparison", async ({ page }) => {
  await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Agra", start: isoInDays(30), end: isoInDays(32), people: "2", budget: "30000" });
  const t0 = Date.now();
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible({ timeout: 8_000 });
  const ms = Date.now() - t0;
  const cards = await page.getByRole("button", { name: /^Choose / }).count();
  expect(cards).toBeGreaterThanOrEqual(1);
  expect(cards).toBeLessThanOrEqual(3);
  console.log(`UI-AT-01: ${cards} card(s) in ${ms} ms`);
});

// UI-AT-03: infeasible budget shows the minimum budget; Edit budget returns to the form with values kept.
test("UI-AT-03 infeasible budget", async ({ page }) => {
  await signUp(page);
  await fillTrip(page, { from: "Bengaluru", to: "Delhi", start: isoInDays(40), end: isoInDays(43), people: "2", budget: "4000" });
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByText("No plan fits this trip yet")).toBeVisible();
  await expect(page.getByText(/Minimum budget for these dates and people/)).toBeVisible();
  await page.getByRole("button", { name: "Edit budget" }).click();
  await expect(page).toHaveURL(/\/new$/);
  await expect(page.getByLabel("From", { exact: true })).toHaveValue("BLR");
  await expect(page.getByLabel("To", { exact: true })).toHaveValue("DEL");
  await expect(page.getByLabel("Start date", { exact: true })).toHaveValue(isoInDays(40));
  await expect(page.getByLabel("Budget (₹)", { exact: true })).toHaveValue("4000");
});
