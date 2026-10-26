// Minimal typed client for the Tripwise API. The JWT lives in localStorage; a 401 logs the user out.

import type {
  ChatMessage, ChatReply, City, DraftPrefs, Explanations, Meta, ParsedTrip, Places, Prefs, TradeOffs, Trip, TripForm, TripSummary, User, Version, VersionSummary, VariantName,
} from "./types";

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";
const TOKEN_KEY = "tripwise.token";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public fields: Record<string, string> = {},
              public body: Record<string, unknown> = {}) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable: the session lasts until reload */ }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "network", "Can't reach the Tripwise server. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    const message = res.status === 429 && data.error !== "rate_limited" ? "The planner is busy right now. Please retry in a moment."
      : (data.message as string) || "Something went wrong.";
    throw new ApiError(res.status, (data.error as string) || "error", message, (data.fields as Record<string, string>) || {}, data);
  }
  return data as T;
}

export const api = {
  meta: () => request<Meta>("GET", "/meta"),
  cities: () => request<City[]>("GET", "/cities"),
  places: (code: string) => request<Places>("GET", `/cities/${code}/places`),
  signup: (email: string, password: string) => request<{ token: string; user: User }>("POST", "/auth/signup", { email, password }),
  login: (email: string, password: string) => request<{ token: string; user: User }>("POST", "/auth/login", { email, password }),
  me: () => request<User>("GET", "/auth/me"),
  getProfile: () => request<{ prefs: DraftPrefs; saved: boolean }>("GET", "/profile"),
  putProfile: (prefs: Prefs) => request<{ prefs: Prefs; saved: boolean }>("PUT", "/profile", { prefs }),
  createTrip: (form: TripForm) => request<Trip>("POST", "/trips", form),
  listTrips: (when: "upcoming" | "past") => request<TripSummary[]>("GET", `/trips?when=${when}`),
  getTrip: (id: string) => request<Trip>("GET", `/trips/${id}`),
  renameTrip: (id: string, name: string) => request<Trip>("PATCH", `/trips/${id}`, { name }),
  deleteTrip: (id: string) => request<void>("DELETE", `/trips/${id}`),
  duplicateTrip: (id: string) => request<{ request: TripForm }>("POST", `/trips/${id}/duplicate`),
  select: (id: string, variant: VariantName) => request<Version>("POST", `/trips/${id}/select`, { variant }),
  versions: (id: string) => request<VersionSummary[]>("GET", `/trips/${id}/versions`),
  version: (id: string, v: number) => request<Version>("GET", `/trips/${id}/versions/${v}`),
  restore: (id: string, v: number) => request<Version>("POST", `/trips/${id}/versions/${v}/restore`),
  tradeoffs: (id: string, variant: VariantName) => request<TradeOffs>("GET", `/trips/${id}/tradeoffs?variant=${variant}`),
  chat: (id: string) => request<ChatMessage[]>("GET", `/trips/${id}/chat`),
  explanations: (id: string) => request<Explanations>("GET", `/trips/${id}/explanations`),
  sendChat: (id: string, message: string) => request<ChatReply>("POST", `/trips/${id}/chat`, { message }),
  parsePrefs: (text: string) => request<ParsedTrip>("POST", "/ai/parse-prefs", { text }),
};
