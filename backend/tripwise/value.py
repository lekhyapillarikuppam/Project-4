"""Trip value (002 Spec §6, addendum A1; ENG-FR-03)."""

from __future__ import annotations

from tripwise.config import Config
from tripwise.data import Attraction
from tripwise.models import Prefs


def match(a: Attraction, prefs: Prefs, cfg: Config) -> float:
    sec = cfg.value["secondary_tag"]
    return max((prefs.interests.get(t, 0) / 5) * (1.0 if i == 0 else sec) for i, t in enumerate(a.tags))


def crowd(a: Attraction, prefs: Prefs, cfg: Config) -> float:
    if not prefs.avoid_crowds:
        return 1.0
    return cfg.value["crowd"].get(a.crowd, 1.0)


def activity(a: Attraction, prefs: Prefs, cfg: Config) -> float:
    """v(a) = 100 × (rating ÷ 5) × (base + (1 − base) × match) × crowd."""
    base = cfg.value["base_share"]
    return 100 * (a.rating / 5) * (base + (1 - base) * match(a, prefs, cfg)) * crowd(a, prefs, cfg)


def hotel_term(tier: str, cfg: Config) -> float:
    v = cfg.variants
    return v["kappa_h"] * v["tier_value"][tier]


def plan(sum_v: float, comfort_out: float, comfort_ret: float, preferred_journeys: int,
         travel_minutes: float, tier: str, cfg: Config) -> float:
    """V = Σv + κ_t × mean journey comfort + β × preferred journeys − μ × local travel minutes + κ_h × tier value."""
    c = cfg.value
    return (sum_v + c["kappa_t"] * (comfort_out + comfort_ret) / 2 + c["beta_pref_mode"] * preferred_journeys
            - c["mu_travel_per_min"] * travel_minutes + hotel_term(tier, cfg))
