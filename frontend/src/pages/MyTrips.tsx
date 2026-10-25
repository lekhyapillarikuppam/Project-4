import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { TripSummary } from "../api/types";
import ConfirmDialog from "../components/ConfirmDialog";
import { ErrorBox, PageTitle, Skeleton } from "../components/ui";
import { inr, niceDate, VARIANT_LABEL } from "../lib/format";
import { useCityName } from "../lib/meta";

type Tab = "upcoming" | "past";

function TripRow({ t, onDelete }: { t: TripSummary; onDelete: (t: TripSummary) => void }) {
  const city = useCityName();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(t.name);
  const rename = useMutation({
    mutationFn: () => api.renameTrip(t.id, name.trim()),
    onSuccess: () => { setEditing(false); qc.invalidateQueries({ queryKey: ["trips"] }); },
  });
  const duplicate = useMutation({
    mutationFn: () => api.duplicateTrip(t.id),
    onSuccess: (r) => navigate("/new", { state: { request: r.request } }),
  });
  const link = t.selected_variant ? `/trips/${t.id}/plan` : `/trips/${t.id}`;
  return (
    <li className="card flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        {editing ? (
          <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) rename.mutate(); }}>
            <label htmlFor={`name-${t.id}`} className="sr-only">Trip name</label>
            <input id={`name-${t.id}`} className="input w-64 max-w-full" value={name} maxLength={120} autoFocus
                   onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") { setEditing(false); setName(t.name); } }} />
            <button type="submit" className="btn-primary px-3 py-1" disabled={rename.isPending || !name.trim()}>Save</button>
            <button type="button" className="btn-secondary px-3 py-1" onClick={() => { setEditing(false); setName(t.name); }}>Cancel</button>
          </form>
        ) : (
          <h2 className="truncate text-lg font-semibold"><Link to={link} className="hover:underline">{t.name}</Link></h2>
        )}
        <p className="text-sm text-ink-700">
          {city(t.origin)} → {city(t.destination)} · {niceDate(t.start_date)} – {niceDate(t.end_date)} · {t.people} {t.people === 1 ? "person" : "people"} · <span data-not-price>budget {inr(t.budget_total)}</span>
        </p>
        <p className="text-sm text-ink-500">
          {t.status === "infeasible" ? "No plan fits yet" : t.selected_variant ? `${VARIANT_LABEL[t.selected_variant]} plan chosen` : "Plans ready to compare"}
        </p>
        {(rename.isError || duplicate.isError) && <ErrorBox error={rename.error || duplicate.error} />}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Link to={link} className="btn-secondary px-3 py-1">Open</Link>
        <button type="button" className="btn-secondary px-3 py-1" onClick={() => setEditing(true)} aria-label={`Rename ${t.name}`}>Rename</button>
        <button type="button" className="btn-secondary px-3 py-1" onClick={() => duplicate.mutate()} aria-label={`Duplicate ${t.name}`}>Duplicate</button>
        <button type="button" className="btn-secondary px-3 py-1 text-bad-700" onClick={() => onDelete(t)} aria-label={`Delete ${t.name}`}>Delete</button>
      </div>
    </li>
  );
}

export default function MyTrips() {
  const [tab, setTab] = useState<Tab>("upcoming");
  const qc = useQueryClient();
  const trips = useQuery({ queryKey: ["trips", tab], queryFn: () => api.listTrips(tab) });
  const [deleting, setDeleting] = useState<TripSummary | null>(null);
  const del = useMutation({
    mutationFn: (id: string) => api.deleteTrip(id),
    onSuccess: () => { setDeleting(null); qc.invalidateQueries({ queryKey: ["trips"] }); },
  });
  return (
    <div>
      <PageTitle sub="Your saved trips, plans and versions.">My Trips</PageTitle>
      <div role="tablist" aria-label="Trips" className="mb-4 flex gap-1 border-b border-sand-200">
        {(["upcoming", "past"] as Tab[]).map((k) => (
          <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls="trip-list" type="button"
                  className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${tab === k ? "border-accent-700 text-accent-800" : "border-transparent text-ink-700 hover:text-ink-900"}`}
                  onClick={() => setTab(k)}>
            {k === "upcoming" ? "Upcoming" : "Past"}
          </button>
        ))}
      </div>
      <div id="trip-list" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {trips.isError ? <ErrorBox error={trips.error} onRetry={() => trips.refetch()} />
          : !trips.data ? <Skeleton lines={4} />
          : trips.data.length === 0 ? (
            <p className="text-ink-700">{tab === "upcoming" ? <>No upcoming trips. <Link to="/new" className="btn-link">Plan one</Link></> : "No past trips yet."}</p>
          ) : (
            <ul className="space-y-3">{trips.data.map((t) => <TripRow key={t.id} t={t} onDelete={setDeleting} />)}</ul>
          )}
      </div>
      {deleting && (
        <ConfirmDialog title="Delete this trip?" body={`"${deleting.name}" and its plan versions and chat will be removed. This can't be undone.`}
                       confirmLabel="Delete trip" busy={del.isPending} onCancel={() => setDeleting(null)}
                       onConfirm={() => del.mutate(deleting.id)} />
      )}
    </div>
  );
}
