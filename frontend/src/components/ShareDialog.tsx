import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { ErrorBox } from "./ui";

/** Share dialog (UI-FR-11): creates or shows the read-only link; Copy link, Stop sharing. Focus stays inside; Escape closes. */
export default function ShareDialog({ tripId, onClose }: { tripId: string; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "copied" | "manual" | "stopped">("loading");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let live = true;
    api.share(tripId).then((r) => { if (live) { setUrl(`${window.location.origin}${r.url_path}`); setState("ready"); } })
      .catch((e) => { if (live) setError(e); });
    return () => { live = false; };
  }, [tripId]);

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("button:not([disabled])")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && ref.current) {
        const items = ref.current.querySelectorAll<HTMLElement>("button:not([disabled]), input");
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [onClose]);

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setState("copied");
    } catch {                                             // no clipboard access: select the link for a manual copy
      inputRef.current?.focus();
      inputRef.current?.select();
      setState("manual");
    }
  }

  async function stop() {
    try {
      await api.unshare(tripId);
      setUrl(null);
      setState("stopped");
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-ink-900/40 p-4 print:hidden">
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby="share-title" aria-describedby="share-body"
           className="w-full max-w-md rounded-lg bg-white p-5 shadow-lg">
        <h2 id="share-title" className="text-lg font-semibold">Share this plan</h2>
        <p id="share-body" className="mt-2 text-sm text-ink-700">
          Anyone with the link can see this plan, read-only: the days, transport, hotel and budget. Not your chat or account.
        </p>
        {error !== null && <div className="mt-3"><ErrorBox error={error} /></div>}
        {state === "stopped" ? (
          <p role="status" className="mt-4 text-sm text-ink-700">Sharing is off. The old link no longer works.</p>
        ) : (
          <div className="mt-4">
            <label htmlFor="share-url" className="label">Link</label>
            <input id="share-url" ref={inputRef} readOnly className="input" value={url ?? "Creating link…"}
                   onFocus={(e) => e.currentTarget.select()} />
            <p role="status" className="mt-1 min-h-5 text-sm text-accent-700">
              {state === "copied" ? "Link copied." : state === "manual" ? "Copy the selected link (Ctrl+C or long-press)." : ""}
            </p>
          </div>
        )}
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          {state !== "stopped" && (
            <>
              <button type="button" className="btn-secondary" onClick={stop} disabled={!url}>Stop sharing</button>
              <button type="button" className="btn-primary" onClick={copy} disabled={!url}>Copy link</button>
            </>
          )}
          <button type="button" className="btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
