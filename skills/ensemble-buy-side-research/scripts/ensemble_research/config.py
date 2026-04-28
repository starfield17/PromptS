from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True)
class Settings:
    sec_user_agent: str | None
    newsapi_key: str | None
    tushare_token: str | None
    cache_dir: Path
    request_timeout: int = 20

def load_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv()

    return Settings(
        sec_user_agent=os.getenv("SEC_USER_AGENT"),
        newsapi_key=os.getenv("NEWSAPI_KEY"),
        tushare_token=os.getenv("TUSHARE_TOKEN"),
        cache_dir=Path(os.getenv("ENSEMBLE_CACHE_DIR", ".ensemble_cache")),
        request_timeout=int(os.getenv("ENSEMBLE_REQUEST_TIMEOUT", "20")),
    )


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_csv(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = []
        for item in value:
            parts.extend(str(item).split(","))
    return [part.strip() for part in parts if part and part.strip()]


def slugify(value: str, max_len: int = 64) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return (value or "item")[:max_len].strip("-") or "item"


def confidence_from_count(count: int) -> str:
    if count >= 5:
        return "high"
    if count >= 2:
        return "medium"
    if count == 1:
        return "low"
    return "unknown"
