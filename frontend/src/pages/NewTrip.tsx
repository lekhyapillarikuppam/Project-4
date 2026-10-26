import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { DraftPrefs, Meta, TripForm } from "../api/types";
import DescribeTrip from "../components/DescribeTrip";
import PrefsForm, { prefsSummary } from "../components/PrefsForm";
import { ErrorBox, FieldError, PageTitle, Skeleton } from "../components/ui";
import { addDays, todayIST } from "../lib/format";
import { useDocumentTitle } from "../lib/title";
import { useCities, useMeta } from "../lib/meta";
import { fieldId, tripDays, validateDates, validateTrip, type DraftTripForm, type Errors } from "../lib/validate";

type Draft = Omit<DraftTripForm, "budget_total" | "budget_per_person" | "name"> & { budget: string; per: boolean; name: string };

/** Blank preferences (UI-FR-02): nothing chosen, interests 0, transport neutral, crowds allowed. */
function blankPrefs(meta: Meta): DraftPrefs {
  return {
    daily_hours_out: null, pace: null, comfort: null, avoid_crowds: false,
    interests: Object.fromEntries(meta.interests.map((t) => [t, 0])) as DraftPrefs["interests"],
    modes: Object.fromEntries(meta.modes.map((m) => [m, "neutral"])) as DraftPrefs["modes"],
  };
}

function draftFrom(req: Partial<TripForm> | undefined, name: string | undefined, meta: Meta): Draft {
  const start = addDays(todayIST(), 30);
  return {
    origin: req?.origin ?? "", destination: req?.destination ?? "",
    start_date: req?.start_date ?? start, end_date: req?.end_date ?? addDays(start, 2),
    people: req?.people ?? 2, prefs: req?.prefs ?? blankPrefs(meta), locks: req?.locks ?? [], excludes: req?.excludes ?? [],
    budget: req?.budget_total ? String(req.budget_total) : "", per: false, name: name ?? "",
  };
}

function toForm(d: Draft): DraftTripForm {
  const amount = d.budget.trim() === "" ? NaN : Number(d.budget);
  const { budget, per, name, ...rest } = d;
  void budget;
  const named = name.trim() ? { name: name.trim() } : {};
  return per ? { ...rest, ...named, budget_per_person: amount } : { ...rest, ...named, budget_total: amount };
}

/** The name the API gives a trip left unnamed: "Delhi to Agra, 05 Nov 2026" (backend default_name). */
function autoName(d: Draft, cityName: (code: string) => string): string {
  if (!d.origin || !d.destination || !d.start_date) return "Named from your cities and start date";
  const day = new Date(`${d.start_date}T00:00:00`);
  const date = `${String(day.getDate()).padStart(2, "0")} ${day.toLocaleString("en-GB", { month: "short" })} ${day.getFullYear()}`;
  return `${cityName(d.origin)} to ${cityName(d.destination)}, ${date}`;
}

export default function NewTrip() {
  const meta = useMeta();
  const cities = useCities();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const loc = useLocation();
  const navigate = useNavigate();
  const state = loc.state as { request?: Partial<TripForm>; name?: string } | null;
  const incoming = state?.request;
  const [draft, setDraft] = useState<Draft | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useDocumentTitle("New trip");

  useEffect(() => {
    if (draft === null && meta.data) setDraft(draftFrom(incoming, state?.name, meta.data));
  }, [meta.data, incoming, state?.name, draft]);

  if (meta.isError || cities.isError) return <ErrorBox error={meta.error || cities.error} />;
  if (!meta.data || !draft || !cities.data) return <Skeleton lines={8} />;
  const m = meta.data;
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft({ ...draft, [k]: v });
  /** A date changed: recheck both dates at once (UI-FR-02); other fields keep their submit-time errors. */
  const setDate = (k: "start_date" | "end_date", v: string) => {
    const next = { ...draft, [k]: v };
    setDraft(next);
    const { start_date: _s, end_date: _e, ...others } = errors;
    void _s; void _e;
    setErrors({ ...others, ...validateDates(next, m) });
  };
  const cityName = (code: string) => cities.data!.find((c) => c.code === code)?.name ?? code;
  const saved = profile.data?.saved === true;

  async function submit(e: FormEvent) {
    e.preventDefault();
    const form = toForm(draft!);
    const errs = validateTrip(form, m);
    setErrors(errs);
    setError(null);
    if (Object.keys(errs).length) {
      document.getElementById(fieldId(Object.keys(errs)[0], m))?.focus();
      return;
    }
    setBusy(true);
    try {
      const trip = await api.createTrip(form as TripForm);       // validated: hours, pace and comfort are chosen
      navigate(`/trips/${trip.id}`);
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields);
      setError(err);
      setBusy(false);
    }
  }

  const budgetField = draft.per ? "budget_per_person" : "budget_total";
  function radioKeys(e: KeyboardEvent<HTMLDivElement>) {        // arrow keys move the choice (ARIA radio group)
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    e.preventDefault();
    set("per", !draft!.per);
    requestAnimationFrame(() => e.currentTarget?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus());
  }
  const days = draft.start_date && draft.end_date ? tripDays(draft.start_date, draft.end_date) : null;
  const [minDays, maxDays] = m.limits.trip_days;
  const dayCount = days === null ? null
    : days < 1 ? <span className="font-normal text-bad-700">(check dates)</span>
    : <span className={`font-normal ${days < minDays || days > maxDays ? "text-bad-700" : "text-ink-500"}`}>({days} {days === 1 ? "day" : "days"})</span>;
  return (
    <div>
      <PageTitle sub={incoming ? "Adjust the details and plan again." : "Tell us about your trip."}>New trip</PageTitle>
      <div className="mb-6">
        <DescribeTrip onParsed={(p) => setDraft({
          ...draft, prefs: p.prefs,
          ...(p.origin ? { origin: p.origin } : {}), ...(p.destination ? { destination: p.destination } : {}),
          ...(p.start_date ? { start_date: p.start_date } : {}), ...(p.end_date ? { end_date: p.end_date } : {}),
          ...(p.people ? { people: p.people } : {}),
          ...(p.budget_total ? { budget: String(p.budget_total), per: false } : {}),
          ...(p.budget_per_person ? { budget: String(p.budget_per_person), per: true } : {}),
        })} />
      </div>
      <form onSubmit={submit} noValidate className="space-y-6" aria-busy={busy}>
        <section className="card grid gap-4 sm:grid-cols-2">
          {(["origin", "destination"] as const).map((k) => (
            <div key={k}>
              <label htmlFor={`f-${k}`} className="label">{k === "origin" ? "From" : "To"}</label>
              <select id={`f-${k}`} className="input" value={draft[k]} aria-invalid={!!errors[k]} aria-describedby={`${k}-err`}
                      onChange={(e) => set(k, e.target.value)}>
                <option value="">Choose a city</option>
                {cities.data.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
              </select>
              <FieldError id={`${k}-err`} message={errors[k]} />
            </div>
          ))}
          <div>
            <label htmlFor="f-start_date" className="label">Start date</label>
            <input id="f-start_date" type="date" className="input" value={draft.start_date} min={addDays(todayIST(), 1)}
                   max={addDays(todayIST(), m.limits.max_days_ahead)}
                   aria-invalid={!!errors.start_date} aria-describedby="start-err" onChange={(e) => setDate("start_date", e.target.value)} />
            <FieldError id="start-err" message={errors.start_date} />
          </div>
          <div>
            <label htmlFor="f-end_date" className="label">End date {dayCount}</label>
            <input id="f-end_date" type="date" className="input" value={draft.end_date}
                   min={draft.start_date || undefined} max={draft.start_date ? addDays(draft.start_date, maxDays - 1) : undefined}
                   aria-invalid={!!errors.end_date} aria-describedby="end-err" onChange={(e) => setDate("end_date", e.target.value)} />
            <FieldError id="end-err" message={errors.end_date} />
          </div>
          <div>
            <label htmlFor="f-people" className="label">People</label>
            <input id="f-people" type="number" inputMode="numeric" min={m.limits.people[0]} max={m.limits.people[1]} className="input"
                   value={Number.isNaN(draft.people) ? "" : draft.people} aria-invalid={!!errors.people} aria-describedby="people-err"
                   onChange={(e) => set("people", e.target.value === "" ? NaN : Number(e.target.value))} />
            <FieldError id="people-err" message={errors.people} />
          </div>
          <div>
            <label htmlFor={`f-${budgetField}`} className="label">Budget (₹)</label>
            <div className="flex gap-2">
              <input id={`f-${budgetField}`} type="number" inputMode="numeric" min={0} step={500} className="input" value={draft.budget}
                     placeholder="e.g. 30000"
                     aria-invalid={!!errors[budgetField]} aria-describedby="budget-err" onChange={(e) => set("budget", e.target.value)} />
              <div role="radiogroup" aria-label="Budget is" onKeyDown={radioKeys}
                   className="flex shrink-0 overflow-hidden rounded-md border border-sand-500">
                {[false, true].map((per) => (
                  <button key={String(per)} type="button" role="radio" aria-checked={draft.per === per} tabIndex={draft.per === per ? 0 : -1}
                          className={`min-h-11 px-3 text-sm ${draft.per === per ? "bg-accent-700 text-white" : "bg-white text-ink-700"}`}
                          onClick={() => set("per", per)}>
                    {per ? "Per person" : "Total"}
                  </button>
                ))}
              </div>
            </div>
            <FieldError id="budget-err" message={errors[budgetField]} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="f-name" className="label">Trip name <span className="font-normal text-ink-500">(optional)</span></label>
            <input id="f-name" className="input" maxLength={120} value={draft.name} placeholder={autoName(draft, cityName)}
                   aria-invalid={!!errors.name} aria-describedby="name-err" onChange={(e) => set("name", e.target.value)} />
            <FieldError id="name-err" message={errors.name} />
          </div>
        </section>
        <section className="card">
          <h2 className="text-lg font-semibold">Your preferences</h2>
          <p className="mt-1 text-sm text-ink-500">{prefsSummary(draft.prefs)}</p>
          <div className="mb-4 mt-3 flex flex-wrap items-center gap-3">
            <button type="button" className="btn-secondary btn-sm" disabled={!saved}
                    aria-describedby={saved ? undefined : "fill-hint"}
                    onClick={() => { if (profile.data?.saved) { set("prefs", profile.data.prefs); setErrors({}); } }}>
              Fill from my profile
            </button>
            {!saved && profile.data && <p id="fill-hint" className="text-sm text-ink-500">Save your preferences in Profile first.</p>}
          </div>
          <PrefsForm value={draft.prefs} onChange={(p) => set("prefs", p)} meta={m} errors={errors} />
        </section>
        {error !== null && <ErrorBox error={error}
          onRetry={error instanceof ApiError && error.status === 429 ? () => document.querySelector<HTMLFormElement>("form")?.requestSubmit() : undefined} />}
        <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center gap-3 border-t border-sand-200 bg-sand-50/95 px-4 py-3
                        sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0">
          <button type="submit" className="btn-primary px-6 py-3 text-base" disabled={busy}>
            {busy ? "Planning…" : "Plan my trip"}
          </button>
          {busy && <p role="status" className="text-sm text-ink-700">Planning your trip… usually under 5 s.</p>}
        </div>
      </form>
    </div>
  );
}
