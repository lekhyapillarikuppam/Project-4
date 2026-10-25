import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EstimatedLabel } from "./ui";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-accent-50 text-accent-800" : "text-ink-700 hover:bg-sand-100"}`;

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="border-b border-sand-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3">
          <Link to="/" className="mr-auto text-lg font-bold text-accent-800">Tripwise</Link>
          <nav aria-label="Main" className="flex flex-wrap items-center gap-1">
            {user ? (
              <>
                <NavLink to="/new" className={navClass}>New trip</NavLink>
                <NavLink to="/trips" end className={navClass}>My Trips</NavLink>
                <NavLink to="/profile" className={navClass}>Profile</NavLink>
                <button type="button" className="rounded-md px-3 py-2 text-sm font-medium text-ink-700 hover:bg-sand-100"
                        onClick={() => { logout(); navigate("/"); }}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={navClass}>Log in</NavLink>
                <NavLink to="/signup" className={navClass}>Sign up</NavLink>
              </>
            )}
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-sand-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs text-ink-500">
          <span>Tripwise — budget trips between 15 Indian cities</span>
          <EstimatedLabel />
        </div>
      </footer>
    </div>
  );
}
