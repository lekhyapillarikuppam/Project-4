import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { VariantName } from "../api/types";
import { TextWithPrices } from "./ui";

/** AI explanation of one variant (AI-FR-02, AI-FR-08). Grounded or template text from the API; never blocks the plan. */
export default function Explanation({ tripId, variant }: { tripId: string; variant: VariantName }) {
  const q = useQuery({ queryKey: ["explanations", tripId], queryFn: () => api.explanations(tripId), staleTime: Infinity, retry: false });
  if (q.isPending) return <p className="text-sm text-ink-500" aria-live="polite">Writing a short explanation…</p>;
  if (q.isError || !q.data) return null;
  if (q.data.status === "unavailable") return <p className="text-sm text-ink-500">{q.data.notice}</p>;
  const text = q.data.texts[variant];
  if (!text) return null;
  return (
    <div className="rounded-md bg-sand-100 p-3 text-sm text-ink-900">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-500">
        Why this plan{q.data.source[variant] === "template" ? "" : " · AI summary of the plan"}
      </p>
      <p><TextWithPrices text={text} /></p>
    </div>
  );
}
