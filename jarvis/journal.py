"""The day's ledger. Every workflow appends what it did or what got done here, and the
end-of-day report reads it back. One markdown file per day, append-only.

    python -m jarvis.journal done "Submitted the Datadog application"
    python -m jarvis.journal todo "Send rating sheet to teammates"
    python -m jarvis.journal note "n8n tunnel flaky; use static JSON on video day"
    python -m jarvis.journal show          # today's entries
"""
from __future__ import annotations

import re
import sys

from .config import JOURNAL, now, today

KINDS = ("done", "todo", "note", "auto")   # auto = written by a workflow, not a person


def path(day: str | None = None):
    return JOURNAL / f"{day or today()}.md"


def add(kind: str, text: str, day: str | None = None) -> None:
    if kind not in KINDS:
        raise SystemExit(f"kind must be one of {KINDS}")
    p = path(day)
    if not p.exists():
        p.write_text(f"# {day or today()}\n\n", encoding="utf-8")
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"- [{kind}] {now().strftime('%H:%M')} {text.strip()}\n")


def entries(day: str | None = None) -> dict[str, list[str]]:
    p = path(day)
    out: dict[str, list[str]] = {k: [] for k in KINDS}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"- \[(\w+)\] (\d\d:\d\d) (.*)", line)
        if m and m.group(1) in out:
            out[m.group(1)].append(f"{m.group(2)} {m.group(3)}")
    return out


def carry_forward(days_back: int = 7) -> list[str]:
    """Todos written in the last week that were never marked done (by exact text match)."""
    from datetime import timedelta
    open_items: list[str] = []
    done_text: set[str] = set()
    for i in range(days_back, -1, -1):
        d = (now() - timedelta(days=i)).strftime("%Y-%m-%d")
        e = entries(d)
        done_text |= {x.split(" ", 1)[1].lower() for x in e["done"]}
        open_items += [x.split(" ", 1)[1] for x in e["todo"]]
    seen: set[str] = set()
    out = []
    for t in open_items:
        if t.lower() not in done_text and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "show":
        e = entries()
        for k, v in e.items():
            for x in v:
                print(f"[{k}] {x}")
    else:
        add(sys.argv[1], " ".join(sys.argv[2:]))
        print("ok")
