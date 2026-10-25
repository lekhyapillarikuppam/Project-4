import type { Plan } from "../api/types";
import { inr, MODE_LABEL, TIER_LABEL, VARIANT_LABEL } from "../lib/format";
import Explanation from "./Explanation";
import { Price } from "./ui";

const BLURB: Record<string, string> = {
  experience: "The most you can get out of the trip within your budget.",
  balanced: "The best trade-off between what you get and what you spend.",
  saver: "The lowest cost that still keeps most of the value.",
};

/** Value as a 1–5 bar, scaled within this trip's variants (UI-FR-03). */
export function ValueBar({ score }: { score: number }) {
  const filled = Math.round(score);
  return (
    <span role="img" className="inline-flex items-center gap-1" aria-label={`Value ${score.toFixed(1)} of 5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} aria-hidden className={`h-2 w-6 rounded-full ${i < filled ? "bg-accent-600" : "bg-sand-200"}`} />
      ))}
      <span className="ml-1 text-xs text-ink-500" aria-hidden>{score.toFixed(1)}/5</span>
    </span>
  );
}

export function scoreWithin(values: number[], v: number): number {
  const lo = Math.min(...values), hi = Math.max(...values);
  return hi === lo ? 5 : 1 + (4 * (v - lo)) / (hi - lo);
}

export default function VariantCard({ plan, score, onChoose, choosing, tripId }: {
  plan: Plan; score: number; onChoose: () => void; choosing: boolean; tripId: string;
}) {
  const name = VARIANT_LABEL[plan.variant ?? "balanced"];
  const stops = plan.days.flatMap((d) => d.stops);
  const o = plan.transport.outbound, r = plan.transport.return;
  return (
    <article className="card flex flex-col gap-3" aria-labelledby={`v-${plan.variant}`}>
      <header>
        <h2 id={`v-${plan.variant}`} className="text-lg font-bold">{name}</h2>
        <p className="text-sm text-ink-700">{BLURB[plan.variant ?? "balanced"]}</p>
      </header>
      <p className="text-2xl font-bold"><Price>{inr(plan.budget.total)}</Price></p>
      <ValueBar score={score} />
      <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-ink-500">Hotel</dt><dd>{plan.hotel.name} <span className="text-ink-500">({TIER_LABEL[plan.hotel.tier]})</span></dd>
        <dt className="text-ink-500">Out</dt><dd>{MODE_LABEL[o.mode]} {o.class}{o.overnight ? ", overnight" : ""}</dd>
        <dt className="text-ink-500">Back</dt><dd>{MODE_LABEL[r.mode]} {r.class}{r.overnight ? ", overnight" : ""}</dd>
        <dt className="text-ink-500">Activities</dt><dd>{stops.length}</dd>
      </dl>
      {stops.length > 0 && (
        <div>
          <p className="text-sm font-medium text-ink-700">Highlights</p>
          <ul className="list-inside list-disc text-sm">
            {stops.slice(0, 3).map((s) => <li key={s.attraction_id}>{s.name}</li>)}
          </ul>
        </div>
      )}
      <Explanation tripId={tripId} variant={plan.variant ?? "balanced"} />
      <div className="mt-auto pt-2">
        <button type="button" className="btn-primary w-full" onClick={onChoose} disabled={choosing}>
          {choosing ? "Opening…" : `Choose ${name}`}
        </button>
      </div>
    </article>
  );
}
