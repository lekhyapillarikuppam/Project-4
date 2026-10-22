"""Read the curated CSV/JSON files into models (001 Plan §2.1 conventions).

CSV: UTF-8, header row, `;` inside a cell for lists, `true`/`false` for booleans,
empty cell = missing.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError


@dataclass(frozen=True, order=True)
class Issue:
    """One validation finding, printed as `file:row:field: message`."""

    file: str
    row: str          # file line number (header is line 1), or "-" for whole-file issues
    field: str        # column name, or "-"
    code: str         # stable machine code, used by tests
    message: str
    severity: str = "error"   # "error" or "warning"

    def __str__(self) -> str:
        return f"{self.file}:{self.row}:{self.field}: {self.message}"


@dataclass
class Row:
    line: int
    raw: dict[str, str | None]
    model: BaseModel | None = None   # None when the row failed type-level parsing


@dataclass
class Table:
    file: str                        # path relative to the data directory, with forward slashes
    rows: list[Row] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def models(self) -> list[Any]:
        return [r.model for r in self.rows if r.model is not None]

    @property
    def failed(self) -> list[Row]:
        return [r for r in self.rows if r.model is None]

    @property
    def readable(self) -> bool:
        """False when the file is missing or its header is wrong (no rows were read)."""
        return not any(i.code in ("missing_file", "bad_header") for i in self.issues)


def split_list(cell: str | None) -> list[str]:
    """Split a `;`-separated list cell. Missing or blank means an empty list."""
    if cell is None:
        return []
    return [part.strip() for part in cell.split(";") if part.strip()]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _code_for(error: dict) -> str:
    """Map a Pydantic error to one of our codes."""
    etype = error["type"]
    if error.get("input") is None:
        return "missing_value"
    if etype in ("greater_than", "greater_than_equal", "less_than", "less_than_equal"):
        return "out_of_range"
    if etype == "literal_error":
        return "bad_enum"
    if etype == "string_pattern_mismatch":
        return "bad_format"
    if etype in ("too_short", "too_long"):
        return "bad_length"
    if etype.startswith(("int_", "float_", "decimal_")):
        return "bad_number"
    return etype   # custom errors already carry our code as their type


def read_csv(data_dir: Path, rel: str, model: type[BaseModel], context: dict | None = None) -> Table:
    """Read one CSV into a Table. Missing file, bad header and bad cells become Issues."""
    table = Table(file=rel)
    path = data_dir / rel
    if not path.is_file():
        table.issues.append(Issue(rel, "-", "-", "missing_file", "file not found"))
        return table

    expected = [f.alias or name for name, f in model.model_fields.items()]
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in expected if c not in header]
        extra = [c for c in header if c not in expected]
        if missing or extra:
            parts = []
            if missing:
                parts.append("missing columns " + ", ".join(missing))
            if extra:
                parts.append("unexpected columns " + ", ".join(extra))
            table.issues.append(Issue(rel, "1", "-", "bad_header", "; ".join(parts)))
            return table

        for raw in reader:
            line = reader.line_num
            cleaned = {k: _clean(v) for k, v in raw.items() if k is not None}
            row = Row(line=line, raw=cleaned)
            try:
                row.model = model.model_validate(cleaned, context=context)
            except ValidationError as exc:
                for err in exc.errors():
                    fld = str(err["loc"][0]) if err["loc"] else "-"
                    table.issues.append(Issue(rel, str(line), fld, _code_for(err), err["msg"]))
            table.rows.append(row)
    return table


def read_json(data_dir: Path, rel: str) -> tuple[Any | None, list[Issue]]:
    path = data_dir / rel
    if not path.is_file():
        return None, [Issue(rel, "-", "-", "missing_file", "file not found")]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return None, [Issue(rel, str(exc.lineno), "-", "bad_json", f"invalid JSON: {exc.msg}")]


def read_version(data_dir: Path, rel: str) -> tuple[dict[str, str] | None, list[Issue]]:
    """Read `key=value` lines from the VERSION file."""
    path = data_dir / rel
    if not path.is_file():
        return None, [Issue(rel, "-", "-", "missing_file", "file not found")]
    values: dict[str, str] = {}
    issues: list[Issue] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        key, sep, value = line.partition("=")
        if not sep:
            issues.append(Issue(rel, str(n), "-", "bad_version", f"expected key=value, got {line!r}"))
            continue
        values[key.strip()] = value.strip()
    return values, issues
