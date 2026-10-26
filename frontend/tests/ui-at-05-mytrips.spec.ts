import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, signUp } from "./helpers";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PY = path.resolve(HERE, "..", "..", "backend", ".venv", "Scripts", "python.exe");

// UI-AT-05: rename, duplicate (pre-filled form) and delete (with confirm) work; upcoming/past tabs are correct.
test("UI-AT-05 My Trips", async ({ page }) => {
  const { email } = await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Agra", start: isoInDays(25), end: isoInDays(27), people: "3", budget: "45000" });
  await fillPrefs(page);
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  execFileSync(PY, [path.join(HERE, "make_past_trip.py"), email], { stdio: "pipe" });

  await page.getByRole("link", { name: "My Trips" }).click();
  await expect(page.getByRole("tab", { name: "Upcoming" })).toHaveAttribute("aria-selected", "true");
  const list = page.getByRole("tabpanel");
  await expect(list.getByRole("listitem")).toHaveCount(1);
  await expect(list.getByText("Last month in Agra")).toHaveCount(0);
  // when the trip was made, in India time (UI-FR-06)
  await expect(list.getByText(/^Created \d{1,2} [A-Z][a-z]{2} \d{4}, \d{1,2}:\d{2} (am|pm)$/)).toBeVisible();

  // rename inline
  await list.getByRole("button", { name: /^Rename/ }).click();
  await page.getByLabel("Trip name").fill("Family Agra trip");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(list.getByRole("link", { name: "Family Agra trip" })).toBeVisible();

  // past tab
  await page.getByRole("tab", { name: "Past" }).click();
  await expect(page.getByRole("tabpanel").getByText("Last month in Agra")).toBeVisible();
  await page.getByRole("tab", { name: "Upcoming" }).click();

  // duplicate opens the form pre-filled
  await page.getByRole("tabpanel").getByRole("button", { name: /^Duplicate/ }).click();
  await expect(page).toHaveURL(/\/new$/);
  await expect(page.getByLabel("To", { exact: true })).toHaveValue("AGR");
  await expect(page.getByLabel("People", { exact: true })).toHaveValue("3");
  await expect(page.getByLabel("Budget (₹)", { exact: true })).toHaveValue("45000");
  await expect(page.getByLabel(/^Trip name/)).toHaveValue("Family Agra trip (copy)");
  await expect(page.getByLabel("Hours out each day")).toHaveValue("9");        // the trip's own preferences, not blank

  // delete with confirm: cancel first, then confirm
  await page.getByRole("link", { name: "My Trips" }).click();
  await page.getByRole("tabpanel").getByRole("button", { name: /^Delete/ }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await page.getByRole("tabpanel").getByRole("button", { name: /^Delete/ }).click();
  await page.getByRole("button", { name: "Delete trip" }).click();
  await expect(page.getByText("No upcoming trips.")).toBeVisible();
});
