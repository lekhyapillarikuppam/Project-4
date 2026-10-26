import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { DraftPrefs, Prefs } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import PrefsForm from "../components/PrefsForm";
import { ErrorBox, PageTitle, Skeleton } from "../components/ui";
import { useMeta } from "../lib/meta";
import { useDocumentTitle } from "../lib/title";
import { fieldId, validatePrefs } from "../lib/validate";

export default function Profile() {
  const { user } = useAuth();
  const meta = useMeta();
  const qc = useQueryClient();
  const loc = useLocation();
  const welcome = loc.state as { welcome?: boolean; next?: string } | null;   // just signed up (UI-FR-01)
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const [prefs, setPrefs] = useState<DraftPrefs | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  useDocumentTitle("Profile");
  useEffect(() => { if (profile.data && !prefs) setPrefs(profile.data.prefs); }, [profile.data, prefs]);
  const save = useMutation({
    mutationFn: (p: Prefs) => api.putProfile(p),
    onSuccess: (r) => { qc.setQueryData(["profile"], r); setSaved(true); },
    onError: (e) => { if (e instanceof ApiError) setErrors(e.fields); },
  });
  if (profile.isError) return <ErrorBox error={profile.error} onRetry={() => profile.refetch()} />;
  if (!prefs || !meta.data) return <Skeleton lines={8} />;
  return (
    <div>
      <PageTitle sub={<p>Signed in as <span className="break-all">{user?.email}</span>. Use these on any new trip with “Fill from my profile”.</p>}>
        Profile and preferences
      </PageTitle>
      {welcome?.welcome && (
        <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-accent-600/30 bg-accent-50 p-3 text-sm text-accent-800">
          <p>Set your preferences once; you can reuse them for every trip.</p>
          <Link to={welcome.next ?? "/new"} className="btn-link">Skip for now</Link>
        </div>
      )}
      <form className="space-y-4" noValidate onSubmit={(e) => {
        e.preventDefault();
        setSaved(false);
        const errs = validatePrefs(prefs, meta.data!);
        setErrors(errs);
        const first = Object.keys(errs)[0];
        if (first) document.getElementById(fieldId(first, meta.data!))?.focus();   // as New trip does
        else save.mutate(prefs as Prefs);
      }}>
        <section className="card"><PrefsForm value={prefs} onChange={(p) => { setPrefs(p); setSaved(false); }} meta={meta.data} errors={errors} /></section>
        {save.isError && !(save.error instanceof ApiError && Object.keys(save.error.fields).length) && <ErrorBox error={save.error} />}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save preferences"}</button>
          {saved && <p role="status" className="text-sm text-accent-700">Saved.</p>}
          {saved && welcome?.welcome && <Link to={welcome.next ?? "/new"} className="btn-link">Plan a trip</Link>}
        </div>
      </form>
    </div>
  );
}
