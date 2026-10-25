"""Environment settings (004 Plan). Secrets come only from the environment or the git-ignored .env."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    frontend_origin: str
    db_schema: str
    app_env: str          # "development" also allows http://localhost:5173 (API-FR-12)

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.frontend_origin] if self.frontend_origin else []
        if self.app_env == "development" and "http://localhost:5173" not in origins:
            origins.append("http://localhost:5173")
        return origins


@lru_cache(maxsize=1)
def get() -> Settings:
    load_dotenv(ROOT / ".env")
    schema = os.environ.get("DB_SCHEMA", "app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise RuntimeError(f"bad DB_SCHEMA {schema!r}")
    missing = [k for k in ("DATABASE_URL", "JWT_SECRET") if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")
    return Settings(os.environ["DATABASE_URL"], os.environ["JWT_SECRET"], os.environ.get("FRONTEND_ORIGIN", ""),
                    schema, os.environ.get("APP_ENV", "development"))
