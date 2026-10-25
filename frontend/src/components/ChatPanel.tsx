import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ChatMessage } from "../api/types";
import { ErrorBox, TextWithPrices } from "./ui";

function VersionChip({ tripId, version, current }: { tripId: string; version: number; current: number }) {
  const qc = useQueryClient();
  const undo = useMutation({
    mutationFn: () => api.restore(tripId, version - 1),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["versions", tripId] }),
  });
  return (
    <span className="mt-1 flex flex-wrap items-center gap-2 text-xs">
      <span className="rounded-full bg-accent-100 px-2 py-0.5 font-semibold text-accent-800">Version {version} created</span>
      {version === current ? (
        <button type="button" className="btn-text min-h-0 py-2 text-xs" disabled={undo.isPending} onClick={() => undo.mutate()}>
          {undo.isPending ? "Undoing…" : `Undo (back to version ${version - 1})`}
        </button>
      ) : version < current && <span className="text-ink-500">· a later version replaced it</span>}
      {undo.isError && <span className="text-warn-700">Couldn't undo, please retry.</span>}
    </span>
  );
}

/**
 * Chat assistant on Plan detail (AI-FR-08): history, typing state, and a "Version N created" chip with undo
 * (a restore of the previous version). Docked in the sidebar on wide screens, a bottom sheet on phones.
 */
export default function ChatPanel({ tripId, currentVersion }: { tripId: string; currentVersion: number }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const logRef = useRef<HTMLOListElement>(null);
  const sheetRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const history = useQuery({ queryKey: ["chat", tripId], queryFn: () => api.chat(tripId) });
  const send = useMutation({
    mutationFn: (message: string) => api.sendChat(tripId, message),
    onSuccess: (r) => {
      qc.setQueryData<ChatMessage[]>(["chat", tripId], (old) => [...(old ?? []), r.user, r.assistant]);
      if (r.version) qc.invalidateQueries({ queryKey: ["versions", tripId] });
      setText("");
    },
  });
  const messages = history.data ?? [];
  useEffect(() => {
    logRef.current?.lastElementChild?.scrollIntoView({ block: "nearest" });
  }, [messages.length, send.isPending, open]);
  useEffect(() => {        // phone sheet: focus goes in when it opens and back to the button when it closes
    if (open) document.getElementById("chat-input")?.focus();
    else if (wasOpen.current) triggerRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  function sheetKeys(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === "Escape") { setOpen(false); return; }
    if (e.key !== "Tab" || !sheetRef.current) return;
    const items = [...sheetRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), input, [href]")];
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const m = text.trim();
    if (m && !send.isPending) send.mutate(m);
  }

  return (
    <>
      {!open && (
        <button ref={triggerRef} type="button"
                className="btn-primary fixed bottom-[max(1rem,env(safe-area-inset-bottom))] right-4 z-[1100] shadow-lg lg:hidden"
                aria-expanded={false} aria-controls="chat-panel" onClick={() => setOpen(true)}>
          Ask the assistant
        </button>
      )}
      {open && <div aria-hidden className="fixed inset-0 z-[1090] bg-ink-900/40 lg:hidden" onClick={() => setOpen(false)} />}
      <aside id="chat-panel" ref={sheetRef} aria-labelledby="chat-title" onKeyDown={sheetKeys}
             className={`${open ? "fixed inset-x-0 bottom-0 z-[1100] flex max-h-[80vh] rounded-b-none shadow-2xl" : "hidden"} card flex-col gap-3 lg:static lg:z-auto lg:flex lg:max-h-none lg:rounded-md lg:shadow-none`}>
        <div className="flex items-center justify-between gap-2">
          <h2 id="chat-title" className="text-lg font-semibold">Chat assistant</h2>
          <button type="button" className="btn-text lg:hidden" onClick={() => setOpen(false)}>Close</button>
        </div>
        <div role="log" aria-live="polite" aria-label="Conversation" className="max-h-80 min-h-16 overflow-y-auto text-sm lg:max-h-96">
          <ol ref={logRef} className="flex flex-col gap-2">
            {messages.length === 0 && !send.isPending && (
              <li className="text-ink-500">Ask for a change, like "only 5 hours on day 2", "cheaper hotel" or "why isn't Amber Fort in?"</li>
            )}
            {messages.map((m) => (
              <li key={m.id} className={m.role === "user" ? "ml-6 self-end rounded-md bg-accent-50 px-3 py-2"
                                                           : "mr-6 rounded-md bg-sand-100 px-3 py-2"}>
                <span className="sr-only">{m.role === "user" ? "You:" : "Assistant:"} </span>
                {m.role === "assistant" ? <TextWithPrices text={m.text} /> : m.text}
                {m.role === "assistant" && m.version !== null && (
                  <VersionChip tripId={tripId} version={m.version} current={currentVersion} />
                )}
              </li>
            ))}
            {send.isPending && <li className="mr-6 rounded-md bg-sand-100 px-3 py-2 text-ink-500">Assistant is thinking…</li>}
          </ol>
        </div>
        {history.isError && <ErrorBox error={history.error} />}
        {send.isError && <ErrorBox error={send.error} />}
        <form onSubmit={submit} className="flex gap-2">
          <label htmlFor="chat-input" className="sr-only">Message the assistant</label>
          <input id="chat-input" className="input min-w-0 flex-1" maxLength={1000} value={text} autoComplete="off"
                 placeholder="Ask for a change…" onChange={(e) => setText(e.target.value)} />
          <button type="submit" className="btn-primary" disabled={send.isPending || !text.trim()}>Send</button>
        </form>
        <p className="text-xs text-ink-500">Changes are made by the planner; prices are estimates.</p>
      </aside>
    </>
  );
}
