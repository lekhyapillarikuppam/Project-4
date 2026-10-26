import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, FieldError, PageTitle } from "../components/ui";
import { useDocumentTitle } from "../lib/title";

type Mode = "login" | "signup";

/** Log in and Sign up share a route position, so the form is remounted per mode: switching always starts empty (UI-FR-01). */
export default function AuthPage({ mode }: { mode: Mode }) {
  return <AuthForm key={mode} mode={mode} />;
}

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
      {!open && <path d="M4 4l16 16" />}
    </svg>
  );
}

function AuthForm({ mode }: { mode: Mode }) {
  const { user, login, signup } = useAuth();
  const [params] = useSearchParams();
  const next = params.get("next");
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : null;
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useDocumentTitle(mode === "login" ? "Log in" : "Sign up");
  if (user && !busy) return <Navigate to={safeNext ?? "/new"} replace />;

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
      if (mode === "login") {
        await login(email, password);
        navigate(safeNext ?? "/new", { replace: true });
      } else {                                                    // a new account starts on Profile (UI-FR-01)
        await signup(email, password);
        navigate("/profile", { replace: true, state: { welcome: true, next: safeNext ?? undefined } });
      }
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) setFields(err.fields);
      setError(err);
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
          <div className="relative">
            <input id="password" type={show ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"}
                   className="input pr-12" value={password} aria-invalid={!!fields.password}
                   aria-describedby={fields.password ? "password-err" : mode === "signup" ? "password-hint" : undefined}
                   onChange={(e) => setPassword(e.target.value)} />
            <button type="button" aria-label={show ? "Hide password" : "Show password"} aria-pressed={show}
                    aria-controls="password" onClick={() => setShow(!show)}
                    className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md text-ink-700 hover:text-ink-900
                               focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent-700">
              <EyeIcon open={!show} />
            </button>
          </div>
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
