import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { ParsedTrip } from "../api/types";

/** "Describe your trip" box (AI-FR-01, AI-FR-08): fills the form; the user checks the values before planning. */
export default function DescribeTrip({ onParsed }: { onParsed: (p: ParsedTrip) => void }) {
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  async function go() {
    if (!text.trim()) return;
    setState("busy");
    try {
      const p = await api.parsePrefs(text.trim());
      onParsed(p);
      setState("done");
      setMessage("Filled in from your description — check the values below before planning.");
    } catch (e) {
      setState("error");
      setMessage(e instanceof ApiError ? e.message : "Couldn't understand that, please use the sliders.");
    }
  }
  return (
    <section className="card space-y-2" aria-labelledby="describe">
      <h2 id="describe" className="text-lg font-semibold">Describe your trip <span className="text-sm font-normal text-ink-500">(optional)</span></h2>
      <label htmlFor="describe-text" className="label">In your own words</label>
      <textarea id="describe-text" className="input min-h-24" maxLength={2000} value={text}
                placeholder="e.g. Two of us from Bengaluru to Goa for 4 days, about ₹40,000. We love beaches and seafood, no long bus rides."
                onChange={(e) => setText(e.target.value)} />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="btn-secondary" onClick={go} disabled={state === "busy" || !text.trim()}>
          {state === "busy" ? "Reading…" : "Fill in the form"}
        </button>
        {message && <p role="status" className={`text-sm ${state === "error" ? "text-warn-700" : "text-accent-700"}`}>{message}</p>}
      </div>
    </section>
  );
}
