// Types for the Tripwise API (backend/api, Feature 004; plan schema from backend/tripwise/models.py).

export type Tag =
  | "nature" | "adventure" | "food" | "history" | "culture" | "spiritual" | "shopping" | "relaxation" | "nightlife";
export type Pace = "relaxed" | "balanced" | "packed";
export type Comfort = "budget" | "mid" | "premium";
export type Mode = "train" | "bus" | "flight";
export type ModePref = "preferred" | "neutral" | "avoid";
export type VariantName = "experience" | "balanced" | "saver";

export interface Prefs {
  daily_hours_out: number;
  interests: Record<Tag, number>;
  pace: Pace;
  comfort: Comfort;
  modes: Record<Mode, ModePref>;
  avoid_crowds: boolean;
}

export interface TripRequest {
  origin: string;
  destination: string;
  start_date: string;
  end_date: string;
  people: number;
  budget_total: number;
  prefs: Prefs;
  locks: string[];
  excludes: string[];
}

export interface TripForm extends Omit<TripRequest, "budget_total"> {
  budget_total?: number;
  budget_per_person?: number;
  name?: string;
}

export interface Leg { from: string | null; to: string | null; minutes: number; km: number; mode: string; cost: number }
export interface Stop {
  attraction_id: string; name: string; arrive: string; start: string; end: string; entry_cost: number; leg_from_prev: Leg;
}
export interface Day {
  day: number; date: string; weekday: number; window: [string, string] | null; lunch: [string, string] | null;
  stops: Stop[]; return_leg: Leg | null;
}
export interface Journey {
  mode: Mode; class: string; minutes: number; overnight: boolean; cost: number;
  depart?: string; arrive_centre?: string; leave_centre?: string; arrive_origin?: string;
}
export interface Budget {
  outbound: number; return: number; stay: number; food: number; entry_fees: number; local_travel: number;
  total: number; usable_budget: number; contingency: number; budget_total: number; estimate_label: string;
}
export interface NearMiss { attraction_id: string; name: string; reason: "budget" | "time" | "closed" }
export interface Plan {
  status: "ok";
  variant: VariantName | null;
  dataset_version: string;
  request_hash: string;
  value: number;
  transport: { outbound: Journey; return: Journey };
  hotel: { hotel_id: string; name: string; tier: Comfort; nights: number; rooms: number; price_per_room_night: number; cost: number };
  days: Day[];
  budget: Budget;
  near_misses: NearMiss[];
  solver: { hotel_candidates: number; feedback_iters: number; repairs: number; solve_ms: number };
}
export interface Infeasible {
  status: "infeasible";
  reason: "budget" | "no_route" | "lock_impossible" | "lock_over_budget";
  min_budget_total: number | null;
  message: string;
  attraction_id?: string | null;
}
export interface VariantsResult { status: "ok"; variants: Plan[]; dropped: { name: VariantName; reason: string }[] }
export type TripResult = VariantsResult | Infeasible;

export interface Trip {
  id: string; name: string; request: TripRequest; result: TripResult; selected_variant: VariantName | null;
  start_date: string; created_at: string; updated_at: string;
}
export interface TripSummary {
  id: string; name: string; origin: string; destination: string; start_date: string; end_date: string;
  people: number; budget_total: number; status: "ok" | "infeasible"; selected_variant: VariantName | null; updated_at: string;
}
export interface VersionSummary {
  version: number; source: "select" | "replan" | "chat" | "restore"; note: string | null; changes: unknown;
  variant: VariantName | null; total: number; value: number; created_at: string;
}
export interface Version extends VersionSummary { plan: Plan; request: TripRequest }

export interface TradeOffRow {
  factor: number; budget_total: number; status: string; delta_cost: number | null; delta_value: number | null;
  added: string[]; dropped: string[]; hotel_change: [string, string] | null; transport_change: [string, string] | null;
}
export interface TradeOffs {
  status: "ok"; variant: VariantName; budget_total: number; cost: number; value: number; rows: TradeOffRow[]; cached?: boolean;
}

export interface City { code: string; name: string; lat: number; lon: number }
export interface Places {
  city: string;
  attractions: { id: string; name: string; lat: number; lon: number; tags: string[] }[];
  hotels: { id: string; name: string; tier: Comfort; lat: number; lon: number }[];
}
export interface Meta {
  dataset_version: string; estimate_label: string; interests: Tag[]; paces: Pace[]; comforts: Comfort[];
  modes: Mode[]; mode_prefs: ModePref[];
  limits: {
    trip_days: [number, number]; people: [number, number]; hours_out: [number, number]; interest_weight: [number, number];
    budget_min_per_person: number; budget_max_total: number; max_days_ahead: number;
  };
}
export interface User { id: string; email: string }
export interface ParsedTrip {
  prefs: Prefs; origin?: string; destination?: string; start_date?: string; end_date?: string; people?: number;
  budget_total?: number; budget_per_person?: number;
}
export type Explanations =
  | { status: "ok"; texts: Partial<Record<VariantName, string>>; source: Partial<Record<VariantName, "llm" | "llm_retry" | "template">>; cached: boolean }
  | { status: "unavailable"; notice: string };
export interface ChatMessage {
  id: number; role: "user" | "assistant"; text: string; actions: unknown; version: number | null; created_at: string;
}
export interface ChatReply { user: ChatMessage; assistant: ChatMessage; version: Version | null }
