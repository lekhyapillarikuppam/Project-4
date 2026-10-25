import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { NearMiss, TradeOffs, VariantName, VersionSummary } from "../api/types";
import { inr, signedInr, VARIANT_LABEL } from "../lib/format";
import { ErrorBox, Price, Spinner } from "./ui";

const REASON: Record<NearMiss["reason"], string> = {
  budget: "didn't fit the budget",
  time: "didn't fit the time available",
  closed: "closed or not open at a reachable time",
};

export function NearMisses({ items }: { items: NearMiss[] }) {
  if (!items.length) return <p className="muted">Nothing important was left out.</p>;
  return (
    <ul className="space-y-1 text-sm">
      {items.map((n) => <li key={n.attraction_id}><span className="font-medium">{n.name}</span> — {REASON[n.reason]}</li>)}
    </ul>
  );
}

function unchanged(t: TradeOffs): boolean {
  return t.rows.every((r) => r.status === "ok" && !r.delta_cost && !r.delta_value && !r.added.length && !r.dropped.length
    && !r.hotel_change && !r.transport_change);
}

export function TradeOffsPanel({ tripId, variant, names }: { tripId: string; variant: VariantName; names: (id: string) => string }) {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["tradeoffs", tripId, variant], queryFn: () => api.tradeoffs(tripId, variant), enabled: open });
  if (!open) return <button type="button" className="btn-secondary" onClick={() => setOpen(true)}>Show what changes with more or less budget</button>;
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Spinner label="Re-planning at four budgets…" />;
  if (unchanged(q.data)) return <p className="rounded-md bg-sand-100 p-3 text-sm">Your plan is limited by time, not budget: 20% more or less money gives the same plan.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-sm">
        <thead><tr className="border-b border-sand-300 text-left">
          <th scope="col" className="py-1">Budget</th><th scope="col">Cost change</th><th scope="col">Value change</th><th scope="col">What changes</th>
        </tr></thead>
        <tbody>
          {q.data.rows.map((r) => (
            <tr key={r.factor} className="border-b border-sand-200 align-top">
              <td className="py-1 font-mono">{Math.round((r.factor - 1) * 100) > 0 ? "+" : ""}{Math.round((r.factor - 1) * 100)}% <span data-not-price className="text-ink-500">({inr(r.budget_total)})</span></td>
              {r.status !== "ok" ? <td colSpan={3} className="py-1 text-warn-700">No plan fits this budget</td> : (
                <>
                  <td className="py-1 font-mono"><Price>{signedInr(r.delta_cost ?? 0)}</Price></td>
                  <td className="py-1 font-mono">{(r.delta_value ?? 0) > 0 ? "+" : ""}{(r.delta_value ?? 0).toFixed(1)}</td>
                  <td className="py-1">
                    {r.added.length > 0 && <p>Adds {r.added.map(names).join(", ")}</p>}
                    {r.dropped.length > 0 && <p>Drops {r.dropped.map(names).join(", ")}</p>}
                    {r.hotel_change && <p>Different hotel</p>}
                    {r.transport_change && <p>Transport {r.transport_change[1]}</p>}
                    {!r.added.length && !r.dropped.length && !r.hotel_change && !r.transport_change && <p className="text-ink-500">Same plan</p>}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SOURCE: Record<VersionSummary["source"], string> = { select: "Chosen", replan: "Re-planned", chat: "Chat change", restore: "Restored" };

export function VersionList({ tripId, versions, current }: { tripId: string; versions: VersionSummary[]; current: number }) {
  const qc = useQueryClient();
  const restore = useMutation({
    mutationFn: (v: number) => api.restore(tripId, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["versions", tripId] }),
  });
  return (
    <div>
      <ol className="space-y-2 text-sm">
        {[...versions].reverse().map((v) => (
          <li key={v.version} className="flex flex-wrap items-center justify-between gap-2 border-b border-sand-200 pb-2">
            <span>
              <strong>Version {v.version}</strong> · {SOURCE[v.source]}{v.variant ? ` · ${VARIANT_LABEL[v.variant]}` : ""}
              <span className="block text-ink-500">{v.note ?? ""} <Price>{inr(v.total)}</Price></span>
            </span>
            {v.version === current ? <span className="text-xs font-semibold text-accent-700">Current</span> : (
              <button type="button" className="btn-secondary px-3 py-1" disabled={restore.isPending}
                      onClick={() => restore.mutate(v.version)}>
                Restore
              </button>
            )}
          </li>
        ))}
      </ol>
      {restore.isError && <ErrorBox error={restore.error} />}
    </div>
  );
}
