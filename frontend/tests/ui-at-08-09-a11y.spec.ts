import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, newEmail, signUp } from "./helpers";

/** Press Tab until the focused element's label matches, checking each stop shows a visible focus ring. */
async function tabTo(page: Page, name: RegExp, max = 80) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return { label: "", ring: true };
      const input = el as HTMLInputElement;
      const label = (input.labels?.[0]?.textContent ?? "") + " " + (el.getAttribute("aria-label") ?? "") + " " + (el.textContent ?? "");
      const st = getComputedStyle(el);
      const ring = (st.outlineStyle !== "none" && parseFloat(st.outlineWidth) >= 1) || st.boxShadow !== "none";
      return { label: label.trim(), ring };
    });
    expect(info.ring, `focus not visible on "${info.label}"`).toBe(true);
    if (name.test(info.label)) return;
  }
  throw new Error(`could not Tab to ${name}`);
}

// UI-AT-08: UI-AT-01 by keyboard only, with visible focus throughout.
test("UI-AT-08 keyboard-only run", async ({ page }) => {
  await page.goto("/signup");
  await tabTo(page, /^Email/);
  await page.keyboard.type(newEmail());
  await tabTo(page, /^Password/);
  await page.keyboard.type("correct horse 1");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/profile$/);
  // wait for each page to render before walking it by keyboard (the URL changes before the lazy page loads)
  await expect(page.getByRole("link", { name: "Skip for now" })).toBeVisible();
  await tabTo(page, /^Skip for now/);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/new$/);
  await expect(page.getByLabel("From", { exact: true })).toBeVisible();
  await tabTo(page, /^From/);
  await page.keyboard.type("Delhi");
  await tabTo(page, /^To/);
  await page.keyboard.type("Agra");
  await expect(page.getByLabel("To", { exact: true })).toHaveValue("AGR");
  await tabTo(page, /^Budget \(/);                                  // the budget starts empty (F10)
  await page.keyboard.type("30000");
  // blank preferences, chosen by keyboard: hours from the list, an interest, pace and comfort
  await tabTo(page, /^Hours out/);
  await page.keyboard.type("9");
  await expect(page.getByLabel("Hours out each day")).toHaveValue("9");
  await tabTo(page, /^History/);
  for (let i = 0; i < 3; i++) await page.keyboard.press("ArrowRight");
  await tabTo(page, /^relaxed/i);
  await page.keyboard.press("Space");
  await tabTo(page, /^Budget —/);
  await page.keyboard.press("Space");
  await tabTo(page, /^Plan my trip/);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  await tabTo(page, /^Choose /);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/plan$/);
});

async function unlabelledPrices(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const bad: string[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const text = n.textContent ?? "";
      if (!/₹\s?\d/.test(text)) continue;
      const el = n.parentElement;
      if (el && !el.closest("[data-estimate],[data-not-price]")) bad.push(text.trim());
    }
    return bad;
  });
}

// UI-AT-09: every price on screen has the Estimated label or sits under one.
test("UI-AT-09 estimated labels", async ({ page }) => {
  await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Jaipur", start: isoInDays(45), end: isoInDays(47), budget: "50000" });
  await fillPrefs(page);
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  expect(await unlabelledPrices(page)).toEqual([]);
  await page.getByRole("button", { name: /^Choose / }).first().click();
  await expect(page.getByRole("heading", { name: "Day by day" })).toBeVisible();
  await page.getByRole("button", { name: /Show what changes/ }).click();
  await expect(page.getByText(/limited by time, not budget|Cost change/).first()).toBeVisible({ timeout: 30_000 });
  expect(await unlabelledPrices(page)).toEqual([]);
  await expect(page.getByText(/Estimated prices, compiled/).first()).toBeVisible();
});

// UI-FR-09: a busy planner (429) shows the retry state.
test("busy planner shows retry", async ({ page }) => {
  await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Agra", budget: "30000" });
  await fillPrefs(page);
  await page.route("**/trips", (route) => route.request().method() === "POST"
    ? route.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ error: "busy", message: "busy" }) })
    : route.continue());
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByText("The planner is busy right now. Please retry in a moment.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

// NFR-007: no WCAG 2 A/AA violations (labels, contrast, names) on any page.
test("accessibility scan of every page", async ({ page }) => {
  const scan = async (where: string) => {
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).exclude(".leaflet-container").analyze();
    const v = r.violations.map((x) => `${where}: ${x.id} (${x.nodes.length}) ${x.nodes[0]?.target.join(" ")}`);
    return v;
  };
  const problems: string[] = [];
  await page.goto("/");
  problems.push(...await scan("landing"));
  await page.goto("/login");
  problems.push(...await scan("login"));
  await signUp(page);
  problems.push(...await scan("new trip"));
  await fillTrip(page, { from: "Delhi", to: "Agra", budget: "30000" });
  await fillPrefs(page);
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
  problems.push(...await scan("comparison"));
  await page.getByRole("button", { name: /^Choose / }).first().click();
  await expect(page.getByRole("heading", { name: "Day by day" })).toBeVisible();
  problems.push(...await scan("plan detail"));
  await page.goto("/trips");
  await expect(page.getByRole("tabpanel").getByRole("listitem").first()).toBeVisible();
  problems.push(...await scan("my trips"));
  await page.goto("/profile");
  await expect(page.getByRole("button", { name: "Save preferences" })).toBeVisible();
  problems.push(...await scan("profile"));
  expect(problems).toEqual([]);
});
