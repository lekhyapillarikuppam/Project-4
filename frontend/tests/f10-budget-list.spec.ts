import { expect, test } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, signUp } from "./helpers";

// 006 follow-up F10 (UI-FR-02, UI-FR-06): an empty budget to start; My Trips lists only trips with a plan, newest first.

test("an empty budget is blocked with its message", async ({ page }) => {
  await signUp(page);
  const budget = page.getByLabel("Budget (₹)", { exact: true });
  await expect(budget).toHaveValue("");
  await expect(budget).toHaveAttribute("placeholder", "e.g. 30000");
  await fillTrip(page, { from: "Delhi", to: "Agra", start: isoInDays(30), end: isoInDays(32), people: "2" });
  await fillPrefs(page);
  let posted = false;
  page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith("/trips")) posted = true; });
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByText("Enter your budget.", { exact: true })).toBeVisible();
  await expect(budget).toBeFocused();
  await expect(budget).toHaveAttribute("aria-invalid", "true");
  expect(posted).toBe(false);
  await budget.fill("30000");                                                // per person works the same way
  await page.getByRole("radio", { name: "Per person" }).click();
  await page.getByLabel("Budget (₹)", { exact: true }).fill("");
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByText("Enter your budget.", { exact: true })).toBeVisible();
});

test("My Trips: no infeasible trips, newest first", async ({ page }) => {
  await signUp(page);
  const plan = async (o: Parameters<typeof fillTrip>[1]) => {
    await page.goto("/new");
    await fillTrip(page, o);
    await fillPrefs(page);
    await page.getByRole("button", { name: "Plan my trip" }).click();
  };
  // first trip (later start date), then a second one created after it (earlier start date)
  await plan({ from: "Delhi", to: "Agra", start: isoInDays(60), end: isoInDays(62), people: "2", budget: "30000", name: "First made" });
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  await plan({ from: "Delhi", to: "Jaipur", start: isoInDays(20), end: isoInDays(22), people: "2", budget: "40000", name: "Second made" });
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  // an infeasible one: the screen with Edit budget still works right after planning
  await plan({ from: "Bengaluru", to: "Delhi", start: isoInDays(40), end: isoInDays(43), people: "2", budget: "4000", name: "Too cheap" });
  await expect(page.getByText("No plan fits this trip yet")).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit budget" })).toBeVisible();
  const infeasibleUrl = page.url();

  await page.getByRole("link", { name: "My Trips" }).click();
  const list = page.getByRole("tabpanel");
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(list.getByRole("heading", { level: 2 })).toHaveText(["Second made", "First made"]);   // newest first
  await expect(list.getByText("Too cheap")).toHaveCount(0);
  await expect(list.getByText("No plan fits yet")).toHaveCount(0);

  await page.goto(infeasibleUrl);                                            // still opens by URL
  await expect(page.getByText("No plan fits this trip yet")).toBeVisible();
});
