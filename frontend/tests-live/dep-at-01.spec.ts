import { expect, test } from "@playwright/test";
import { fillTrip, isoInDays, signUp } from "../tests/helpers";

// DEP-AT-01 / DEP-FR-03: the full flow for a new user on the deployed URLs —
// sign up → plan → choose → chat change → My Trips.
test("DEP-AT-01 live full flow", async ({ page }) => {
  const email = `live-check-${Date.now()}@example.com`;
  await signUp(page, email);
  await fillTrip(page, { from: "Delhi", to: "Jaipur", start: isoInDays(30), end: isoInDays(32), people: "2", budget: "50000" });
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  await page.getByRole("button", { name: /^Choose / }).first().click();
  await expect(page).toHaveURL(/\/plan$/);

  const panel = page.getByRole("complementary", { name: "Chat assistant" });
  await panel.getByLabel("Message the assistant").fill("Switch to a budget hotel");
  await panel.getByRole("button", { name: "Send" }).click();
  await expect(panel.getByText("Version 2 created")).toBeVisible();
  await expect(page.getByText(/plan, version 2/)).toBeVisible();

  await page.getByRole("link", { name: "My Trips" }).click();
  const list = page.getByRole("tabpanel");
  await expect(list.getByRole("listitem")).toHaveCount(1);
  await expect(list.getByText(/Jaipur/).first()).toBeVisible();
  await page.screenshot({ path: "test-shots/live-my-trips.png", fullPage: false });
});
