"""Open tickets = GitHub issues assigned to the user, via the `gh` CLI (already logged in).

    python -m jarvis.tickets            # grouped list
    python -m jarvis.tickets --json
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone


def fetch(limit: int = 100) -> list[dict]:
    q = "assignee:@me+is:open+is:issue"     # gh api takes the raw query string: use + not spaces
    proc = subprocess.run(["gh", "api", f"search/issues?q={q}&per_page={limit}&sort=updated", "--jq", ".items"],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip()[:200] or "gh api failed (is `gh auth login` done?)")
    raw = proc.stdout
    items = json.loads(raw or "[]")
    now = datetime.now(timezone.utc)
    out = []
    for it in items:
        updated = datetime.fromisoformat(it["updated_at"].replace("Z", "+00:00"))
        out.append({"repo": it["repository_url"].rsplit("/", 1)[-1], "number": it["number"], "title": it["title"],
                    "url": it["html_url"], "labels": [l["name"] for l in it.get("labels", [])],
                    "days_since_update": (now - updated).days,
                    "milestone": (it.get("milestone") or {}).get("title")})
    return out


def report(tickets: list[dict] | None = None) -> str:
    t = tickets if tickets is not None else fetch()
    if not t:
        return "No open tickets assigned to you."
    by_repo: dict[str, list[dict]] = {}
    for x in t:
        by_repo.setdefault(x["repo"], []).append(x)
    lines = [f"{len(t)} open tickets assigned to you:"]
    for repo, items in by_repo.items():
        lines.append(f"  {repo} ({len(items)})")
        for x in sorted(items, key=lambda x: x["days_since_update"])[:6]:
            stale = "  ⚠ stale" if x["days_since_update"] > 21 else ""
            lines.append(f"    #{x['number']} {x['title']} — {x['days_since_update']}d{stale}")
        if len(items) > 6:
            lines.append(f"    … and {len(items) - 6} more")
    return "\n".join(lines)


if __name__ == "__main__":
    t = fetch()
    print(json.dumps(t, indent=1) if "--json" in sys.argv else report(t))
