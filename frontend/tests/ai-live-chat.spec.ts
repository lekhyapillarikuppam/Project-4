import { expect, test } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, signUp } from "./helpers";

// 007 T06 live check (real Groq): a chat change shows "Version N created", the plan moves to version N, and Undo
// restores the previous version. Run with:  $env:E2E_LIVE_GROQ="1"; npx playwright test tests/ai-live-chat.spec.ts
test.skip(!process.env.E2E_LIVE_GROQ, "needs E2E_LIVE_GROQ=1 and a Groq key");

test("live chat change, version chip and undo", async ({ page }) => {
  test.setTimeout(120_000);
  await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Jaipur", start: isoInDays(30), end: isoInDays(32), people: "2", budget: "50000" });
  await fillPrefs(page);
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await expect(page.getByText(/Why this plan/).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Choose / }).first().click();
  await expect(page).toHaveURL(/\/plan$/);
  const panel = page.getByRole("complementary", { name: "Chat assistant" });
  await panel.getByLabel("Message the assistant").fill("Switch to a budget hotel");
  await panel.getByRole("button", { name: "Send" }).click();
  await expect(panel.getByText("Assistant is thinking…")).toBeVisible();
  await expect(panel.getByText("Version 2 created")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/plan, version 2/)).toBeVisible();
  await panel.getByRole("button", { name: /Undo \(back to version 1\)/ }).click();
  await expect(page.getByText(/plan, version 3/)).toBeVisible();
  await expect(panel.getByRole("button", { name: /Undo/ })).toHaveCount(0);
  await page.screenshot({ path: "test-shots/8-chat-1280.png", fullPage: false });
});
