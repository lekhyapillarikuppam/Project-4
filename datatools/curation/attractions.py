"""Build data/curated/attractions/<CITY>.csv (T15).

    python -m datatools.curation.attractions <CITY> [<CITY> ...]

Inputs:
- data/raw/attractions/<CITY>_draft.csv      ranked candidates (datatools.draft)
- data/raw/attractions/<CITY>_selection.csv  the hand selection: candidate, name, place_type, tags,
                                             outdoor, fixed_slot, official, note, wiki_title (the English
                                             Wikipedia article when the seed record has no Wikidata link)
- data/raw/attractions/asi/<CODE>.json       ASI e-ticket records (official hours and Indian fee)
- data/raw/attractions/official_hours.csv    hours/fees read from other official sites (a fee the user read
                                             from an official booking page: "read by user from <url>, <date>")
- data/raw/attractions/fee_secondary.csv     secondary-source fees: city_id, place, fee, url, fetched_on, page_date (the
                                             published, updated or reviewed date the page shows; empty if none), extract
- data/raw/attractions/fee_revisions.csv     known fee revisions: city_id, place, effective_on, fee, url, published_on,
                                             fetched_on, extract (the revision's source is also a dated fee source)
- data/raw/attractions/hours_secondary.csv   secondary-source hours, used when the official page gives days but no hours
- data/raw/attractions/activities.csv        hand-curated adventure activities (selection candidate "activity:<place>"):
                                             location, hours and price read from an operator or state tourism page
- data/raw/wiki/<CITY>/pageviews.json        12-month pageviews

Rules (001 Spec §5.5): rating from pageviews log-scaled within the city, OpenTripMap rate 1/2/3 ->
2/3/4 as fallback; crowd_level = rating terciles; hours and fee from ASI or the official site, else
place-type defaults (hours_approx); with no official fee, the median of >= 2 independent secondary
sources (fee_approx), else fee 0 for free-by-nature types; visit_minutes = place-type default
(visit_approx). A monument, fort, museum or activity with no official or secondary fee stays TODO.
A hand-curated activity takes its place, hours and price from its page (fee_approx unless the page is
official) and is rated 2.0.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime
from urllib.parse import urlparse

from datatools import draft as drafting
from datatools import rules
from datatools.curation.common import CURATED, RAW, latest, read_csv, write_csv

A = RAW / "attractions"
WIKI_FETCHED = "2026-10-23"
HEADER = ["attraction_id", "city_id", "name", "lat", "lon", "visit_minutes", "visit_approx", "open_time", "close_time",
          "closed_weekdays", "hours_approx", "entry_fee", "fee_approx", "tags", "rating", "outdoor", "crowd_level", "fixed_slot",
          "source", "checked_on"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def asi_record(code: str) -> dict:
    d = json.loads((A / "asi" / f"{code}.json").read_text(encoding="utf-8"))
    m = d["response"]["data"]
    def hhmm(s: str) -> str:
        return datetime.strptime(s.strip().upper(), "%I:%M:%S %p").strftime("%H:%M")
    av = m.get("availability") or {}
    slots = av.get("timeSlots") or []
    week = av.get("week") or {}
    return {
        "open": min(hhmm(s["startTime"]) for s in slots), "close": max(hhmm(s["endTime"]) for s in slots),
        "closed": [i for i, day in enumerate(WEEKDAYS) if week.get(day) is False],
        "fee": next(a["total"] for a in m["configuration"]["amounts"] if a["type"] == "Indian"),
        "url": d["url"], "fetched_on": d["fetched_on"], "name": m["name"],
    }


def ratings(rows: list[dict]) -> dict[str, tuple[float, str]]:
    """candidate -> (rating, basis)."""
    pv = {r["candidate"]: int(r["pageviews"]) for r in rows if r["pageviews"] and int(r["pageviews"]) > 0}
    out = {}
    if pv:
        lo, hi = math.log(min(pv.values())), math.log(max(pv.values()))
        for c, v in pv.items():
            val = rules.RATING_SAME_PAGEVIEWS if hi == lo else 1 + 4 * (math.log(v) - lo) / (hi - lo)
            out[c] = (round(val, 1), f"{v} pageviews {WIKI_PERIOD}")
    for r in rows:
        if r["candidate"] not in out and r["otm_rate"]:
            out[r["candidate"]] = (rules.OTM_RATE_TO_RATING[int(r["otm_rate"])], f"OpenTripMap rate {r['otm_rate']} (no Wikipedia article)")
        elif r["candidate"] not in out and not r.get("wiki_title"):
            out[r["candidate"]] = (rules.NO_POPULARITY_RATING, "no Wikipedia article or OpenTripMap rate, lowest fallback (001 Spec 5.5)")
    return out


WIKI_PERIOD = "Oct 2025-Sep 2026"
ACTIVITY_PREFIX = "activity:"
MIN_SECONDARY_FEES = 2


def secondary_fee(rows: list[dict], revision: dict | None = None) -> tuple[int, str, str] | None:
    """(median fee, source text, latest fetch date) from >= 2 sources on different sites, else None.

    With a known fee revision only sources whose page_date is on or after its effective date count;
    an undated source does not count (001 Spec 5.5)."""
    if revision:   # the revision's own source is a dated source for the fee it quotes
        rows = [r for r in rows if r["page_date"] and r["page_date"] >= revision["effective_on"]] + [
            {"url": revision["url"], "fee": revision["fee"], "fetched_on": revision["fetched_on"],
             "page_date": revision["published_on"]}]
    by_site = {urlparse(r["url"]).netloc.removeprefix("www."): r for r in rows}
    if len(by_site) < MIN_SECONDARY_FEES:
        return None
    fees = [int(r["fee"]) for r in by_site.values()]
    fee = int(math.floor(statistics.median(fees) + 0.5))
    text = "; ".join(f"{r['url']} Rs {r['fee']}" + (f" dated {r['page_date']}" if revision else "") for r in by_site.values())
    rev = (f", dated on or after the fee revision of {revision['effective_on']} ({revision['url']}; data/raw/attractions/fee_revisions.csv)"
           if revision else "")
    dates = [r["fetched_on"] for r in by_site.values()] + ([revision["fetched_on"]] if revision else [])
    return fee, f"fee: median of {len(fees)} secondary sources Rs {fee}{rev} ({text}; data/raw/attractions/fee_secondary.csv)", latest(*dates)


def check_selection(city: str, sel: list[dict]) -> None:
    """Stop on a row whose columns shifted (an unquoted comma in a note) or a wiki_title with stray whitespace."""
    for line, s in enumerate(sel, start=2):
        if None in s or None in s.values():
            raise SystemExit(f"{city}_selection.csv:{line}: column count differs from the header (quote cells that contain commas)")
        t = s.get("wiki_title", "")
        if t != t.strip():
            raise SystemExit(f"{city}_selection.csv:{line}:wiki_title: leading or trailing whitespace {t!r}")


def secondary_hours(rows: list[dict]) -> tuple[str, str, str, str] | None:
    """(open, close, source text, latest fetch date): median opening and closing times of >= 2 sources on
    different sites, for an official page that gives the days but no hours (001 Spec 5.5). A closing time at
    or before the opening time is past midnight; the median close is capped at the last minute of the day."""
    by_site = {urlparse(r["url"]).netloc.removeprefix("www."): r for r in rows}
    def mins(t: str) -> int:
        h, m = t.split(":")
        return int(h) * 60 + int(m)
    opens = [mins(r["open_time"]) for r in by_site.values() if r["open_time"]]
    closes = [mins(r["close_time"]) for r in by_site.values() if r["close_time"]]
    if len(opens) < MIN_SECONDARY_HOURS or len(closes) < MIN_SECONDARY_HOURS:
        return None
    o = int(math.floor(statistics.median(opens) + 0.5))
    c = int(math.floor(statistics.median([x + 1440 if x <= o else x for x in closes]) + 0.5))
    c = min(c, LAST_MINUTE)
    text = "; ".join(f"{r['url']} {r['open_time'] or '-'}-{r['close_time'] or '-'}" for r in by_site.values())
    return (f"{o // 60:02d}:{o % 60:02d}", f"{c // 60:02d}:{c % 60:02d}",
            f"hours: median of secondary sources ({text}; data/raw/attractions/hours_secondary.csv)"
            + (", closing capped at 23:59" if c == LAST_MINUTE else ""),
            latest(*(r["fetched_on"] for r in by_site.values())))


LAST_MINUTE = 23 * 60 + 59
MIN_SECONDARY_HOURS = 2


def build(city: str) -> list[list]:
    draft = {r["candidate"]: r for r in read_csv(A / f"{city}_draft.csv")}
    seed = json.loads((RAW / "seed" / f"{city}.json").read_text(encoding="utf-8"))
    seed_date = seed["fetched_on"]
    # Overpass blocks refetched later (seed --extras-only) carry their own date.
    block_date = {it["osm"]: b["fetched_on"] for b in seed["overpass"].values() if b.get("fetched_on") for it in b["items"]}
    activities = {r["place"]: r for r in read_csv(A / "activities.csv") if r["city_id"] == city}
    for name, a in activities.items():
        draft[ACTIVITY_PREFIX + name] = {"candidate": ACTIVITY_PREFIX + name, "name": name, "lat": a["lat"], "lon": a["lon"],
                                         "pageviews": "", "otm_rate": ""}
    official = {(r["city_id"], r["place"]): r for r in read_csv(A / "official_hours.csv")}
    secondary: dict[str, list[dict]] = {}
    for r in read_csv(A / "fee_secondary.csv"):
        if r["city_id"] == city:
            secondary.setdefault(r["place"], []).append(r)
    revisions = {r["place"]: r for r in read_csv(A / "fee_revisions.csv") if r["city_id"] == city}
    sec_hours: dict[str, list[dict]] = {}
    for r in read_csv(A / "hours_secondary.csv"):
        if r["city_id"] == city:
            sec_hours.setdefault(r["place"], []).append(r)
    sel = read_csv(A / f"{city}_selection.csv")
    check_selection(city, sel)
    chosen =[{**draft[s["candidate"]], **{k: v for k, v in s.items() if v != ""}} for s in sel]
    for s, c in zip(sel, chosen):   # a hand-set article (e.g. the draft had a redirect title) needs its own pageviews
        if s.get("wiki_title") and s["wiki_title"] != draft[s["candidate"]].get("wiki_title"):
            c["pageviews"] = ""
    # Pageviews were fetched for the top candidates only (datatools.draft); fetch any selected title still missing.
    missing = [c["wiki_title"] for c in chosen if c.get("wiki_title") and not c.get("pageviews")]
    if missing:
        pv = drafting.pageviews(missing, RAW / "wiki" / city / "pageviews.json")
        for c in chosen:
            if c.get("wiki_title") and not c.get("pageviews") and pv.get(c["wiki_title"]) is not None:
                c["pageviews"] = str(pv[c["wiki_title"]])
    pv_dates = drafting.load_cache(drafting.fetched_path(RAW / "wiki" / city / "pageviews.json"))
    unknown = [c["wiki_title"] for c in chosen if c.get("wiki_title") and not c.get("pageviews")]
    if unknown:   # a shifted column or a typo lands here: Wikipedia has no such article
        raise SystemExit(f"{city}_selection.csv: wiki_title not found on English Wikipedia: {unknown}")
    rate = ratings(chosen)
    order = sorted((c["candidate"] for c in chosen if c["candidate"] in rate), key=lambda c: rate[c][0])
    n = len(order)
    crowd = {c: ("low" if i < n / 3 else "medium" if i < 2 * n / 3 else "high") for i, c in enumerate(order)}

    rows = []
    for i, c in enumerate(chosen, start=1):
        ptype = rules.PLACE_TYPE_ALIASES.get(c["place_type"], c["place_type"])
        d = rules.PLACE_TYPES[ptype]
        dates, src, todo = [block_date.get(c["candidate"], seed_date)], [], []
        open_t, close_t, closed, fee, hours_approx, fee_approx = d["open"], d["close"], d["closed"], None, True, False
        sh_src = None
        act = activities.get(c["candidate"].removeprefix(ACTIVITY_PREFIX)) if c["candidate"].startswith(ACTIVITY_PREFIX) else None
        if act:
            dates = [act["fetched_on"]]
            src.append(f"place, hours and price: {'state tourism' if act['official'] == 'true' else 'operator'} page {act['url']} "
                       f"({act['extract']}); location: {act['location']} (data/raw/attractions/activities.csv)")
            if act["open_time"]:
                open_t, close_t, hours_approx = act["open_time"], act["close_time"], False
                closed = [int(x) for x in act["closed_weekdays"].split(";") if x]
            if act["entry_fee"]:
                fee, fee_approx = int(act["entry_fee"]), act["official"] != "true"
        else:
            cand_src = f"https://opentripmap.com/en/card/{c['candidate']}" if c["candidate"][:1] in "NWRQ" and "/" not in c["candidate"] \
                else f"https://www.openstreetmap.org/{c['candidate']}"
            src.append(f"place: {cand_src} (data/raw/seed/{city}.json)")

        off = c.get("official", "")
        if off.startswith("asi:"):
            a = asi_record(off[4:])
            open_t, close_t, closed, fee, hours_approx = a["open"], a["close"], a["closed"], a["fee"], False
            src.append(f"hours and fee: ASI e-ticket {a['url']} ('{a['name']}', ticket slots {a['open']}-{a['close']}, Indian Rs {a['fee']})")
            dates.append(a["fetched_on"])
        elif off.startswith("official:"):
            o = official[(city, off[9:])]
            dates.append(o["fetched_on"])
            if o["open_time"]:
                open_t, close_t, hours_approx = o["open_time"], o["close_time"], False
                closed = [int(x) for x in o["closed_weekdays"].split(";") if x] if o["closed_weekdays"] else []
            elif o["closed_weekdays"]:
                closed = [int(x) for x in o["closed_weekdays"].split(";")]
                if sh := secondary_hours(sec_hours.get(c["name"], [])):
                    open_t, close_t, sh_text, sh_date = sh
                    sh_src = sh_text
                    dates.append(sh_date)
            if o["entry_fee"]:
                fee = int(o["entry_fee"])
            src.append(f"official: {o['url']} ({o['extract']})")
        if sh_src:
            src.append(sh_src)
        elif hours_approx:
            src.append(f"hours: {ptype} default (001 Spec 5.5)")
        if fee is None and (sec := secondary_fee(secondary.get(c["name"], []), revisions.get(c["name"]))):
            fee, text, sec_date = sec
            fee_approx = True
            src.append(text)
            dates.append(sec_date)
        if fee is None:
            if ptype in rules.FREE_BY_DEFAULT:
                fee = 0
                src.append(f"fee: 0, {ptype} default (001 Spec 5.5)")
            else:
                todo.append("entry fee (no ASI, official or secondary source found)")

        r, basis = rate.get(c["candidate"], (None, None))
        if r is None:
            todo.append("rating")
        else:
            src.append(f"rating: {basis}" + (f" https://en.wikipedia.org/wiki/{c['wiki_title'].replace(' ', '_')}" if c.get("wiki_title") else ""))
            if c.get("wiki_title"):   # pageviews cached before fetch dates were kept were fetched while drafting
                dates.append(pv_dates.get(c["wiki_title"]) or latest(WIKI_FETCHED, seed_date))
        visit, visit_approx = (int(act["visit_minutes"]), False) if act and act["visit_minutes"] else (d["visit"], True)
        src.append((f"visit: {visit} min from the activity page" if not visit_approx else f"visit: {ptype} default {visit} min")
                   + "; tags/type/outdoor: "
                   + ("from the activity page" if act else "curated from OpenTripMap kinds, OSM tags and the Wikipedia summary"))
        if c.get("note"):
            src.append(c["note"])
        if todo:
            src.insert(0, "TODO: " + "; ".join(todo))
        rows.append([f"{city}-A-{i:02d}", city, c["name"], f"{float(c['lat']):.5f}", f"{float(c['lon']):.5f}", visit, str(visit_approx).lower(),
                     open_t, close_t, ";".join(str(x) for x in closed), str(hours_approx).lower(),
                     "" if fee is None else fee, str(fee_approx).lower(), c["tags"], "" if r is None else f"{r:.1f}", c["outdoor"],
                     crowd.get(c["candidate"], ""), c.get("fixed_slot", "false"), " | ".join(src),
                     "" if todo else latest(*dates)])
    return rows


def main(argv: list[str] | None = None) -> int:
    for city in (argv if argv is not None else sys.argv[1:]):
        rows = build(city)
        write_csv(CURATED / rules.ATTRACTIONS_DIR / f"{city}.csv", HEADER, rows)
        print(city, len(rows), "attractions,", sum(1 for r in rows if r[-1] == ""), "TODO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
