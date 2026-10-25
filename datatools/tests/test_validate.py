"""DATA-AT-02: validator self-test.

`fixtures/valid` is a small fake 2-city dataset (JAI, AGR) that passes every rule.
Each broken case copies it to a temp directory, breaks exactly one rule, and checks
that the validator reports exactly that error and exits non-zero.
"""

import csv
import json
import shutil
from pathlib import Path

import pytest

from datatools.validate import main, validate

VALID = Path(__file__).parent / "fixtures" / "valid"
CITIES = ["JAI", "AGR"]
CITIES_ARG = ",".join(CITIES)


def set_cell(path: Path, key_col: str, key: str, col: str, value: str) -> None:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header, rows = reader.fieldnames, list(reader)
    hits = [r for r in rows if r[key_col] == key]
    assert len(hits) == 1, f"{key} not found once in {path.name}"
    hits[0][col] = value
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def drop_matrix_node(path: Path, node: str) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    i = doc["nodes"].index(node)
    doc["nodes"].pop(i)
    for grid in ("km", "minutes_free_flow"):
        doc[grid].pop(i)
        for row in doc[grid]:
            row.pop(i)
    path.write_text(json.dumps(doc), encoding="utf-8")


def drop_tag(path: Path, tag: str, keep: int) -> None:
    """Remove `tag` from all but the first `keep` rows that carry it (a row left with no tag gets 'shopping')."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header, rows = reader.fieldnames, list(reader)
    for r in [r for r in rows if tag in r["tags"].split(";")][keep:]:
        r["tags"] = ";".join(t for t in r["tags"].split(";") if t != tag) or "shopping"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def set_pair(path: Path, **cells: str) -> None:
    for col, value in cells.items():
        set_cell(path, "city_a", "AGR", col, value)


# (id, mutation, expected (file, row, field, code))
BROKEN = [
    ("missing_source",
     lambda d: set_cell(d / "attractions/JAI.csv", "attraction_id", "JAI-A-26", "source", ""),
     ("attractions/JAI.csv", "27", "source", "missing_source")),
    ("bad_tag",
     lambda d: set_cell(d / "attractions/AGR.csv", "attraction_id", "AGR-A-26", "tags", "shopping;museums"),
     ("attractions/AGR.csv", "27", "tags", "bad_tag")),
    ("open_not_before_close",
     lambda d: (set_cell(d / "attractions/JAI.csv", "attraction_id", "JAI-A-03", "open_time", "09:00"),
                set_cell(d / "attractions/JAI.csv", "attraction_id", "JAI-A-03", "close_time", "08:30")),
     ("attractions/JAI.csv", "4", "close_time", "open_not_before_close")),
    ("closed_all_week",
     lambda d: set_cell(d / "attractions/JAI.csv", "attraction_id", "JAI-A-05", "closed_weekdays", "0;1;2;3;4;5;6"),
     ("attractions/JAI.csv", "6", "closed_weekdays", "closed_all_week")),
    ("unknown_city",
     lambda d: set_cell(d / "attractions/JAI.csv", "attraction_id", "JAI-A-26", "city_id", "XYZ"),
     ("attractions/JAI.csv", "27", "city_id", "unknown_city")),
    ("price_out_of_band",
     lambda d: set_cell(d / "hotels.csv", "hotel_id", "AGR-H-05", "price_per_room_night", "9000"),
     ("hotels.csv", "15", "price_per_room_night", "price_out_of_band")),
    ("matrix_missing_node",
     lambda d: drop_matrix_node(d / "matrices/JAI.json", "JAI-A-10"),
     ("matrices/JAI.json", "-", "nodes", "matrix_missing_node")),
    ("too_few_food",
     lambda d: drop_tag(d / "attractions/AGR.csv", "food", keep=1),
     ("attractions/AGR.csv", "-", "tags", "tag_coverage")),
    ("pair_no_mode",
     lambda d: set_pair(d / "city_pairs.csv", train_available="false", bus_available="false"),
     ("city_pairs.csv", "2", "-", "pair_no_mode")),
]


@pytest.fixture
def broken_dir(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    shutil.copytree(VALID, target)
    return target


def test_valid_fixture_has_no_issues(capsys):
    assert validate(VALID, CITIES) == []
    assert main(["--data", str(VALID), "--cities", CITIES_ARG]) == 0
    assert capsys.readouterr().out.strip().endswith("0 errors, 0 warnings")


@pytest.mark.parametrize("mutate, expected", [b[1:] for b in BROKEN], ids=[b[0] for b in BROKEN])
def test_each_broken_rule_gives_exactly_its_error(broken_dir, mutate, expected, capsys):
    mutate(broken_dir)

    issues = validate(broken_dir, CITIES)
    assert [(i.file, i.row, i.field, i.code) for i in issues] == [expected]

    assert main(["--data", str(broken_dir), "--cities", CITIES_ARG]) == 1
    out = capsys.readouterr().out.splitlines()
    file, row, field, _ = expected
    assert out[0].startswith(f"{file}:{row}:{field}: ")
    assert out[-1] == "1 errors, 0 warnings"


def test_open_not_before_close_message_format(broken_dir):
    BROKEN[2][1](broken_dir)
    (issue,) = validate(broken_dir, CITIES)
    assert str(issue) == "attractions/JAI.csv:4:close_time: must be later than open_time (09:00 ≥ 08:30)"


def test_unreadable_file_and_bad_cells_do_not_cascade(broken_dir):
    hubs = broken_dir / "hubs.csv"
    hubs.write_text(hubs.read_text(encoding="utf-8").replace("hub_code", "code", 1), encoding="utf-8")
    set_pair(broken_dir / "city_pairs.csv", train_available="yes")
    set_cell(broken_dir / "attractions/AGR.csv", "attraction_id", "AGR-A-04", "close_time", "25:00")

    issues = validate(broken_dir, CITIES)
    assert [(i.file, i.code) for i in issues] == [
        ("attractions/AGR.csv", "bad_time"),
        ("city_pairs.csv", "bad_bool"),
        ("hubs.csv", "bad_header"),
    ]
    assert str(issues[1]) == "city_pairs.csv:2:train_available: must be true or false, got 'yes'"


def test_missing_cities_are_reported_without_the_cities_option():
    issues = validate(VALID)
    missing = {i.message for i in issues if i.code == "missing_city"}
    assert len(missing) == 13
