import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Trip, VariantName, VariantsResult } from "../api/types";
import VariantCard, { scoreWithin } from "../components/VariantCard";
import { ErrorBox, PageTitle, Price, Skeleton } from "../components/ui";
import { ExplanationNotice } from "../components/Explanation";
import { daysBetween, inr, niceDate, VARIANT_LABEL } from "../lib/format";
import { useCityName } from "../lib/meta";
import { useDocumentTitle } from "../lib/title";

/** The trip's facts as chips under its name; the route is repeated only when the name no longer says it. */
export function tripSubtitle(trip: Trip, city: (c: string) => string) {
  const r = trip.request;
  const route = `${city(r.origin)} to ${city(r.destination)}`;
  const days = daysBetween(r.start_date, r.end_date) + 1;
  return (
    <>
      {!trip.name.startsWith(route) && <span className="chip">{city(r.origin)} → {city(r.destination)}</span>}
      <span className="chip">{niceDate(r.start_date)} – {niceDate(r.end_date)} · {days} days</span>
      <span className="chip">{r.people} {r.people === 1 ? "person" : "people"}</span>
      <span className="chip" data-not-price>Budget <span className="num">{inr(r.budget_total)}</span></span>
    </>
  );
}

export default function Compare() {
  const { id = "" } = useParams();
  const trip = useQuery({ queryKey: ["trip", id], queryFn: () => api.getTrip(id) });
  const city = useCityName();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [choosing, setChoosing] = useState<VariantName | null>(null);
  const [error, setError] = useState<unknown>(null);
  useDocumentTitle(trip.data?.name ?? "Your plans");

  if (trip.isError) return <ErrorBox error={trip.error} onRetry={() => trip.refetch()} />;
  if (!trip.data) return <Skeleton lines={6} />;
  const t = trip.data;
  const res = t.result;

  async function choose(v: VariantName) {
    setChoosing(v);
    setError(null);
    try {
      await api.select(t.id, v);
      await qc.invalidateQueries({ queryKey: ["trip", t.id] });
      await qc.invalidateQueries({ queryKey: ["versions", t.id] });
      navigate(`/trips/${t.id}/plan`);
    } catch (e) {
      setError(e);
      setChoosing(null);
    }
  }

  if (res.status === "infeasible") {
    return (
      <div>
        <PageTitle sub={tripSubtitle(t, city)}>{t.name}</PageTitle>
        <section className="card space-y-3 border-warn-700/30 bg-warn-50" role="status">
          <h2 className="text-lg font-semibold text-warn-700">No plan fits this trip yet</h2>
          <p>{res.message}</p>
          {res.min_budget_total !== null && (
            <p className="text-lg">Minimum budget for these dates and people: <strong><Price>{inr(res.min_budget_total)}</Price></strong></p>
          )}
          <button type="button" className="btn-primary"
                  onClick={() => navigate("/new", { state: { request: { ...t.request } } })}>
            Edit budget
          </button>
        </section>
      </div>
    );
  }

  const vr = res as VariantsResult;
  const values = vr.variants.map((p) => p.value);
  const ranked = [...values].sort((a, b) => b - a);
  return (
    <div>
      <PageTitle sub={tripSubtitle(t, city)}>{t.name}</PageTitle>
      {t.selected_variant && (
        <p className="mb-4 text-sm">
          You chose {VARIANT_LABEL[t.selected_variant]}. <Link to={`/trips/${t.id}/plan`} className="btn-link">Open your plan</Link>
        </p>
      )}
      <div className="mb-4 space-y-1 text-sm text-ink-700">
        <p>Every plan below was checked by the planner against your budget, opening hours, travel times and daily time limit.
          Value compares these plans with each other: places that match your interests, comfort and less time in transit.</p>
        <ExplanationNotice tripId={t.id} />
      </div>
      <div className={`grid gap-4 ${vr.variants.length === 3 ? "md:grid-cols-3" : vr.variants.length === 2 ? "md:grid-cols-2" : ""}`}>
        {vr.variants.map((p) => (
          <VariantCard key={p.variant} plan={p} score={scoreWithin(values, p.value)}
                       rank={values.length === 1 ? "only" : p.value === ranked[0] ? "most" : p.value === ranked[ranked.length - 1] ? "least" : "middle"}
                       onChoose={() => choose(p.variant!)} choosing={choosing === p.variant} tripId={t.id} />
        ))}
      </div>
      {vr.dropped.length > 0 && (
        <div className="mt-4 rounded-md bg-sand-100 p-3 text-sm text-ink-700">
          <p className="font-medium">Why fewer than three plans?</p>
          <ul className="list-inside list-disc">
            {vr.dropped.map((d) => <li key={d.name}>{VARIANT_LABEL[d.name]}: {d.reason.toLowerCase()}, so it isn't shown.</li>)}
          </ul>
        </div>
      )}
      {error !== null && <div className="mt-4"><ErrorBox error={error} /></div>}
    </div>
  );
}
