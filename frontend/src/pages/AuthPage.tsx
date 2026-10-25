import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, FieldError, PageTitle } from "../components/ui";
import { useDocumentTitle } from "../lib/title";

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { user, login, signup } = useAuth();
  const [params] = useSearchParams();
  const next = params.get("next");
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/new";
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useDocumentTitle(mode === "login" ? "Log in" : "Sign up");
  if (user) return <Navigate to={safeNext} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) errs.email = "Enter a valid email address.";
    if (password.length < 8 || password.length > 128) errs.password = "Password must be 8–128 characters.";
    setFields(errs);
    setError(null);
    if (Object.keys(errs).length) {
      document.getElementById(Object.keys(errs)[0])?.focus();       // say what is wrong at once (WCAG 3.3.1)
      return;
    }
    setBusy(true);
    try {
      await (mode === "login" ? login(email, password) : signup(email, password));
      navigate(safeNext, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setFields(err.fields);
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const other = mode === "login" ? "signup" : "login";
  const qs = next ? `?next=${encodeURIComponent(next)}` : "";
  return (
    <div className="mx-auto max-w-md">
      <PageTitle sub={mode === "login" ? "Welcome back." : "Save trips, plans and chats to your account."}>
        {mode === "login" ? "Log in" : "Create your account"}
      </PageTitle>
      <form onSubmit={submit} noValidate className="card space-y-4">
        <div>
          <label htmlFor="email" className="label">Email</label>
          <input id="email" type="email" autoComplete="email" className="input" value={email}
                 aria-invalid={!!fields.email} aria-describedby={fields.email ? "email-err" : undefined}
                 onChange={(e) => setEmail(e.target.value)} />
          <FieldError id="email-err" message={fields.email} />
        </div>
        <div>
          <label htmlFor="password" className="label">Password</label>
          <input id="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"}
                 className="input" value={password} aria-invalid={!!fields.password}
                 aria-describedby={fields.password ? "password-err" : "password-hint"}
                 onChange={(e) => setPassword(e.target.value)} />
          {mode === "signup" && !fields.password && <p id="password-hint" className="muted mt-1">8–128 characters.</p>}
          <FieldError id="password-err" message={fields.password} />
        </div>
        {error !== null && !(error instanceof ApiError && Object.keys(error.fields).length) && <ErrorBox error={error} />}
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
        </button>
        <p className="text-center text-sm text-ink-700">
          {mode === "login" ? "New to Tripwise? " : "Already have an account? "}
          <Link to={`/${other}${qs}`} className="btn-link">{mode === "login" ? "Sign up" : "Log in"}</Link>
        </p>
      </form>
    </div>
  );
}
