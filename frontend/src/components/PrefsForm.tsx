import type { Comfort, DraftPrefs, Meta, Mode, ModePref, Pace, Tag } from "../api/types";
import { FieldError } from "./ui";

const TAG_LABEL: Record<Tag, string> = {
  nature: "Nature", adventure: "Adventure", food: "Food", history: "History & heritage", culture: "Culture & art",
  spiritual: "Spiritual", shopping: "Shopping", relaxation: "Relaxation", nightlife: "Nightlife",
};
const PACE_HELP: Record<Pace, string> = { relaxed: "up to 3 a day", balanced: "up to 4 a day", packed: "up to 6 a day" };
const COMFORT_HELP: Record<Comfort, string> = { budget: "hostels, guesthouses", mid: "comfortable hotels", premium: "top hotels" };

/** One line naming the current preferences, e.g. "9 h a day · balanced pace · mid-range stays · likes Food, History & heritage". */
export function prefsSummary(p: DraftPrefs): string {
  if (p.daily_hours_out === null && p.pace === null && p.comfort === null && Object.values(p.interests).every((w) => w === 0))
    return "Not set yet: choose your hours, pace, stay comfort and at least one interest.";
  const liked = (Object.keys(p.interests) as Tag[]).filter((t) => p.interests[t] >= 4).map((t) => TAG_LABEL[t]);
  return [p.daily_hours_out === null ? "hours not chosen" : `${p.daily_hours_out} h a day`,
          p.pace === null ? "pace not chosen" : `${p.pace} pace`,
          p.comfort === null ? "stay comfort not chosen" : `${p.comfort === "mid" ? "mid-range" : p.comfort} stays`,
          liked.length ? `likes ${liked.join(", ")}` : null].filter(Boolean).join(" · ");
}

interface Props {
  value: DraftPrefs;
  onChange: (p: DraftPrefs) => void;
  meta: Meta;
  errors: Record<string, string>;
}

export default function PrefsForm({ value, onChange, meta, errors }: Props) {
  const set = <K extends keyof DraftPrefs>(k: K, v: DraftPrefs[K]) => onChange({ ...value, [k]: v });
  const [lo, hi] = meta.limits.hours_out;
  const err = (k: string) => errors[`prefs.${k}`];
  return (
    <div className="space-y-6">
      <div className="max-w-xs">
        <label htmlFor="hours" className="label">Hours out each day</label>
        <select id="hours" className="input" value={value.daily_hours_out ?? ""} aria-invalid={!!err("daily_hours_out")}
                aria-describedby="hours-err" onChange={(e) => set("daily_hours_out", e.target.value === "" ? null : Number(e.target.value))}>
          <option value="">Choose hours</option>
          {Array.from({ length: hi - lo + 1 }, (_, i) => lo + i).map((h) => <option key={h} value={h}>{h} hours</option>)}
        </select>
        <FieldError id="hours-err" message={err("daily_hours_out")} />
      </div>

      <fieldset>
        <legend className="label">What do you enjoy? <span className="font-normal text-ink-500">(0 = not at all, 5 = love it)</span></legend>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 lg:grid-cols-3">
          {meta.interests.map((t) => (
            <div key={t}>
              <div className="flex justify-between gap-2 text-sm text-ink-700">
                <label htmlFor={`int-${t}`}>{TAG_LABEL[t]}</label>
                <span aria-hidden className="font-semibold text-ink-900">{value.interests[t]}</span>
              </div>
              <input id={`int-${t}`} type="range" min={0} max={5} step={1} value={value.interests[t]} className="w-full accent-accent-700"
                     aria-valuetext={`${value.interests[t]} of 5`} aria-describedby={err("interests") ? "interests-err" : undefined}
                     onChange={(e) => set("interests", { ...value.interests, [t]: Number(e.target.value) })} />
            </div>
          ))}
        </div>
        <FieldError id="interests-err" message={errors["prefs.interests"]} />
      </fieldset>

      <div className="grid gap-6 sm:grid-cols-2">
        <fieldset aria-describedby={err("pace") ? "pace-err" : undefined}>
          <legend className="label">Pace</legend>
          <div>
            {meta.paces.map((p) => (
              <label key={p} className="flex min-h-11 items-center gap-2 text-sm">
                <input id={`pace-${p}`} type="radio" name="pace" value={p} checked={value.pace === p} onChange={() => set("pace", p)}
                       className="accent-accent-700" />
                <span className="capitalize">{p}</span> <span className="text-ink-500">— {PACE_HELP[p]}</span>
              </label>
            ))}
          </div>
          <FieldError id="pace-err" message={err("pace")} />
        </fieldset>
        <fieldset aria-describedby={err("comfort") ? "comfort-err" : undefined}>
          <legend className="label">Stay comfort</legend>
          <div>
            {meta.comforts.map((c) => (
              <label key={c} className="flex min-h-11 items-center gap-2 text-sm">
                <input id={`comfort-${c}`} type="radio" name="comfort" value={c} checked={value.comfort === c} onChange={() => set("comfort", c)}
                       className="accent-accent-700" />
                <span>{c === "mid" ? "Mid-range" : c === "budget" ? "Budget" : "Premium"}</span> <span className="text-ink-500">— {COMFORT_HELP[c]}</span>
              </label>
            ))}
          </div>
          <FieldError id="comfort-err" message={err("comfort")} />
        </fieldset>
      </div>

      <fieldset>
        <legend className="label">Transport</legend>
        <div className="grid gap-3 sm:grid-cols-3">
          {meta.modes.map((m: Mode) => (
            <div key={m}>
              <label htmlFor={`mode-${m}`} className="text-sm capitalize text-ink-700">{m}</label>
              <select id={`mode-${m}`} className="input mt-1" value={value.modes[m]}
                      onChange={(e) => set("modes", { ...value.modes, [m]: e.target.value as ModePref })}>
                {meta.mode_prefs.map((v) => <option key={v} value={v}>{v === "avoid" ? "Avoid" : v === "preferred" ? "Preferred" : "Neutral"}</option>)}
              </select>
            </div>
          ))}
        </div>
        <FieldError id="modes-err" message={errors["prefs.modes"]} />
      </fieldset>

      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={value.avoid_crowds} onChange={(e) => set("avoid_crowds", e.target.checked)} className="h-4 w-4 accent-accent-700" />
        Avoid crowded places
      </label>
    </div>
  );
}
