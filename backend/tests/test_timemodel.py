"""ENG-AT-02: time model unit tests (002 Spec §4), hand-computed."""

from tests.helpers import CFG, fixture_ds, option, request
from tripwise import timemodel as tm


def test_options_daytime_pair_and_avoided_mode():
    ds = fixture_ds()
    opts = tm.options(ds, CFG, request(), "out")
    assert sorted(o.key for o in opts) == ["bus ACS", "train 2A", "train 3A", "train SL"]
    assert all(not o.overnight for o in opts)
    assert sorted(o.key for o in tm.options(ds, CFG, request(prefs={"modes": {"bus": "avoid"}}), "ret")) == \
        ["train 2A", "train 3A", "train SL"]
    assert tm.options(ds, CFG, request(prefs={"modes": {"bus": "avoid", "train": "avoid"}}), "out") == []


def test_daytime_outbound_and_return_train():
    ds = fixture_ds()
    out = next(o for o in tm.options(ds, CFG, request(), "out") if o.key == "train 3A")
    t = tm.outbound_times(out, CFG)
    assert t == {"depart": 360, "arrive_centre": 360 + 322 + 11, "day1_earliest": 693 + 30}
    ret = next(o for o in tm.options(ds, CFG, request(), "ret") if o.key == "train 3A")
    r = tm.return_times(ret, CFG)
    assert r == {"leave_centre": 1380 - 333, "arrive_origin": 1380, "dayD_latest": 1047 - 30}
    assert tm.door_minutes(out, CFG) == 12 + 322 + 11      # AGR train access + mode + JAI train access


def test_flight_daytime_both_directions():
    out = option("flight", 120, 44, False)
    assert tm.outbound_times(out, CFG) == {"depart": 420, "arrive_centre": 584, "day1_earliest": 614}
    assert tm.return_times(option("flight", 120, 44, False, "ret"), CFG) == \
        {"leave_centre": 1380 - (120 + 44 + 90), "arrive_origin": 1380, "dayD_latest": 1126 - 30}
    assert tm.door_minutes(out, CFG) == 15 + 120 + 44 + 90


def test_overnight_both_directions():
    assert tm.outbound_times(option("train", 600, 20, True), CFG) == \
        {"depart": (420 - 600) % 1440, "arrive_centre": 440, "day1_earliest": 500}
    assert tm.return_times(option("train", 600, 20, True, "ret"), CFG) == \
        {"leave_centre": 1240, "arrive_origin": (1260 + 600) % 1440, "dayD_latest": 1210}


def test_day_windows_and_usable_time():
    req = request()                                  # 4 days, 09:00-18:00, balanced
    w = tm.day_windows(req, CFG, option("train", 600, 20, True), option("train", 600, 20, True, "ret"))
    assert [(x.start, x.end) for x in w] == [(540, 1080), (540, 1080), (540, 1080), (540, 1080)]
    assert w[0].weekday == 0 and w[0].date == "2026-12-14"
    assert all(x.lunch for x in w) and w[1].usable == int((540 - 60) * 0.9) and w[1].max_count == 4
    w = tm.day_windows(req, CFG, option("flight", 120, 44, False), option("flight", 120, 44, False, "ret"))
    assert (w[0].start, w[0].end, w[3].start, w[3].end) == (614, 1080, 540, 1080)
    assert w[0].lunch is True                        # 10:14-18:00 holds a 12:30 lunch
    assert w[0].usable == int((1080 - 614 - 60) * 0.9)


def test_short_window_has_no_activities():
    req = request(prefs={"daily_hours_out": 4})        # 09:00-13:00
    w = tm.first_window(req, CFG, option("train", 322, 11, False))
    assert (w.start, w.end, w.active, w.usable, w.max_count) == (723, 780, False, 0, 0)


def test_lunch_boundary_at_six_hours():
    assert tm.lunch_fits(540, 900, CFG) is True       # exactly 6 h, 09:00-15:00
    assert tm.lunch_fits(540, 899, CFG) is False      # 5 h 59
    assert tm.lunch_fits(900, 1380, CFG) is False     # 8 h but starts after 14:30
    assert tm.lunch_fits(840, 1260, CFG) is True      # 14:00-21:00, lunch 14:00-15:00
