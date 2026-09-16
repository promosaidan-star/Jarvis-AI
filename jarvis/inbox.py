"""Email and calendar: summarize what needs doing, and draft replies that a person sends.

Gmail and Google Calendar are reached through n8n's own nodes (that is where the Google
OAuth lives). The n8n workflow drops two files here before calling this module:

    inbox/today_inbox.json     [{id, threadId, from, subject, date, snippet, labels}]
    inbox/today_calendar.json  [{summary, start, end, location, attendees, description}]

This module then:
  - `todo`   -> a short "things you need to do" list, with the email/meeting each came from
  - `drafts` -> reply drafts as JSON; the workflow turns them into Gmail DRAFTS (never sends)

Replies are written in AJ's voice and are always saved as drafts for a human to send.
That is a design rule, not a missing feature.

    python -m jarvis.inbox todo
    python -m jarvis.inbox drafts > out/drafts.json
"""
from __future__ import annotations

import json
import sys

from .config import INBOX, OUT
from .llm import VOICE, ask_json

IGNORE_SENDERS = ("noreply", "no-reply", "notifications@", "newsletter", "linkedin.com", "glassdoor",
                  "indeed.com", "mailer-daemon", "calendar-notification")


def load(name: str) -> list[dict]:
    p = INBOX / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def humans_only(msgs: list[dict]) -> list[dict]:
    return [m for m in msgs if not any(s in (m.get("from") or "").lower() for s in IGNORE_SENDERS)]


def todo() -> dict:
    inbox, cal = humans_only(load("today_inbox.json")), load("today_calendar.json")
    if not inbox and not cal:
        return {"items": [], "note": "no inbox/calendar files from n8n yet"}
    system = ("You turn today's emails and meetings into a to-do list. Output JSON: "
              '{"items":[{"task": str, "why": str, "source": "email: <subject>" | "meeting: <summary>", '
              '"due": str|null, "priority": "high"|"normal"|"low"}]}. '
              "Only real actions the recipient must take. Merge duplicates. No more than 12 items. " + VOICE)
    user = f"EMAILS:\n{json.dumps(inbox[:40])}\n\nMEETINGS:\n{json.dumps(cal)}"
    return ask_json(system, user)


def drafts() -> list[dict]:
    inbox = humans_only(load("today_inbox.json"))
    system = ("For each email that actually needs a reply from AJ, draft one. Skip newsletters, "
              "receipts, FYIs, and anything already answered. Output JSON: "
              '{"drafts":[{"id": str, "threadId": str, "to": str, "subject": str, "body": str, '
              '"reason": str}]}. Plain text body, 2-5 sentences, sign off "AJ". ' + VOICE)
    out = ask_json(system, json.dumps(inbox[:40])).get("drafts", [])
    (OUT / "drafts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def calendar_lines(cal: list[dict] | None = None) -> list[str]:
    cal = cal if cal is not None else load("today_calendar.json")
    lines = []
    for e in sorted(cal, key=lambda e: str(e.get("start"))):
        start = str(e.get("start", ""))[11:16] or "all day"
        where = f" · {e['location']}" if e.get("location") else ""
        lines.append(f"{start} {e.get('summary', '(no title)')}{where}")
    return lines


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "todo"
    print(json.dumps(drafts() if cmd == "drafts" else todo(), indent=1))
