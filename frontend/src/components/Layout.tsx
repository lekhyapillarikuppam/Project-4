import { Suspense } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EstimatedLabel, Skeleton } from "./ui";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-11 items-center rounded-md px-3 text-sm font-medium ${isActive ? "bg-accent-50 text-accent-800" : "text-ink-700 hover:bg-sand-100"}`;
// Signed out (UI-FR-01): outlined in the accent; accent-800 text is AA on accent-50 and on the darker accent-100 hover.
const authClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex min-h-11 items-center rounded-md border border-accent-600 px-4 text-sm font-semibold text-accent-800 hover:bg-accent-100 ${isActive ? "bg-accent-100" : "bg-accent-50"}`;

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="border-b border-sand-200 bg-white print:hidden">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3">
          <Link to="/" className="mr-auto font-display text-xl font-bold tracking-tight text-accent-800">Tripwise</Link>
          <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
            {user ? (
              <>
                <NavLink to="/new" className={navClass}>New trip</NavLink>
                <NavLink to="/trips" end className={navClass}>My Trips</NavLink>
                <NavLink to="/profile" className={navClass}>Profile</NavLink>
                <button type="button" className="inline-flex min-h-11 items-center rounded-md px-3 text-sm font-medium text-ink-700 hover:bg-sand-100"
                        onClick={() => { logout(); navigate("/"); }}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={authClass}>Log in</NavLink>
                <NavLink to="/signup" className={authClass}>Sign up</NavLink>
              </>
            )}
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Suspense fallback={<Skeleton lines={6} />}>
          <Outlet />
        </Suspense>
      </main>
      <footer className="border-t border-sand-200 bg-white print:hidden">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs text-ink-500">
          <span>Tripwise — budget trips between 15 Indian cities</span>
          <EstimatedLabel />
        </div>
      </footer>
    </div>
  );
}
