import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Journey, Plan } from "../api/types";
import Explanation from "../components/Explanation";
import { BudgetDonut, BudgetTable } from "../components/Budget";
import ChatPanel from "../components/ChatPanel";
import DayMap from "../components/DayMap";
import { NearMisses, TradeOffsPanel, VersionList } from "../components/PlanPanels";
import Timeline from "../components/Timeline";
import { ErrorBox, PageTitle, Price, Skeleton } from "../components/ui";
import { duration, inr, MODE_LABEL, TIER_LABEL, VARIANT_LABEL } from "../lib/format";
import { CheckList } from "../components/VariantCard";
import { useCityName } from "../lib/meta";
import { useDocumentTitle } from "../lib/title";
import { tripSubtitle } from "./Compare";

function JourneyCard({ title, j, out }: { title: string; j: Journey; out: boolean }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-ink-700">{title}</h3>
      <p className="mt-1 text-lg font-semibold">{MODE_LABEL[j.mode]} <span className="text-ink-500">{j.class}</span></p>
      <p className="text-sm">
        {out ? `Leaves ${j.depart}${j.overnight ? " (overnight)" : ""}, at the city centre ${j.arrive_centre}`
             : `Leave the centre ${j.leave_centre}, arrive ${j.arrive_origin}${j.overnight ? " (overnight)" : ""}`}
      </p>
      <p className="text-sm text-ink-700">Door to door {duration(j.minutes)} · <Price>{inr(j.cost)}</Price></p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={title.replace(/\W+/g, "-")} className="space-y-3">
      <h2 id={title.replace(/\W+/g, "-")} className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default function PlanDetail() {
  const { id = "" } = useParams();
  const trip = useQuery({ queryKey: ["trip", id], queryFn: () => api.getTrip(id) });
  const versions = useQuery({ queryKey: ["versions", id], queryFn: () => api.versions(id) });
  const latestNo = versions.data?.length ? versions.data[versions.data.length - 1].version : null;
  const version = useQuery({ queryKey: ["version", id, latestNo], queryFn: () => api.version(id, latestNo!), enabled: latestNo !== null });
  const dest = trip.data?.request.destination;
  const places = useQuery({ queryKey: ["places", dest], queryFn: () => api.places(dest!), enabled: !!dest, staleTime: Infinity });
  const city = useCityName();
  useDocumentTitle(trip.data ? `${trip.data.name} plan` : "Your plan");

  const err = trip.error || versions.error || version.error;
  if (err) return <ErrorBox error={err} />;
  if (!trip.data || !versions.data) return <Skeleton lines={8} />;
  if (versions.data.length === 0) return <Navigate to={`/trips/${id}`} replace />;
  if (!version.data) return <Skeleton lines={8} />;
  const plan: Plan = version.data.plan;
  const names = (aid: string) => places.data?.attractions.find((a) => a.id === aid)?.name ?? aid;

  return (
    <div className="grid gap-6 pb-24 lg:grid-cols-[1fr,20rem] lg:pb-0">
      <div className="min-w-0 space-y-8">
        <div>
          <PageTitle sub={<>
            <span className="chip bg-accent-50 font-medium text-accent-800">{VARIANT_LABEL[plan.variant ?? "balanced"]} plan, version {version.data.version}</span>
            {tripSubtitle(trip.data, city)}
          </>}>
            {trip.data.name}
          </PageTitle>
          <div className="-mt-3 mb-1 flex flex-wrap items-center gap-x-4 gap-y-1">
            <p className="text-sm text-ink-700">
              <span className="num font-semibold text-ink-900"><Price>{inr(plan.budget.total)}</Price></span>{" "}
              <span data-not-price>of your {inr(plan.budget.budget_total)} budget</span>
            </p>
            <CheckList />
          </div>
          <Link to={`/trips/${id}`} className="btn-text">← Compare plans</Link>
        </div>
        {plan.variant && trip.data.result.status === "ok"
          && trip.data.result.variants.some((v) => v.variant === plan.variant && v.request_hash === plan.request_hash)
          && <Explanation tripId={id} variant={plan.variant} />}
        <Section title="Getting there and staying">
          <div className="grid gap-3 sm:grid-cols-3">
            <JourneyCard title="Outbound" j={plan.transport.outbound} out />
            <JourneyCard title="Return" j={plan.transport.return} out={false} />
            <div className="card">
              <h3 className="text-sm font-semibold text-ink-700">Hotel</h3>
              <p className="mt-1 line-clamp-2 text-base font-semibold leading-snug" title={plan.hotel.name}>{plan.hotel.name}</p>
              <p className="text-sm">{TIER_LABEL[plan.hotel.tier]} · {plan.hotel.nights} night{plan.hotel.nights === 1 ? "" : "s"} · {plan.hotel.rooms} room{plan.hotel.rooms === 1 ? "" : "s"}</p>
              <p className="num text-sm text-ink-700"><Price>{inr(plan.hotel.cost)}</Price> · <Price>{inr(plan.hotel.price_per_room_night)}</Price> per room per night</p>
            </div>
          </div>
        </Section>
        <Section title="Day by day">
          <Timeline plan={plan} />
        </Section>
        <Section title="Map">
          <DayMap plan={plan} places={places.data} />
        </Section>
        <Section title="Nearly made it">
          <NearMisses items={plan.near_misses} />
        </Section>
        <Section title="Budget">
          <div className="card grid items-center gap-6 md:grid-cols-2">
            <BudgetDonut budget={plan.budget} />
            <BudgetTable budget={plan.budget} />
          </div>
        </Section>
        <Section title="Budget trade-offs">
          <TradeOffsPanel tripId={id} variant={plan.variant ?? "balanced"} names={names} />
        </Section>
      </div>
      <div className="space-y-6 lg:sticky lg:top-4 lg:self-start">
        <ChatPanel tripId={id} currentVersion={version.data.version} />
        <section aria-labelledby="versions" className="card">
          <h2 id="versions" className="mb-2 text-lg font-semibold">Version history</h2>
          <VersionList tripId={id} versions={versions.data} current={version.data.version} />
        </section>
      </div>
    </div>
  );
}
