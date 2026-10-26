import { expect, test } from "@playwright/test";
import { isoInDays, signUp } from "./helpers";

// 006 follow-up F9 (UI-FR-02): the dates are checked as soon as they change, with no submit.
test("dates are validated as they change", async ({ page }) => {
  await signUp(page);
  let posted = false;
  page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith("/trips")) posted = true; });
  const start = page.getByLabel("Start date", { exact: true });
  const end = page.getByLabel(/^End date/);
  const before = page.getByText("End date can't be before the start date.");
  const length = page.getByText("A trip lasts 2 to 7 days (start and end included).");

  await start.fill(isoInDays(30));
  await expect(end).toHaveAttribute("min", isoInDays(30));
  await expect(end).toHaveAttribute("max", isoInDays(36));                  // start + 6 days

  // an end date before the start: message at once, field invalid, no negative count
  await end.fill(isoInDays(27));
  await expect(before).toBeVisible();
  await expect(end).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#end-err")).toHaveAttribute("aria-live", "polite");
  await expect(page.locator('label[for="f-end_date"]')).toContainText("(check dates)");
  await expect(page.locator('label[for="f-end_date"]')).not.toContainText("-");

  // a 15-day trip: the length message, and the count in the error colour
  await end.fill(isoInDays(44));
  await expect(before).toHaveCount(0);
  await expect(length).toBeVisible();
  const count = page.locator('label[for="f-end_date"] span', { hasText: "(15 days)" });
  await expect(count).toBeVisible();
  await expect(count).toHaveCSS("color", "rgb(161, 33, 33)");                // bad-700, AA on white

  // a start date in the past shows its message too
  await start.fill(isoInDays(0));
  await expect(page.getByText("The trip must start tomorrow or later.")).toBeVisible();

  // a valid range clears every date message
  await start.fill(isoInDays(30));
  await end.fill(isoInDays(32));
  await expect(before).toHaveCount(0);
  await expect(length).toHaveCount(0);
  await expect(page.getByText("The trip must start tomorrow or later.")).toHaveCount(0);
  await expect(end).toHaveAttribute("aria-invalid", "false");
  await expect(page.locator('label[for="f-end_date"]')).toContainText("(3 days)");

  // moving the start past the end leaves the end as it is, so the message shows
  await start.fill(isoInDays(34));
  await expect(end).toHaveValue(isoInDays(32));
  await expect(before).toBeVisible();
  expect(posted).toBe(false);                                               // all of this without submitting
});
