import type { Plan } from "../api/types";
import { inr, MODE_LABEL, TIER_LABEL, VARIANT_LABEL } from "../lib/format";
import Explanation from "./Explanation";
import { Price } from "./ui";

const BLURB: Record<string, string> = {
  experience: "The most you can get out of the trip within your budget.",
  balanced: "The best trade-off between what you get and what you spend.",
  saver: "The lowest cost that still keeps most of the value.",
};

export type ValueRank = "most" | "middle" | "least" | "only";
const RANK_TEXT: Record<ValueRank, string> = {
  most: "Most value of these plans", middle: "In between", least: "Least value, lowest cost", only: "The only plan that fits",
};

/** Value as a 1–5 bar, scaled within this trip's variants (UI-FR-03), with a relative label rather than a rating. */
export function ValueBar({ score, rank }: { score: number; rank: ValueRank }) {
  const filled = Math.round(score);
  return (
    <span role="img" className="inline-flex flex-wrap items-center gap-1"
          aria-label={`Value ${score.toFixed(1)} of 5 within this trip: ${RANK_TEXT[rank].toLowerCase()}`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} aria-hidden className={`h-2 w-6 rounded-full ${i < filled ? "bg-accent-600" : "bg-sand-200"}`} />
      ))}
      <span className="ml-1 text-xs text-ink-700" aria-hidden>{RANK_TEXT[rank]}</span>
    </span>
  );
}

export function scoreWithin(values: number[], v: number): number {
  const lo = Math.min(...values), hi = Math.max(...values);
  return hi === lo ? 5 : 1 + (4 * (v - lo)) / (hi - lo);
}

function Check() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8.5 6.5 12 13 4.5" />
    </svg>
  );
}

const CHECKS = ["Within budget", "Opening hours", "Travel times", "Daily time limit"];

/** What the planner checked every plan against (the product's promise, made visible). */
export function CheckList({ className = "" }: { className?: string }) {
  return (
    <ul aria-label="Checked by the planner" className={`flex flex-wrap gap-x-3 gap-y-1 text-xs font-medium text-accent-800 ${className}`}>
      {CHECKS.map((c) => <li key={c} className="inline-flex items-center gap-1"><Check />{c}</li>)}
    </ul>
  );
}

export default function VariantCard({ plan, score, rank, onChoose, choosing, tripId }: {
  plan: Plan; score: number; rank: ValueRank; onChoose: () => void; choosing: boolean; tripId: string;
}) {
  const name = VARIANT_LABEL[plan.variant ?? "balanced"];
  const stops = plan.days.flatMap((d) => d.stops);
  const o = plan.transport.outbound, r = plan.transport.return;
  const share = Math.min(1, plan.budget.total / plan.budget.budget_total);
  return (
    <article className="card flex flex-col gap-3" aria-labelledby={`v-${plan.variant}`}>
      <header>
        <h2 id={`v-${plan.variant}`} className="text-xl font-bold">{name}</h2>
        <p className="text-sm text-ink-700">{BLURB[plan.variant ?? "balanced"]}</p>
      </header>
      <div>
        <p className="flex flex-wrap items-baseline gap-x-2">
          <span className="num text-2xl font-bold"><Price>{inr(plan.budget.total)}</Price></span>
          <span className="text-sm text-ink-500" data-not-price>of your <span className="num">{inr(plan.budget.budget_total)}</span></span>
        </p>
        <div aria-hidden className="mt-2 h-1 rounded-full bg-sand-200">
          <div className="h-1 rounded-full bg-accent-600" style={{ width: `${Math.round(share * 100)}%` }} />
        </div>
      </div>
      <CheckList />
      <ValueBar score={score} rank={rank} />
      <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-ink-500">Hotel</dt><dd>{plan.hotel.name} <span className="text-ink-500">({TIER_LABEL[plan.hotel.tier]})</span></dd>
        <dt className="text-ink-500">Outbound</dt><dd>{MODE_LABEL[o.mode]} {o.class}{o.overnight ? ", overnight" : ""}</dd>
        <dt className="text-ink-500">Return</dt><dd>{MODE_LABEL[r.mode]} {r.class}{r.overnight ? ", overnight" : ""}</dd>
        <dt className="text-ink-500">Activities</dt><dd className="num">{stops.length}</dd>
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
        <p className="mt-2 text-center text-xs text-ink-500">You can come back and pick another plan later.</p>
      </div>
    </article>
  );
}
