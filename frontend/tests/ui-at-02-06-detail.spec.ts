import { expect, test, type Page } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, signUp } from "./helpers";

async function planAndChoose(page: Page) {
  await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Jaipur", start: isoInDays(35), end: isoInDays(38), people: "2", budget: "60000" });
  await fillPrefs(page);
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await page.getByRole("button", { name: /^Choose / }).first().click();
  await expect(page).toHaveURL(/\/plan$/);
  await expect(page.getByRole("heading", { name: "Day by day" })).toBeVisible();
}

// UI-AT-02: detail shows transport, hotel, every day, the map with coloured routes and a budget donut + table summing to the total.
test("UI-AT-02 plan detail", async ({ page }) => {
  await planAndChoose(page);
  await expect(page.getByRole("heading", { name: "Outbound" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Return" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hotel", exact: true })).toBeVisible();
  for (let d = 1; d <= 4; d++) await expect(page.getByRole("heading", { name: new RegExp(`^Day ${d} ·`) })).toBeVisible();
  await expect(page.getByRole("figure", { name: /Budget chart/ })).toBeVisible();
  const rows = page.locator("table").first().locator("tbody tr");
  const num = async (i: number) => Number((await rows.nth(i).locator("td").innerText()).replace(/[^\d]/g, ""));
  let sum = 0;
  for (let i = 0; i < 6; i++) sum += await num(i);
  expect(sum).toBe(await num(6));                                  // lines sum to the plan total
  expect((await num(6)) + (await num(7)) + (await num(8))).toBe(await num(9));   // total + contingency + unused = budget
  await expect(page.locator(".leaflet-container")).toBeVisible();
  const routes = page.locator(".leaflet-overlay-pane path");
  await expect(routes.first()).toBeVisible();
  const colours = new Set(await routes.evaluateAll((els) => els.map((e) => e.getAttribute("stroke"))));
  expect(colours.size).toBe(await routes.count());                // one distinct colour per day
  await expect(page.getByRole("img", { name: /^Hotel:/ })).toBeVisible();
  await expect(page.getByRole("img", { name: /^Day 1, stop 1:/ })).toBeVisible();
  await expect(page.getByText("Routes shown as straight lines")).toBeVisible();
});

// UI-AT-06: restore creates a new version; the trade-offs panel shows figures or the "limited by time" message.
test("UI-AT-06 versions and trade-offs", async ({ page }) => {
  await planAndChoose(page);
  await page.getByRole("button", { name: /Show what changes/ }).click();
  await expect(page.getByText(/limited by time, not budget|Cost change/).first()).toBeVisible({ timeout: 30_000 });
  // make a second version through the API (chat arrives in 007), then restore version 1 in the UI
  const token = await page.evaluate(() => localStorage.getItem("tripwise.token"));
  const tripId = page.url().split("/trips/")[1].split("/")[0];
  const r = await page.request.post(`http://localhost:8000/trips/${tripId}/replan`, {
    headers: { Authorization: `Bearer ${token}` }, data: { changes: { prefs: { pace: "relaxed" } } } });
  expect(r.status()).toBe(201);
  await page.reload();
  await expect(page.getByText("Version 2", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Restore" }).first().click();
  await expect(page.getByText("Version 3", { exact: true })).toBeVisible();
  await expect(page.getByText("Restored").first()).toBeVisible();
});
