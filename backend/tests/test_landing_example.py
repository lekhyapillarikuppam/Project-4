"""The Landing page's example day must be exactly what the engine plans from the curated data (no made-up numbers)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))

import make_landing_example  # noqa: E402


def test_landing_example_matches_the_engine():
    shipped = json.loads(make_landing_example.OUT.read_text(encoding="utf-8"))
    assert shipped == make_landing_example.example(), "re-run: python eval/make_landing_example.py"
