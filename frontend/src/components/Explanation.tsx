import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { VariantName } from "../api/types";
import { TextWithPrices } from "./ui";

/** AI explanation of one variant (AI-FR-02, AI-FR-08). Grounded or template text from the API; never blocks the plan. */
export default function Explanation({ tripId, variant }: { tripId: string; variant: VariantName }) {
  const q = useQuery({ queryKey: ["explanations", tripId], queryFn: () => api.explanations(tripId), staleTime: Infinity, retry: false });
  if (q.isPending) return <p className="text-sm text-ink-500" aria-live="polite">Writing a short explanation…</p>;
  if (q.isError || !q.data) return null;
  if (q.data.status === "unavailable") return null;          // said once, by ExplanationNotice
  const text = q.data.texts[variant];
  if (!text) return null;
  return (
    <div className="rounded-md bg-sand-100 p-3 text-sm text-ink-900">
      <p className="mb-1 text-xs font-semibold text-ink-700">
        Why this plan{q.data.source[variant] === "template" ? "" : <span className="font-normal text-ink-500"> · AI summary of the plan</span>}
      </p>
      <p><TextWithPrices text={text} /></p>
    </div>
  );
}

/** The "explanations unavailable" notice, shown once for the page rather than in every card. */
export function ExplanationNotice({ tripId }: { tripId: string }) {
  const q = useQuery({ queryKey: ["explanations", tripId], queryFn: () => api.explanations(tripId), staleTime: Infinity, retry: false });
  return q.data?.status === "unavailable" ? <p className="text-ink-500">{q.data.notice}</p> : null;
}
