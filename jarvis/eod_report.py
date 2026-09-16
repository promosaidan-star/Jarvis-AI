"""End-of-day report: what got done, what is still open, and what tomorrow needs.
Sources: today's journal, GitHub issues closed today, tomorrow's calendar (if n8n dropped
it), open tickets, and the paper account's close. Written to journal/reports/<date>.md.

    python -m jarvis.eod_report
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback

from . import inbox, journal, portfolio, tickets
from .config import JOURNAL, now, today


def closed_today() -> list[str]:
    raw = subprocess.run(["gh", "api", f"search/issues?q=assignee:@me+is:issue+is:closed+closed:>={today()}",
                          "--jq", ".items[] | \"\\(.repository_url|split(\"/\")[-1])#\\(.number) \\(.title)\""],
                         capture_output=True, text=True).stdout
    return [l for l in raw.splitlines() if l.strip()]


def _section(title, fn):
    try:
        body = fn()
    except SystemExit as e:
        body = f"_not configured: {e}_"
    except Exception as e:
        body = f"_unavailable: {type(e).__name__}: {e}_"
        traceback.print_exc(file=sys.stderr)
    return f"## {title}\n\n{body}\n"


def build() -> str:
    e = journal.entries()

    def done():
        items = [x for x in e["done"]] + [f"closed {x}" for x in closed_today()]
        auto = e["auto"]
        out = [f"- {x}" for x in items] or ["- nothing logged as done today"]
        if auto:
            out.append(f"\n_{len(auto)} automated steps ran: " + "; ".join(a.split(' ', 1)[1] for a in auto) + "_")
        return "\n".join(out)

    def still_open():
        c = journal.carry_forward()
        return "\n".join(f"- {x}" for x in c) if c else "Nothing open in the journal."

    def tomorrow():
        cal = inbox.load("tomorrow_calendar.json")
        lines = inbox.calendar_lines(cal) if cal else []
        return "\n".join(f"- {l}" for l in lines) if lines else "No calendar file for tomorrow from n8n."

    def notes():
        return "\n".join(f"- {x}" for x in e["note"]) if e["note"] else "—"

    parts = [f"# End of day — {now().strftime('%A %d %B %Y')}\n",
             _section("Completed", done),
             _section("Still open (carry to tomorrow)", still_open),
             _section("Tomorrow", tomorrow),
             _section("Open tickets", tickets.report),
             _section("Notes", notes),
             _section("Paper portfolio at close", portfolio.report)]
    md = "\n".join(parts)
    (JOURNAL / "reports" / f"{today()}.md").write_text(md, encoding="utf-8")
    journal.add("auto", "end-of-day report written")
    return md


if __name__ == "__main__":
    print(build())
