"""Engine configuration: every tunable comes from config.yaml (NFR-009, ENG-FR-09)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

CONFIG_FILE = Path(__file__).with_name("config.yaml")


def hhmm(text: str) -> int:
    """'HH:MM' -> minutes after midnight."""
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _freeze(x: Any) -> Any:
    if isinstance(x, dict):
        return MappingProxyType({k: _freeze(v) for k, v in x.items()})
    if isinstance(x, list):
        return tuple(_freeze(v) for v in x)
    return x


class Config:
    """Read-only view of config.yaml. Keys are attributes; nested maps are read-only dicts."""

    def __init__(self, raw: dict, path: Path):
        self._raw = _freeze(raw)
        self._plain = raw
        self.path = path

    def as_dict(self) -> dict:
        """The plain mapping, for code that must not import this module (the validator)."""
        return self._plain

    def __getattr__(self, key: str) -> Any:
        try:
            return self._raw[key]
        except KeyError as exc:
            raise AttributeError(f"config has no key {key!r}") from exc

    @property
    def data_dir(self) -> Path:
        return (self.path.parent / self._raw["data_dir"]).resolve()


def load(path: Path | str | None = None) -> Config:
    p = Path(path) if path else CONFIG_FILE
    return Config(yaml.safe_load(p.read_text(encoding="utf-8")), p)


@lru_cache(maxsize=1)
def default() -> Config:
    return load()
