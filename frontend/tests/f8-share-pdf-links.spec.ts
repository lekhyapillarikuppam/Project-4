import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { fillPrefs, fillTrip, isoInDays, signUp } from "./helpers";

// 006 follow-up F8: UI-AT-10 share link, UI-AT-11 PDF, UI-AT-12 live-price links.

async function planDetail(page: Page, people = "2") {
  await signUp(page);
  await fillTrip(page, { from: "Delhi", to: "Jaipur", start: isoInDays(40), end: isoInDays(42), people, budget: "50000", name: "Jaipur long weekend" });
  await fillPrefs(page);
  await page.getByRole("button", { name: "Plan my trip" }).click();
  await page.getByRole("button", { name: /^Choose / }).first().click();
  await expect(page.getByRole("heading", { name: "Day by day" })).toBeVisible();
}

test("UI-AT-10 share link: copy, open logged out, read-only, stop sharing", async ({ page, browser, baseURL }) => {
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin: baseURL! });
  await planDetail(page);
  await page.getByRole("button", { name: "Share", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Share this plan" });
  await expect(dialog.getByLabel("Link")).toHaveValue(/\/s\/[A-Za-z0-9_-]{43,}$/);
  await dialog.getByRole("button", { name: "Copy link" }).click();
  await expect(dialog.getByText("Link copied.")).toBeVisible();
  const link = await page.evaluate(() => navigator.clipboard.readText());
  expect(link).toBe(await dialog.getByLabel("Link").inputValue());

  // a fresh, logged-out browser
  const other = await browser.newContext();
  const guest = await other.newPage();
  await guest.goto(link);
  await expect(guest.getByText("Shared plan · prices are estimates")).toBeVisible();
  await expect(guest.getByRole("heading", { level: 1, name: "Jaipur long weekend" })).toBeVisible();
  for (const h of ["Getting there and staying", "Day by day", "Map", "Budget"]) await expect(guest.getByRole("heading", { name: h, exact: true })).toBeVisible();
  await expect(guest.getByRole("link", { name: "Plan your own trip" })).toBeVisible();
  await expect(guest.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex");
  // read-only: no chat, versions, trade-offs, share or edit controls
  await expect(guest.getByRole("complementary", { name: "Chat assistant" })).toHaveCount(0);
  await expect(guest.getByText("Version history")).toHaveCount(0);
  await expect(guest.getByText("Budget trade-offs")).toHaveCount(0);
  await expect(guest.getByRole("button", { name: "Share", exact: true })).toHaveCount(0);
  await expect(guest.getByRole("button", { name: /Restore|Choose|Rename/ })).toHaveCount(0);
  const axe = await new AxeBuilder({ page: guest }).withTags(["wcag2a", "wcag2aa"]).exclude(".leaflet-container").analyze();
  expect(axe.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);

  // stop sharing: the same link now shows the not-available page
  await dialog.getByRole("button", { name: "Stop sharing" }).click();
  await expect(dialog.getByText("Sharing is off.")).toBeVisible();
  await guest.reload();
  await expect(guest.getByRole("heading", { name: "This shared plan isn't available" })).toBeVisible();
  await other.close();
});

test("UI-AT-11 Download PDF: print layout and page.pdf()", async ({ page }, info) => {
  await planDetail(page);
  await page.evaluate(() => { (window as unknown as { printed: number }).printed = 0; window.print = () => { (window as unknown as { printed: number }).printed++; }; });
  await page.getByRole("button", { name: "Download PDF" }).click();
  expect(await page.evaluate(() => (window as unknown as { printed: number }).printed)).toBe(1);

  await page.emulateMedia({ media: "print" });
  // kept
  await expect(page.getByRole("heading", { level: 1, name: "Jaipur long weekend" })).toBeVisible();
  for (const h of ["Getting there and staying", "Day by day", "Budget"]) await expect(page.getByRole("heading", { name: h, exact: true })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("table").getByText(/Estimated prices, compiled/)).toBeVisible();
  // hidden
  await expect(page.getByRole("banner")).toBeHidden();
  await expect(page.getByRole("complementary", { name: "Chat assistant" })).toBeHidden();
  await expect(page.getByRole("heading", { name: "Version history" })).toBeHidden();
  await expect(page.getByRole("heading", { name: "Budget trade-offs" })).toBeHidden();
  for (const b of ["Download PDF", "Share"]) await expect(page.getByRole("button", { name: b, exact: true })).toBeHidden();
  await expect(page.getByRole("link", { name: /Check live prices/ }).first()).toBeHidden();
  // black text on white
  const colours = await page.evaluate(() => {
    const h = document.querySelector("h1")!;
    return { text: getComputedStyle(h).color, bg: getComputedStyle(document.body).backgroundColor };
  });
  expect(colours).toEqual({ text: "rgb(0, 0, 0)", bg: "rgb(255, 255, 255)" });

  await page.screenshot({ path: `test-shots/plan-print-${info.project.name}.png`, fullPage: true });   // the same layout, viewable
  const pdf = await page.pdf({ format: "A4", printBackground: true, path: `test-shots/plan-print-${info.project.name}.pdf` });
  expect(pdf.subarray(0, 4).toString()).toBe("%PDF");
  expect(pdf.length).toBeGreaterThan(20_000);
});

test("UI-AT-12 live-price links", async ({ page }) => {
  await planDetail(page, "3");
  const meta = await (await page.request.get("http://localhost:8000/meta")).json();
  const links = page.getByRole("link", { name: /^Check live prices on / });
  await expect(links).toHaveCount(3);
  for (const l of await links.all()) {
    await expect(l).toHaveAttribute("target", "_blank");
    await expect(l).toHaveAttribute("rel", "noopener noreferrer");
  }
  await expect(page.getByText("Tripwise doesn't book; prices there may differ.").first()).toBeVisible();
  const modes = await page.locator(".card").filter({ has: page.getByRole("heading", { name: /^(Outbound|Return)$/ }) })
    .locator("p.text-lg").allInnerTexts();
  const hrefs = await links.evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).href));
  modes.forEach((m, i) => {
    const mode = m.split(" ")[0].toLowerCase() as "flight" | "train" | "bus";
    expect(hrefs[i]).toBe(meta.live_prices[mode].url);
  });
  const hotel = new URL(hrefs[2]);
  expect(hotel.origin + hotel.pathname).toBe("https://www.booking.com/searchresults.html");
  expect(hotel.searchParams.get("ss")).toBe("Jaipur");
  expect(hotel.searchParams.get("checkin")).toBe(isoInDays(40));
  expect(hotel.searchParams.get("checkout")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(hotel.searchParams.get("checkout")! > hotel.searchParams.get("checkin")!).toBe(true);
  expect(hotel.searchParams.get("group_adults")).toBe("3");
  expect(hotel.searchParams.get("no_rooms")).toBe("2");
  await expect(links.nth(2)).toHaveText(/Check live prices on Booking\.com/);
});
