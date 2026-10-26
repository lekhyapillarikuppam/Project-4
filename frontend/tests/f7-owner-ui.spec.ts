import { expect, test } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, newEmail, signUp } from "./helpers";

// 006 follow-up F7 (UI-FR-01, 02, 06; FR-007; API-FR-03): owner UI changes.

test("password show/hide toggle", async ({ page }) => {
  await page.goto("/login");
  const pw = page.getByLabel("Password", { exact: true });
  await pw.fill("secret words");
  await expect(pw).toHaveAttribute("type", "password");
  const eye = page.getByRole("button", { name: "Show password" });
  await expect(eye).toHaveAttribute("aria-pressed", "false");
  await pw.focus();
  await page.keyboard.press("Tab");                                  // reachable by keyboard, right after the field
  await expect(eye).toBeFocused();
  await page.keyboard.press("Enter");                                // toggles; does not submit the form
  await expect(pw).toHaveAttribute("type", "text");
  const hide = page.getByRole("button", { name: "Hide password" });
  await expect(hide).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("Enter a valid email address.")).toHaveCount(0);
  await hide.click();
  await expect(pw).toHaveAttribute("type", "password");
});

test("switching between Log in and Sign up starts empty", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("someone@example.com");
  await page.getByLabel("Password", { exact: true }).fill("short");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByText("Password must be 8–128 characters.")).toBeVisible();
  await page.getByRole("main").getByRole("link", { name: "Sign up" }).click();
  await expect(page).toHaveURL(/\/signup$/);
  await expect(page.getByLabel("Email")).toHaveValue("");
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
  await expect(page.getByText("Password must be 8–128 characters.")).toHaveCount(0);
  await page.getByLabel("Email").fill("other@example.com");
  await page.getByRole("main").getByRole("link", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Email")).toHaveValue("");
  expect(page.url()).not.toContain("example.com");
});

test("a new user's profile is blank and Fill from my profile needs a saved one", async ({ page }) => {
  await signUp(page, newEmail(), "correct horse 1", { toNewTrip: false });
  // Profile after sign-up: nothing invented
  await expect(page.getByLabel("Hours out each day")).toHaveValue("");
  for (const r of await page.getByRole("radio").all()) await expect(r).not.toBeChecked();
  for (const t of ["Nature", "Adventure", "Food", "History & heritage", "Culture & art", "Spiritual", "Shopping", "Relaxation", "Nightlife"])
    await expect(page.getByLabel(t, { exact: true })).toHaveValue("0");
  for (const m of ["train", "bus", "flight"]) await expect(page.getByLabel(m, { exact: true })).toHaveValue("neutral");
  await expect(page.getByLabel("Avoid crowded places")).not.toBeChecked();

  // New trip: blank too, and the button is disabled with its hint
  await page.getByRole("link", { name: "Skip for now" }).click();
  const fill = page.getByRole("button", { name: "Fill from my profile" });
  await expect(fill).toBeDisabled();
  await expect(page.getByText("Save your preferences in Profile first.")).toBeVisible();
  await expect(page.getByLabel("Hours out each day")).toHaveValue("");

  // save a profile, then the button fills the form
  await page.getByRole("navigation").getByRole("link", { name: "Profile" }).click();
  await fillPrefs(page, { hours: "11", pace: /^packed/i, comfort: /^Premium/, interests: { Nature: "5" } });
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await page.getByRole("navigation").getByRole("link", { name: "New trip" }).click();
  await expect(page.getByLabel("Hours out each day")).toHaveValue("");             // still blank until asked
  await expect(fill).toBeEnabled();
  await fill.click();
  await expect(page.getByLabel("Hours out each day")).toHaveValue("11");
  await expect(page.getByRole("radio", { name: /^packed/i })).toBeChecked();
  await expect(page.getByRole("radio", { name: /^Premium/ })).toBeChecked();
  await expect(page.getByLabel("Nature", { exact: true })).toHaveValue("5");
});

test("custom trip name and created time on My Trips", async ({ page }) => {
  await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Agra", start: isoInDays(26), end: isoInDays(28), people: "2", budget: "30000" });
  await expect(page.getByLabel(/^Trip name/)).toHaveAttribute("placeholder", /^Delhi to Agra, \d{2} [A-Z][a-z]{2} \d{4}$/);
  await fillTrip(page, { name: "Our Agra weekend" });
  await fillPrefs(page);
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  await page.getByRole("link", { name: "My Trips" }).click();
  const list = page.getByRole("tabpanel");
  await expect(list.getByRole("link", { name: "Our Agra weekend" })).toBeVisible();
  await expect(list.getByText(/^Created \d{1,2} [A-Z][a-z]{2} \d{4}, \d{1,2}:\d{2} (am|pm)$/)).toBeVisible();
});
