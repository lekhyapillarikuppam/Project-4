import { expect, type Page } from "@playwright/test";

export function newEmail(): string {
  return `ui-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

/** Sign up; a new account lands on Profile with the welcome note (UI-FR-01). By default skip on to New trip. */
export async function signUp(page: Page, email = newEmail(), password = "correct horse 1", { toNewTrip = true } = {}) {
  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByText("Set your preferences once; you can reuse them for every trip")).toBeVisible();
  if (toNewTrip) {
    await page.getByRole("link", { name: "Skip for now" }).click();
    await expect(page).toHaveURL(/\/new$/);
  }
  return { email, password };
}

/** Fill the trip fields of the New trip form. Preferences start blank: set them with fillPrefs. */
export async function fillTrip(page: Page, o: { from?: string; to?: string; start?: string; end?: string; people?: string; budget?: string; name?: string } = {}) {
  if (o.from) await page.getByLabel("From", { exact: true }).selectOption({ label: o.from });
  if (o.to) await page.getByLabel("To", { exact: true }).selectOption({ label: o.to });
  if (o.start) await page.getByLabel("Start date", { exact: true }).fill(o.start);
  if (o.end) await page.getByLabel(/^End date/).fill(o.end);
  if (o.people) await page.getByLabel("People", { exact: true }).fill(o.people);
  if (o.budget) await page.getByLabel("Budget (₹)", { exact: true }).fill(o.budget);
  if (o.name !== undefined) await page.getByLabel(/^Trip name/).fill(o.name);
}

/** Set the preferences explicitly (on New trip or Profile): by default the old server defaults, so plans stay comparable. */
export async function fillPrefs(page: Page, o: { hours?: string; pace?: RegExp; comfort?: RegExp; interests?: Record<string, string> } = {}) {
  await page.getByLabel("Hours out each day").selectOption(o.hours ?? "9");
  await page.getByRole("radio", { name: o.pace ?? /^balanced/i }).check();
  await page.getByRole("radio", { name: o.comfort ?? /^Mid-range/ }).check();
  const interests = o.interests ?? { "History & heritage": "3", "Culture & art": "3", Food: "3" };
  for (const [label, v] of Object.entries(interests)) await page.getByLabel(label, { exact: true }).fill(v);
}

export function isoInDays(n: number): string {
  return new Date(Date.now() + 330 * 60_000 + n * 86_400_000).toISOString().slice(0, 10);
}

export async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(0);
}
