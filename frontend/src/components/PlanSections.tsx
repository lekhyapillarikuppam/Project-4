import type { ReactNode } from "react";
import type { Journey, Plan } from "../api/types";
import { addDays, duration, inr, MODE_LABEL, TIER_LABEL } from "../lib/format";
import { useMeta } from "../lib/meta";
import { Price } from "./ui";

/** Plan sections shared by Plan detail and the read-only shared page (UI-FR-04, UI-FR-10). */
export function Section({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  const id = title.replace(/\W+/g, "-");
  return (
    <section aria-labelledby={id} className={`space-y-3 ${className}`}>
      <h2 id={id} className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

/** What a live-price link may fill in: the trip's destination, hotel dates and travellers (FR-055). */
export interface TripFacts { city: string; checkin: string; checkout: string; adults: number; rooms: number }

export function factsFor(plan: Plan, city: string, people: number): TripFacts {
  const checkin = plan.days[0]?.date ?? "";
  return { city, checkin, checkout: checkin ? addDays(checkin, plan.hotel.nights) : "", adults: people, rooms: plan.hotel.rooms };
}

function fill(pattern: string, f: TripFacts): string {
  const v: Record<string, string> = { city: f.city, checkin: f.checkin, checkout: f.checkout, adults: String(f.adults), rooms: String(f.rooms) };
  return pattern.replace(/\{(\w+)\}/g, (m, k: string) => (k in v ? encodeURIComponent(v[k]) : m));
}

/** "Check live prices on <site> ↗": the site's own search in a new tab; Tripwise never fetches prices (UI-FR-13). */
export function LivePriceLink({ kind, facts }: { kind: "flight" | "train" | "bus" | "hotel"; facts: TripFacts }) {
  const link = useMeta().data?.live_prices?.[kind];
  if (!link) return null;
  return (
    <div className="mt-2 border-t border-sand-200 pt-2 print:hidden">
      <a href={fill(link.url, facts)} target="_blank" rel="noopener noreferrer" className="btn-link">
        Check live prices on {link.site} <span aria-hidden>↗</span><span className="sr-only"> (opens in a new tab)</span>
      </a>
      <p className="text-xs text-ink-500">Tripwise doesn't book; prices there may differ.</p>
    </div>
  );
}

export function JourneyCard({ title, j, out, facts }: { title: string; j: Journey; out: boolean; facts: TripFacts }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-ink-700">{title}</h3>
      <p className="mt-1 text-lg font-semibold">{MODE_LABEL[j.mode]} <span className="text-ink-500">{j.class}</span></p>
      <p className="text-sm">
        {out ? `Leaves ${j.depart}${j.overnight ? " (overnight)" : ""}, at the city centre ${j.arrive_centre}`
             : `Leave the centre ${j.leave_centre}, arrive ${j.arrive_origin}${j.overnight ? " (overnight)" : ""}`}
      </p>
      <p className="text-sm text-ink-700">Door to door {duration(j.minutes)} · <Price>{inr(j.cost)}</Price></p>
      <LivePriceLink kind={j.mode} facts={facts} />
    </div>
  );
}

export function HotelCard({ hotel, facts }: { hotel: Plan["hotel"]; facts: TripFacts }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-ink-700">Hotel</h3>
      <p className="mt-1 line-clamp-2 text-base font-semibold leading-snug" title={hotel.name}>{hotel.name}</p>
      <p className="text-sm">{TIER_LABEL[hotel.tier]} · {hotel.nights} night{hotel.nights === 1 ? "" : "s"} · {hotel.rooms} room{hotel.rooms === 1 ? "" : "s"}</p>
      <p className="num text-sm text-ink-700"><Price>{inr(hotel.cost)}</Price> · <Price>{inr(hotel.price_per_room_night)}</Price> per room per night</p>
      <LivePriceLink kind="hotel" facts={facts} />
    </div>
  );
}

/** Transport and hotel, side by side. */
export function GettingThere({ plan, facts }: { plan: Plan; facts: TripFacts }) {
  return (
    <Section title="Getting there and staying">
      <div className="grid gap-3 sm:grid-cols-3">
        <JourneyCard title="Outbound" j={plan.transport.outbound} out facts={facts} />
        <JourneyCard title="Return" j={plan.transport.return} out={false} facts={facts} />
        <HotelCard hotel={plan.hotel} facts={facts} />
      </div>
    </Section>
  );
}

/** "Download PDF": the browser's print dialog with the print stylesheet (UI-FR-12). */
export function DownloadPdf() {
  return <button type="button" className="btn-secondary btn-sm print:hidden" onClick={() => window.print()}>Download PDF</button>;
}
