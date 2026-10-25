import { expect, type Page } from "@playwright/test";

export function newEmail(): string {
  return `ui-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

export async function signUp(page: Page, email = newEmail(), password = "correct horse 1") {
  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page).toHaveURL(/\/new$/);
  return { email, password };
}

/** Fill the trip fields of the New trip form (preferences keep their defaults). */
export async function fillTrip(page: Page, o: { from?: string; to?: string; start?: string; end?: string; people?: string; budget?: string } = {}) {
  if (o.from) await page.getByLabel("From", { exact: true }).selectOption({ label: o.from });
  if (o.to) await page.getByLabel("To", { exact: true }).selectOption({ label: o.to });
  if (o.start) await page.getByLabel("Start date", { exact: true }).fill(o.start);
  if (o.end) await page.getByLabel(/^End date/).fill(o.end);
  if (o.people) await page.getByLabel("People", { exact: true }).fill(o.people);
  if (o.budget) await page.getByLabel("Budget (₹)", { exact: true }).fill(o.budget);
}

export function isoInDays(n: number): string {
  return new Date(Date.now() + 330 * 60_000 + n * 86_400_000).toISOString().slice(0, 10);
}

export async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(0);
}
