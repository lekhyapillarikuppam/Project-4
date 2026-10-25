import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { fillTrip, isoInDays, noHorizontalScroll, signUp } from "./helpers";

const SHOTS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "test-shots");

async function clipped(page: Page): Promise<string[]> {
  // elements (outside the map) whose box extends past the viewport's right edge
  return page.evaluate(() => {
    const w = document.documentElement.clientWidth;
    return [...document.querySelectorAll("body *")]
      .filter((el) => !el.closest(".leaflet-container") && el.getBoundingClientRect().right > w + 1
        && getComputedStyle(el).position !== "fixed")
      .slice(0, 5).map((el) => `${el.tagName.toLowerCase()}.${(el.className || "").toString().slice(0, 40)}`);
  });
}

// UI-AT-07: 360 px and 1280 px screenshots of every page; no horizontal scroll, nothing clipped.
for (const width of [360, 1280]) {
  test(`UI-AT-07 pages at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 360 ? 780 : 900 });
    const shot = async (name: string) => {
      await page.waitForLoadState("networkidle");
      await noHorizontalScroll(page);
      expect(await clipped(page), `${name} at ${width}px`).toEqual([]);
      await page.screenshot({ path: path.join(SHOTS, `${name}-${width}.png`), fullPage: true });
    };
    await page.goto("/");
    await shot("1-landing");
    await page.goto("/login");
    await shot("2-login");
    await signUp(page);
    await shot("3-new-trip");
    await fillTrip(page, { from: "Delhi", to: "Jaipur", start: isoInDays(50), end: isoInDays(53), people: "2", budget: "60000" });
    await page.getByRole("button", { name: "Plan my trip" }).click();
    await expect(page.getByRole("button", { name: /^Choose / }).first()).toBeVisible();
    await shot("4-comparison");
    await page.getByRole("button", { name: /^Choose / }).first().click();
    await expect(page.getByRole("heading", { name: "Day by day" })).toBeVisible();
    await expect(page.locator(".leaflet-marker-icon").first()).toBeVisible();
    await shot("5-plan-detail");
    await page.goto("/trips");
    await expect(page.getByRole("tabpanel").getByRole("listitem").first()).toBeVisible();
    await shot("6-my-trips");
    await page.goto("/profile");
    await expect(page.getByRole("button", { name: "Save preferences" })).toBeVisible();
    await shot("7-profile");
  });
}
