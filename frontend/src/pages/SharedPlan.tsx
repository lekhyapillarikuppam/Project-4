import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { BudgetDonut, BudgetTable } from "../components/Budget";
import DayMap from "../components/DayMap";
import { DownloadPdf, factsFor, GettingThere, Section } from "../components/PlanSections";
import Timeline from "../components/Timeline";
import { EstimatedLabel, ErrorBox, PageTitle, Price, Skeleton } from "../components/ui";
import { inr, niceDate } from "../lib/format";
import { useCityName } from "../lib/meta";
import { useDocumentTitle } from "../lib/title";

/** Keep shared plans out of search engines (UI-FR-10); Vercel also sends X-Robots-Tag for /s/*. */
function useNoIndex() {
  useEffect(() => {
    const m = document.createElement("meta");
    m.name = "robots";
    m.content = "noindex";
    document.head.appendChild(m);
    return () => { m.remove(); };
  }, []);
}

/** Read-only shared plan (UI-FR-10, FR-048): no chat, editing, versions or trade-offs. */
export default function SharedPlan() {
  const { token = "" } = useParams();
  const shared = useQuery({ queryKey: ["shared", token], queryFn: () => api.shared(token), retry: false });
  const city = useCityName();
  const places = useQuery({ queryKey: ["places", shared.data?.destination], queryFn: () => api.places(shared.data!.destination),
                            enabled: !!shared.data, staleTime: Infinity });
  useNoIndex();
  useDocumentTitle(shared.data ? `${shared.data.name} (shared plan)` : "Shared plan");

  if (shared.error instanceof ApiError && shared.error.status === 404) {
    return (
      <div className="mx-auto max-w-lg py-8">
        <PageTitle sub="The link may have been turned off by the person who shared it, or it was copied wrongly.">
          This shared plan isn't available
        </PageTitle>
        <Link to="/" className="btn-primary">Plan your own trip</Link>
      </div>
    );
  }
  if (shared.error) return <ErrorBox error={shared.error} onRetry={() => shared.refetch()} />;
  if (!shared.data) return <Skeleton lines={8} />;
  const s = shared.data;
  const plan = s.plan;

  return (
    <div className="min-w-0 space-y-8">
      <div>
        <p className="mb-2"><span className="chip bg-accent-50 font-medium text-accent-800">Shared plan · prices are estimates</span></p>
        <PageTitle sub={<span>{city(s.origin)} → {city(s.destination)} · {niceDate(s.start_date)} – {niceDate(s.end_date)} · {s.people} {s.people === 1 ? "person" : "people"}</span>}>
          {s.name}
        </PageTitle>
        <p className="-mt-3 text-sm text-ink-700">
          <span className="num font-semibold text-ink-900"><Price>{inr(plan.budget.total)}</Price></span>{" "}
          <span data-not-price>for a {inr(s.budget_total)} budget</span>
        </p>
        <p className="mt-1 hidden text-sm print:block"><EstimatedLabel /></p>
        <div className="mt-4 flex flex-wrap items-center gap-2 print:hidden">
          <Link to="/" className="btn-primary btn-sm">Plan your own trip</Link>
          <DownloadPdf />
        </div>
      </div>
      <GettingThere plan={plan} facts={factsFor(plan, city(s.destination), s.people)} />
      <Section title="Day by day">
        <Timeline plan={plan} />
      </Section>
      <Section title="Map" className="print-map">
        <DayMap plan={plan} places={places.data} />
      </Section>
      <Section title="Budget">
        <div className="card grid items-center gap-6 md:grid-cols-2">
          <BudgetDonut budget={plan.budget} />
          <BudgetTable budget={plan.budget} />
        </div>
      </Section>
    </div>
  );
}
