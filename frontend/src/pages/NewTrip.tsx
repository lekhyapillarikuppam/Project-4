import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Prefs, TripForm } from "../api/types";
import DescribeTrip from "../components/DescribeTrip";
import PrefsForm from "../components/PrefsForm";
import { ErrorBox, FieldError, PageTitle, Skeleton } from "../components/ui";
import { addDays, todayIST } from "../lib/format";
import { useCities, useMeta } from "../lib/meta";
import { validateTrip, type Errors } from "../lib/validate";

type Draft = Omit<TripForm, "budget_total" | "budget_per_person"> & { budget: string; per: boolean };

function draftFrom(req: Partial<TripForm> | undefined, prefs: Prefs): Draft {
  const start = addDays(todayIST(), 30);
  return {
    origin: req?.origin ?? "", destination: req?.destination ?? "",
    start_date: req?.start_date ?? start, end_date: req?.end_date ?? addDays(start, 2),
    people: req?.people ?? 2, prefs: req?.prefs ?? prefs, locks: req?.locks ?? [], excludes: req?.excludes ?? [],
    budget: req?.budget_total ? String(req.budget_total) : "30000", per: false,
  };
}

function toForm(d: Draft): TripForm {
  const amount = d.budget.trim() === "" ? NaN : Number(d.budget);
  const { budget, per, ...rest } = d;
  void budget;
  return per ? { ...rest, budget_per_person: amount } : { ...rest, budget_total: amount };
}

export default function NewTrip() {
  const meta = useMeta();
  const cities = useCities();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const loc = useLocation();
  const navigate = useNavigate();
  const incoming = (loc.state as { request?: Partial<TripForm> } | null)?.request;
  const [draft, setDraft] = useState<Draft | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (draft === null && profile.data) setDraft(draftFrom(incoming, profile.data.prefs));
  }, [profile.data, incoming, draft]);

  if (meta.isError || profile.isError || cities.isError) return <ErrorBox error={meta.error || profile.error || cities.error} />;
  if (!meta.data || !draft || !cities.data) return <Skeleton lines={8} />;
  const m = meta.data;
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft({ ...draft, [k]: v });

  async function submit(e: FormEvent) {
    e.preventDefault();
    const form = toForm(draft!);
    const errs = validateTrip(form, m);
    setErrors(errs);
    setError(null);
    if (Object.keys(errs).length) {
      document.getElementById(`f-${Object.keys(errs)[0].split(".")[0]}`)?.focus();
      return;
    }
    setBusy(true);
    try {
      const trip = await api.createTrip(form);
      navigate(`/trips/${trip.id}`);
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setErrors(err.fields);
      setError(err);
      setBusy(false);
    }
  }

  const budgetField = draft.per ? "budget_per_person" : "budget_total";
  const days = draft.start_date && draft.end_date
    ? Math.round((Date.parse(draft.end_date) - Date.parse(draft.start_date)) / 86_400_000) + 1 : null;
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
                   aria-invalid={!!errors.start_date} aria-describedby="start-err" onChange={(e) => set("start_date", e.target.value)} />
            <FieldError id="start-err" message={errors.start_date} />
          </div>
          <div>
            <label htmlFor="f-end_date" className="label">End date {days !== null && days > 0 && <span className="font-normal text-ink-500">({days} days)</span>}</label>
            <input id="f-end_date" type="date" className="input" value={draft.end_date} min={draft.start_date}
                   aria-invalid={!!errors.end_date} aria-describedby="end-err" onChange={(e) => set("end_date", e.target.value)} />
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
                     aria-invalid={!!errors[budgetField]} aria-describedby="budget-err" onChange={(e) => set("budget", e.target.value)} />
              <div role="radiogroup" aria-label="Budget is" className="flex shrink-0 overflow-hidden rounded-md border border-sand-300">
                {[false, true].map((per) => (
                  <button key={String(per)} type="button" role="radio" aria-checked={draft.per === per}
                          className={`px-3 text-sm ${draft.per === per ? "bg-accent-700 text-white" : "bg-white text-ink-700"}`}
                          onClick={() => set("per", per)}>
                    {per ? "Per person" : "Total"}
                  </button>
                ))}
              </div>
            </div>
            <FieldError id="budget-err" message={errors[budgetField]} />
          </div>
        </section>
        <section className="card">
          <h2 className="mb-4 text-lg font-semibold">Your preferences</h2>
          <PrefsForm value={draft.prefs} onChange={(p) => set("prefs", p)} meta={m} errors={errors} />
        </section>
        {error !== null && <ErrorBox error={error}
          onRetry={error instanceof ApiError && error.status === 429 ? () => document.querySelector<HTMLFormElement>("form")?.requestSubmit() : undefined} />}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className="btn-primary px-6 py-3 text-base" disabled={busy}>
            {busy ? "Planning…" : "Plan my trip"}
          </button>
          {busy && <p role="status" className="text-sm text-ink-700">Planning your trip… usually under 5 s.</p>}
        </div>
      </form>
    </div>
  );
}
