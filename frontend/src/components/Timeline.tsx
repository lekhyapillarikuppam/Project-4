import type { Day, Plan } from "../api/types";
import { duration, inr, niceDate, weekday } from "../lib/format";
import { DAY_COLOURS } from "./DayColours";
import { Price } from "./ui";

function LegLine({ minutes, km, mode, cost, note }: { minutes: number; km: number; mode: string; cost: number; note?: string }) {
  return (
    <p className="ml-[5.75rem] border-l-2 border-dashed border-sand-300 py-1 pl-3 text-[13px] text-ink-500">
      {mode === "auto" ? "Auto" : "Cab"}{note ? ` ${note}` : ""} · {duration(minutes)} · <span className="num">{km} km</span> · <Price className="num">{inr(cost)}</Price>
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
  return (
    <p className="ml-[5.75rem] py-1">
      <span className="num rounded bg-sand-100 px-2 py-0.5 text-xs font-medium text-ink-700">Lunch {day.lunch![0]}–{day.lunch![1]}</span>
    </p>
  );
}

function DayBlock({ day }: { day: Day }) {
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
              <LegLine {...s.leg_from_prev} note={i === 0 ? "from the hotel" : undefined} />
              {li === i && <Lunch day={day} />}
              <div className="grid grid-cols-[5rem,1fr] gap-x-3 py-0.5">
                <span className="num pt-px text-sm text-ink-700">{s.start}–{s.end}</span>
                <span>
                  <span className="text-[15px] font-semibold">{i + 1}. {s.name}</span>{" "}
                  <span className="block text-sm text-ink-500 sm:inline">{s.entry_cost ? <Price className="num">{inr(s.entry_cost)}</Price> : "free entry"}</span>
                </span>
              </div>
            </li>
          ))}
          {day.return_leg && <li><LegLine {...day.return_leg} note="back to the hotel" /></li>}
          {li === day.stops.length && <li><Lunch day={day} /></li>}
        </ol>
      )}
    </section>
  );
}

export default function Timeline({ plan }: { plan: Plan }) {
  return (
    <div className="space-y-3">
      {plan.days.map((d) => <DayBlock key={d.day} day={d} />)}
    </div>
  );
}
