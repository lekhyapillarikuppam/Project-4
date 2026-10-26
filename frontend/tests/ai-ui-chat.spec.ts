import { expect, test } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, noHorizontalScroll, signUp } from "./helpers";

// 007 T06 + AI-AT-05 (UI side): the API runs without a Groq key here, so the assistant must say it is unavailable,
// leave the plan alone, and the rest of the page (explanations included) must degrade quietly.
for (const width of [360, 1280]) {
  test(`chat panel without Groq at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await signUp(page);
    await expect(page.getByRole("heading", { name: /Describe your trip/ })).toBeVisible();
    await fillTrip(page, { from: "Delhi", to: "Jaipur", start: isoInDays(30), end: isoInDays(32), people: "2", budget: "50000" });
    await fillPrefs(page);
    await page.getByRole("button", { name: "Plan my trip" }).click();
    await expect(page.getByText(/Explanations are unavailable right now/).first()).toBeVisible();
    await page.getByRole("button", { name: /^Choose / }).first().click();
    await expect(page).toHaveURL(/\/plan$/);
    if (width < 1024) await page.getByRole("button", { name: "Ask the assistant" }).click();
    const panel = page.getByRole("complementary", { name: "Chat assistant" });
    await expect(panel).toBeVisible();
    await panel.getByLabel("Message the assistant").fill("only 5 hours on day 2");
    await panel.getByRole("button", { name: "Send" }).click();
    const log = panel.getByRole("log", { name: "Conversation" });
    await expect(log.getByText("only 5 hours on day 2")).toBeVisible();
    await expect(log.getByText(/assistant is unavailable right now/i)).toBeVisible();
    await expect(log.getByText(/Version \d+ created/)).toHaveCount(0);
    await expect(page.getByText("version 1", { exact: false }).first()).toBeVisible();
    await noHorizontalScroll(page);
    if (width < 1024) {
      await panel.getByRole("button", { name: "Close" }).click();
      await expect(panel).toBeHidden();
    }
    await page.reload();                                             // history is kept
    if (width < 1024) await page.getByRole("button", { name: "Ask the assistant" }).click();
    await expect(page.getByRole("log", { name: "Conversation" }).getByText("only 5 hours on day 2")).toBeVisible();
  });
}
