import type { Day, Plan } from "../api/types";
import { duration, inr, niceDate, weekday } from "../lib/format";
import { DAY_COLOURS } from "./DayColours";
import { Price } from "./ui";

function LegLine({ minutes, km, mode, cost, note }: { minutes: number; km: number; mode: string; cost: number; note?: string }) {
  return (
    <p className="ml-6 border-l-2 border-dashed border-sand-300 py-1 pl-3 text-xs text-ink-500">
      {mode === "auto" ? "Auto" : "Cab"} · {duration(minutes)} · {km} km · <Price>{inr(cost)}</Price>{note ? ` · ${note}` : ""}
    </p>
  );
}

/** Index of the stop that lunch comes before (stops.length: after the last stop). Times are HH:MM strings. */
function lunchBefore(day: Day): number {
  if (!day.lunch) return -1;
  const [ls, le] = day.lunch;
  for (let i = 0; i < day.stops.length; i++) {
    const prevEnd = i === 0 ? "00:00" : day.stops[i - 1].end;
    if (ls >= prevEnd && le <= day.stops[i].start) return i;
  }
  return day.stops.length;
}

function Lunch({ day }: { day: Day }) {
  return <p className="ml-6 pl-3 text-xs font-medium text-ink-700">Lunch {day.lunch![0]}–{day.lunch![1]}</p>;
}

function DayBlock({ day, hotel }: { day: Day; hotel: string }) {
  const colour = DAY_COLOURS[(day.day - 1) % DAY_COLOURS.length];
  const li = lunchBefore(day);
  return (
    <section aria-labelledby={`day-${day.day}`} className="card">
      <h3 id={`day-${day.day}`} className="flex flex-wrap items-baseline gap-2 font-semibold">
        <span aria-hidden className="inline-block h-3 w-3 rounded-full" style={{ background: colour }} />
        Day {day.day} · {weekday(day.weekday)} {niceDate(day.date)}
        <span className="text-sm font-normal text-ink-500">
          {day.window ? `out ${day.window[0]}–${day.window[1]}` : "travel day, no time for activities"}
        </span>
      </h3>
      {day.stops.length === 0 ? (
        <p className="muted mt-2">{day.window ? "A free day at your own pace." : ""}</p>
      ) : (
        <ol className="mt-3 space-y-1">
          {day.stops.map((s, i) => (
            <li key={s.attraction_id}>
              <LegLine {...s.leg_from_prev} note={i === 0 ? `from ${hotel}` : undefined} />
              {li === i && <Lunch day={day} />}
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span className="w-28 shrink-0 font-mono text-sm text-ink-700">{s.start}–{s.end}</span>
                <span className="font-medium">{i + 1}. {s.name}</span>
                <span className="text-sm text-ink-500">{s.entry_cost ? <Price>{inr(s.entry_cost)}</Price> : "free entry"}</span>
              </div>
            </li>
          ))}
          {day.return_leg && <li><LegLine {...day.return_leg} note={`back to ${hotel}`} /></li>}
          {li === day.stops.length && <li><Lunch day={day} /></li>}
        </ol>
      )}
    </section>
  );
}

export default function Timeline({ plan }: { plan: Plan }) {
  return (
    <div className="space-y-3">
      {plan.days.map((d) => <DayBlock key={d.day} day={d} hotel={plan.hotel.name} />)}
    </div>
  );
}
