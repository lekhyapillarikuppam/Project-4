import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import type { Prefs } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import PrefsForm from "../components/PrefsForm";
import { ErrorBox, PageTitle, Skeleton } from "../components/ui";
import { useMeta } from "../lib/meta";
import { validatePrefs } from "../lib/validate";

export default function Profile() {
  const { user } = useAuth();
  const meta = useMeta();
  const qc = useQueryClient();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
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
      <PageTitle sub={`Signed in as ${user?.email}. These preferences pre-fill every new trip.`}>Profile and preferences</PageTitle>
      <form className="space-y-4" noValidate onSubmit={(e) => {
        e.preventDefault();
        setSaved(false);
        const errs = validatePrefs(prefs, meta.data!);
        setErrors(errs);
        if (!Object.keys(errs).length) save.mutate(prefs);
      }}>
        <section className="card"><PrefsForm value={prefs} onChange={(p) => { setPrefs(p); setSaved(false); }} meta={meta.data} errors={errors} /></section>
        {save.isError && !(save.error instanceof ApiError && Object.keys(save.error.fields).length) && <ErrorBox error={save.error} />}
        <div className="flex items-center gap-3">
          <button type="submit" className="btn-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save preferences"}</button>
          {saved && <p role="status" className="text-sm text-accent-700">Saved.</p>}
        </div>
      </form>
    </div>
  );
}
