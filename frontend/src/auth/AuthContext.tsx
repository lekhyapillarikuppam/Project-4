import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, getToken, setToken, setUnauthorizedHandler } from "../api/client";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    qc.clear();
  }, [qc]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!getToken()) { setReady(true); return; }
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, [logout]);

  const value = useMemo<AuthState>(() => ({
    user, ready, logout,
    login: async (email, password) => { const r = await api.login(email, password); setToken(r.token); setUser(r.user); },
    signup: async (email, password) => { const r = await api.signup(email, password); setToken(r.token); setUser(r.user); },
  }), [user, ready, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
