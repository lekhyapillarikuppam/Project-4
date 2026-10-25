import { useEffect, useRef } from "react";

/** In-page confirmation (FR-046): focus moves into the dialog, Escape or Cancel closes it, Tab stays inside. */
export default function ConfirmDialog({ title, body, confirmLabel, onConfirm, onCancel, busy }: {
  title: string; body: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
      if (e.key === "Tab" && ref.current) {
        const items = ref.current.querySelectorAll<HTMLElement>("button");
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [onCancel]);
  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-ink-900/40 p-4">
      <div ref={ref} role="alertdialog" aria-modal="true" aria-labelledby="dlg-title" aria-describedby="dlg-body"
           className="w-full max-w-sm rounded-lg bg-white p-5 shadow-lg">
        <h2 id="dlg-title" className="text-lg font-semibold">{title}</h2>
        <p id="dlg-body" className="mt-2 text-sm text-ink-700">{body}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button ref={cancelRef} type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="button" className="btn-danger" onClick={onConfirm} disabled={busy}>{busy ? "Deleting…" : confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
