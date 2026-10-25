import type { ReactNode } from "react";
import { ApiError } from "../api/client";
import { useMeta } from "../lib/meta";

export function EstimatedLabel({ className = "" }: { className?: string }) {
  const { data } = useMeta();
  return <span data-estimate className={`text-xs font-medium text-ink-500 ${className}`}>{data?.estimate_label ?? "Estimated prices"}</span>;
}

/** A price with its "Estimated" tag (UI-FR-07). */
export function Price({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span data-estimate className={className}>
      {children} <abbr title="Estimated price" className="text-xs font-normal text-ink-500 no-underline">est.</abbr>
    </span>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-ink-700">
      <span aria-hidden className="h-4 w-4 animate-spin rounded-full border-2 border-accent-700 border-t-transparent" />
      {label}
    </span>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden className="space-y-2">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="h-4 animate-pulse rounded bg-sand-200" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  const busy = e?.status === 429;
  return (
    <div role="alert" className={`rounded-md border p-3 text-sm ${busy ? "border-warn-700/30 bg-warn-50 text-warn-700" : "border-bad-700/30 bg-bad-50 text-bad-700"}`}>
      <p>{e ? e.message : "Something went wrong."}</p>
      {onRetry && <button type="button" className="btn-link mt-2" onClick={onRetry}>{busy ? "Retry" : "Try again"}</button>}
    </div>
  );
}

export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return <p id={id} className="field-error">{message}</p>;
}

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold sm:text-3xl">{children}</h1>
      {sub && <p className="mt-1 text-ink-700">{sub}</p>}
    </div>
  );
}
