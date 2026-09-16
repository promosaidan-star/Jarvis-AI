"""The JSON the dashboard reads: `GET /webhook/jarvis/today` in n8n runs this.

Everything is read from files the other modules already wrote (today's brief, today's
report, journal, Spotify picks) plus two live reads that are cheap and keyless from the
caller's side (weather, paper account). No LLM call, so it is fast and safe to poll.

    python -m jarvis.api
"""
from __future__ import annotations

import json
from pathlib import Path

from . import inbox, journal, portfolio, tickets, weather
from .config import JOURNAL, OUT, now, today


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:  # a dead feed shows up as its error string, never as a crash
        return {"error": f"{type(e).__name__}: {e}"} if default is None else default


def _read(p: Path):
    return p.read_text(encoding="utf-8") if p.exists() else None


def payload() -> dict:
    d = today()
    picks = OUT / f"spotify_recs_{d}.json"
    return {
        "date": d, "generated_at": now().isoformat(timespec="seconds"),
        "weather": _safe(weather.fetch),
        "portfolio": _safe(portfolio.snapshot),
        "tickets": _safe(tickets.fetch, default=[]),
        "calendar": _safe(inbox.calendar_lines, default=[]),
        "journal": journal.entries(d),
        "carry_forward": journal.carry_forward(),
        "morning_brief_md": _read(JOURNAL / "briefs" / f"{d}.md"),
        "eod_report_md": _read(JOURNAL / "reports" / f"{d}.md"),
        "spotify": json.loads(picks.read_text(encoding="utf-8")) if picks.exists() else None,
        "drafts_pending": json.loads((OUT / "drafts.json").read_text(encoding="utf-8")) if (OUT / "drafts.json").exists() else [],
        "disclaimer": "Read-only assistant. Emails are saved as drafts for you to send; the Alpaca account is paper and never traded from here.",
    }


if __name__ == "__main__":
    print(json.dumps(payload(), ensure_ascii=False))
