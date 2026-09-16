"""The morning brief: weather, today's calendar, what the inbox needs, open tickets, the
paper portfolio, and anything carried over from yesterday. Written to
journal/briefs/<date>.md and printed; n8n mails it to you.

    python -m jarvis.morning_brief
    python -m jarvis.morning_brief --no-llm     # skip the inbox summary (no Gemini call)
"""
from __future__ import annotations

import sys
import traceback

from . import inbox, journal, portfolio, tickets, weather
from .config import JOURNAL, now, today


def _section(title: str, fn):
    try:
        body = fn()
    except SystemExit as e:          # a missing key: say so, keep going
        body = f"_not configured: {e}_"
    except Exception as e:           # a dead API must not kill the brief
        body = f"_unavailable: {type(e).__name__}: {e}_"
        traceback.print_exc(file=sys.stderr)
    return f"## {title}\n\n{body}\n"


def build(use_llm: bool = True) -> str:
    def inbox_block():
        cal = inbox.calendar_lines()
        out = ["**Calendar**", *(f"- {l}" for l in cal)] if cal else ["**Calendar**: nothing on file from n8n"]
        if use_llm:
            t = inbox.todo()
            items = t.get("items", [])
            out.append("\n**Needs doing**" if items else f"\n**Needs doing**: {t.get('note', 'nothing flagged')}")
            for it in items:
                due = f" (due {it['due']})" if it.get("due") else ""
                out.append(f"- [{it.get('priority', 'normal')}] {it['task']}{due} — _{it.get('source', '')}_")
        return "\n".join(out)

    def carry():
        c = journal.carry_forward()
        return "\n".join(f"- {x}" for x in c) if c else "Nothing carried over."

    parts = [f"# Morning brief — {now().strftime('%A %d %B %Y')}\n",
             _section("Weather", weather.report),
             _section("Today", inbox_block),
             _section("Carried over", carry),
             _section("Open tickets", tickets.report),
             _section("Paper portfolio", portfolio.report)]
    md = "\n".join(parts)
    (JOURNAL / "briefs" / f"{today()}.md").write_text(md, encoding="utf-8")
    journal.add("auto", "morning brief written")
    return md


if __name__ == "__main__":
    print(build(use_llm="--no-llm" not in sys.argv))
