import { expect, test } from "@playwright/test";
import { fillPrefs, signUp } from "./helpers";

// 006 follow-up F11 (UI-FR-02): a fresh New trip has no dates, people or budget.

test("a fresh New trip starts with empty dates, people and budget", async ({ page }) => {
  await signUp(page);
  const start = page.getByLabel("Start date", { exact: true });
  const end = page.getByLabel(/^End date/);
  const people = page.getByLabel("People", { exact: true });
  const budget = page.getByLabel("Budget (₹)", { exact: true });
  for (const f of [start, end, people, budget]) await expect(f).toHaveValue("");
  await expect(budget).not.toHaveAttribute("placeholder", /.+/);
  await expect(page.locator('label[for="f-end_date"]')).toHaveText("End date");            // no day count
  await expect(start).toHaveAttribute("min", /^\d{4}-\d{2}-\d{2}$/);                      // picker limits kept
  await expect(start).toHaveAttribute("max", /^\d{4}-\d{2}-\d{2}$/);

  // only the cities and preferences chosen: submitting shows all four messages and focuses the first
  await page.getByLabel("From", { exact: true }).selectOption({ label: "Delhi" });
  await page.getByLabel("To", { exact: true }).selectOption({ label: "Agra" });
  await fillPrefs(page);
  let posted = false;
  page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith("/trips")) posted = true; });
  await page.getByRole("button", { name: "Plan my trip" }).click();
  for (const m of ["Choose a start date.", "Choose an end date.", "Enter how many people are going (1–6).", "Enter your budget."])
    await expect(page.getByText(m, { exact: true })).toBeVisible();
  await expect(start).toBeFocused();
  for (const f of [start, end, people, budget]) await expect(f).toHaveAttribute("aria-invalid", "true");
  expect(posted).toBe(false);
});
