import { expect, test } from "@playwright/test";
import { fillTrip, isoInDays, signUp } from "./helpers";

// UI-AT-04: each FR-001–005 violation is blocked on the client; a forced server 422 shows next to its field.
test("UI-AT-04 form validation", async ({ page }) => {
  await signUp(page);
  const submit = page.getByRole("button", { name: "Plan my trip" });
  const blocked = async (field: RegExp | string, text: RegExp) => {
    let posted = false;
    page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith("/trips")) posted = true; });
    await submit.click();
    await expect(page.getByText(text)).toBeVisible();
    expect(posted).toBe(false);
    void field;
  };

  await fillTrip(page, { from: "Delhi", to: "Delhi" });
  await blocked("To", /Destination must differ from origin/);
  await fillTrip(page, { to: "Agra", start: isoInDays(0), end: isoInDays(2) });
  await blocked("Start date", /must start tomorrow or later/);
  await fillTrip(page, { start: isoInDays(20), end: isoInDays(28) });
  await blocked("End date", /A trip lasts 2 to 7 days/);
  await fillTrip(page, { end: isoInDays(22), people: "7" });
  await blocked("People", /Group size is 1 to 6 people/);
  await fillTrip(page, { people: "2", budget: "3000" });
  await blocked("Budget", /at least ₹2,000 per person/);
  await fillTrip(page, { budget: "30000" });
  for (const m of ["train", "bus", "flight"]) await page.getByLabel(m, { exact: true }).selectOption("avoid");
  await blocked("Transport", /At least one transport mode must not be avoided/);
  for (const m of ["train", "bus", "flight"]) await page.getByLabel(m, { exact: true }).selectOption("neutral");
  for (const t of ["Nature", "Adventure", "Food", "History & heritage", "Culture & art", "Spiritual", "Shopping", "Relaxation", "Nightlife"]) {
    await page.getByLabel(t, { exact: true }).fill("0");
  }
  await blocked("Interests", /at least one interest a weight above 0/);
  await page.getByLabel("Food", { exact: true }).fill("4");

  // a server-side 422: the client check passes, the server rejects the destination
  await page.route("**/trips", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({ status: 422, contentType: "application/json",
      body: JSON.stringify({ error: "invalid", message: "Some fields are not valid.", fields: { destination: "Server says no to this city." } }) });
  });
  await submit.click();
  await expect(page.getByText("Server says no to this city.")).toBeVisible();
});
