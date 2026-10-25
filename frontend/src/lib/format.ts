// Formatting helpers: Indian rupee grouping, durations, dates.

export function inr(n: number): string {
  const s = Math.round(Math.abs(n)).toString();
  let out = s;
  if (s.length > 3) {
    const head = s.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    out = `${head},${s.slice(-3)}`;
  }
  return `${n < 0 ? "−" : ""}₹${out}`;
}

export function signedInr(n: number): string {
  return n > 0 ? `+${inr(n)}` : n < 0 ? inr(n) : "₹0";
}

export function duration(minutes: number): string {
  const h = Math.floor(minutes / 60), m = minutes % 60;
  return h ? `${h} h${m ? ` ${m} min` : ""}` : `${m} min`;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export function weekday(i: number): string { return WEEKDAYS[i] ?? ""; }

export function niceDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return t.toISOString().slice(0, 10);
}

/** Today's date in India (UTC+05:30), as the API uses. */
export function todayIST(): string {
  return new Date(Date.now() + 330 * 60_000).toISOString().slice(0, 10);
}

export function daysBetween(a: string, b: string): number {
  const pa = a.split("-").map(Number), pb = b.split("-").map(Number);
  return Math.round((Date.UTC(pb[0], pb[1] - 1, pb[2]) - Date.UTC(pa[0], pa[1] - 1, pa[2])) / 86_400_000);
}

export const VARIANT_LABEL: Record<string, string> = { experience: "Experience", balanced: "Balanced", saver: "Saver" };
export const MODE_LABEL: Record<string, string> = { train: "Train", bus: "Bus", flight: "Flight" };
export const TIER_LABEL: Record<string, string> = { budget: "Budget", mid: "Mid-range", premium: "Premium" };
