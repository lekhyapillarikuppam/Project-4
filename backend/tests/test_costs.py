"""ENG-AT-03: cost model unit tests (002 Spec §5) on hand-computed examples: 1, 3 and 6 people; auto and cab."""

from tests.helpers import CFG, fixture_ds, request
from tripwise import costs
from tripwise import timemodel as tm
from tripwise.data import Hotel


def train3a(req):
    return next(o for o in tm.options(fixture_ds(), CFG, req, "out") if o.key == "train 3A")


def test_fare_and_journey():
    ds = fixture_ds()
    # 3A: max(300, 40 + 1.3 × 240 = 352) = 352 per person; JAI train access 90 per vehicle
    r1 = request(people=1, prefs={"comfort": "budget"})       # auto, capacity 3
    assert costs.fare(ds, train3a(r1)) == 352
    assert costs.journey(ds, CFG, r1, train3a(r1)) == 352 + 90
    r3 = request(people=3)                                     # cab, capacity 4: 1 vehicle
    assert costs.journey(ds, CFG, r3, train3a(r3)) == 3 * 352 + 90
    r6 = request(people=6)                                     # cab: 2 vehicles
    assert costs.journey(ds, CFG, r6, train3a(r6)) == 6 * 352 + 2 * 90
    sl = next(o for o in tm.options(ds, CFG, r1, "out") if o.key == "train SL")
    assert costs.fare(ds, sl) == 140                           # 20 + 0.5 × 240 = 140 > min 100


def test_rides_auto_and_cab():
    ds = fixture_ds()
    r1 = request(people=1, prefs={"comfort": "budget"})
    assert costs.ride(ds, CFG, r1, 1.0) == 30                  # within min_km
    assert costs.ride(ds, CFG, r1, 3.2) == 56                  # 30 + 15 × 1.7 = 55.5 → 56
    assert costs.ride(ds, CFG, request(people=6, prefs={"comfort": "budget"}), 3.2) == 112   # 2 autos
    assert costs.ride(ds, CFG, request(people=3), 7.4) == 182  # cab 100 + 24 × 3.4 = 181.6 → 182
    assert costs.ride(ds, CFG, request(people=6), 7.4) == 364  # 2 cabs
    assert costs.est_local(ds, CFG, request(people=3), 5.0) == 148   # ride(0.6 × 2 × 5 = 6 km) = 100 + 48


def test_stay_food_entry_contingency():
    ds = fixture_ds()
    h = Hotel("JAI-H-01", "JAI", "x", "mid", 0, 0, 3200)
    assert costs.stay(request(people=3), h) == 3 * 2 * 3200     # 3 nights × 2 rooms
    assert costs.stay(request(people=1), h) == 3 * 1 * 3200
    assert costs.food(ds, request(people=3)) == 3 * 4 * 800      # JAI multiplier 1.0
    agr = request(origin="JAI", destination="AGR", people=1, start_date="2026-12-14", end_date="2026-12-15",
                  prefs={"comfort": "budget"})
    assert costs.food(ds, agr) == 720                            # 1 × 2 × 400 × 0.9
    big = request(origin="JAI", destination="AGR", people=6, start_date="2026-12-14", end_date="2026-12-20",
                  prefs={"comfort": "premium"})
    assert costs.food(ds, big) == 60480                          # 6 × 7 × 1600 × 0.9
    assert costs.entry(request(people=6), 150) == 900
    assert costs.usable_budget(40001, CFG) == 36000 and costs.contingency(40001, CFG) == 4001
