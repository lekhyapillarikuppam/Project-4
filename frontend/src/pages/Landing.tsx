import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const STEPS = [
  { title: "Tell us the trip", text: "Where, when, how many people, your budget and what you enjoy." },
  { title: "Compare 2–3 plans", text: "Saver, Balanced and Experience — each checked against the budget, opening hours and travel times." },
  { title: "Refine and keep", text: "Pick a plan, see every day on a map, and save it to My Trips." },
];

export default function Landing() {
  const { user } = useAuth();
  return (
    <div className="space-y-10">
      <section className="rounded-xl bg-accent-50 px-6 py-10 sm:px-10">
        <h1 className="max-w-2xl text-3xl font-bold leading-tight sm:text-4xl">Budget trips that actually work.</h1>
        <p className="mt-3 max-w-2xl text-lg text-ink-700">
          Tripwise plans a complete trip between 15 Indian cities — transport, hotel, a day-by-day itinerary and every rupee —
          and every plan fits your budget, opening hours and travel times.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to={user ? "/new" : "/signup"} className="btn-primary px-6 py-3 text-base">Plan a trip</Link>
          {!user && <Link to="/login" className="btn-secondary px-6 py-3 text-base">Log in</Link>}
        </div>
      </section>
      <section aria-labelledby="how">
        <h2 id="how" className="mb-4 text-xl font-semibold">How it works</h2>
        <ol className="grid gap-4 sm:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="card">
              <p className="text-sm font-semibold text-accent-700">Step {i + 1}</p>
              <h3 className="mt-1 font-semibold">{s.title}</h3>
              <p className="mt-1 text-sm text-ink-700">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>
      <p className="muted">All prices are estimates compiled for planning; Tripwise does not book anything.</p>
    </div>
  );
}
