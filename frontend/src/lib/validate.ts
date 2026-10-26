// Client-side checks with the same rules and field keys as the API (API-FR-04).

import type { DraftPrefs, Meta, TripForm } from "../api/types";
import { addDays, daysBetween, todayIST } from "./format";

export type Errors = Record<string, string>;
/** The trip form while being filled in: preferences may still be unchosen. */
export type DraftTripForm = Omit<TripForm, "prefs"> & { prefs: DraftPrefs };

export function validatePrefs(p: DraftPrefs, meta: Meta, errs: Errors = {}): Errors {
  const [lo, hi] = meta.limits.hours_out;
  if (p.daily_hours_out === null) errs["prefs.daily_hours_out"] = "Choose how many hours a day you want to be out.";
  else if (!(p.daily_hours_out >= lo && p.daily_hours_out <= hi)) errs["prefs.daily_hours_out"] = `Hours out must be between ${lo} and ${hi}.`;
  if (Object.values(p.interests).every((w) => w === 0)) errs["prefs.interests"] = "Give at least one interest a weight above 0.";
  if (p.pace === null) errs["prefs.pace"] = "Choose a pace.";
  if (p.comfort === null) errs["prefs.comfort"] = "Choose a stay comfort.";
  if (Object.values(p.modes).every((m) => m === "avoid")) errs["prefs.modes"] = "At least one transport mode must not be avoided.";
  return errs;
}

/** The element to focus for an error key, so the first problem is announced at once (WCAG 3.3.1). */
export function fieldId(key: string, meta: Meta): string {
  if (key === "prefs.daily_hours_out") return "hours";
  if (key === "prefs.pace") return `pace-${meta.paces[0]}`;
  if (key === "prefs.comfort") return `comfort-${meta.comforts[0]}`;
  if (key.startsWith("prefs.interests")) return `int-${meta.interests[0]}`;
  if (key.startsWith("prefs.modes")) return `mode-${meta.modes[0]}`;
  return `f-${key.split(".")[0]}`;
}

export function validateTrip(f: DraftTripForm, meta: Meta): Errors {
  const errs: Errors = {};
  const L = meta.limits;
  if (!f.origin) errs.origin = "Choose where you're starting from.";
  if (!f.destination) errs.destination = "Choose a destination.";
  else if (f.origin === f.destination) errs.destination = "Destination must differ from origin.";
  const today = todayIST();
  if (!f.start_date) errs.start_date = "Choose a start date.";
  else if (f.start_date < addDays(today, 1)) errs.start_date = "The trip must start tomorrow or later.";
  else if (f.start_date > addDays(today, L.max_days_ahead)) errs.start_date = `The trip must start within ${L.max_days_ahead} days.`;
  if (!f.end_date) errs.end_date = "Choose an end date.";
  else if (f.start_date) {
    const days = daysBetween(f.start_date, f.end_date) + 1;
    if (days < L.trip_days[0] || days > L.trip_days[1]) errs.end_date = `A trip lasts ${L.trip_days[0]} to ${L.trip_days[1]} days (start and end included).`;
  }
  if (f.name !== undefined && f.name.length > 120) errs.name = "A trip name has at most 120 characters.";
  const [plo, phi] = L.people;
  if (!Number.isInteger(f.people) || f.people < plo || f.people > phi) errs.people = `Group size is ${plo} to ${phi} people.`;
  const perPerson = f.budget_per_person !== undefined;
  const field = perPerson ? "budget_per_person" : "budget_total";
  const amount = perPerson ? f.budget_per_person : f.budget_total;
  if (amount === undefined || !Number.isInteger(amount) || amount <= 0) errs[field] = "Enter your budget in whole rupees.";
  else if (!errs.people) {
    const total = perPerson ? amount * f.people : amount;
    if (total < L.budget_min_per_person * f.people) errs[field] = `The budget must be at least ₹${L.budget_min_per_person.toLocaleString("en-IN")} per person.`;
    else if (total > L.budget_max_total) errs[field] = "The total budget can be at most ₹10,00,000.";
  }
  validatePrefs(f.prefs, meta, errs);
  return errs;
}
