"""Shared settings: where secrets come from, where output goes, who and where the user is.

Secrets are read from `Jarvis-AI/.env` (never committed), falling back to the environment.
Every module that talks to an outside service goes through `env()` so a missing key fails
with a plain message instead of a stack trace.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "journal"          # one markdown file per day + briefs/ + reports/
INBOX = ROOT / "inbox"              # JSON dropped by the n8n Gmail / Calendar nodes
OUT = ROOT / "out"                  # generated files (slides, playlists)
TZ = ZoneInfo(os.environ.get("JARVIS_TZ", "America/New_York"))

USER = {
    "name": "AJ",
    "city": "Cambridge, MA",
    "lat": 42.3736, "lon": -71.1097,
    "github": "promosaidan-star",
}

_ENV_FILES = [ROOT / ".env", Path.home() / "Documents" / "AJ-Algo-Trader" / ".env"]


def _load_env() -> dict[str, str]:
    found: dict[str, str] = {}
    for f in _ENV_FILES:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                found.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return found


_FILE_ENV = _load_env()


def env(key: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.environ.get(key) or _FILE_ENV.get(key) or default
    if required and not val:
        raise SystemExit(f"{key} is not set. Add it to {ROOT / '.env'} (see .env.example).")
    return val


def now() -> datetime:
    return datetime.now(TZ)


def today() -> str:
    return now().strftime("%Y-%m-%d")


for d in (JOURNAL, JOURNAL / "briefs", JOURNAL / "reports", INBOX, OUT):
    d.mkdir(parents=True, exist_ok=True)
