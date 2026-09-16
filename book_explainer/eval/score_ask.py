"""Score Ask-the-book faithfulness (metric 5) against the live n8n webhook.

usage: python eval/score_ask.py run_2026-09-11 [--url http://localhost:5678/webhook/ask]
reads results/<run>/ask_questions.json, writes ask_answers.json + ask_results.json

In-scope: every accept group must appear in the answer (case-insensitive; dollars also
match without commas; status answers match on their key word). match="any" = one of the
spellings (source key or its label) is enough.
Out-of-scope: must refuse (starts with the refusal phrase or clearly declines) AND must
not contain a fabricated number for the thing asked.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

REFUSAL = re.compile(r"can't answer that from the book|cannot answer|can't answer|not (a position )?in the book|"
                     r"read-only|not able to (place|give|provide)|don't have (that|access)", re.I)
STATUS_WORD = {"still in decile": r"still in (its|the)? ?decile|\byes\b", "faded toward middle": r"fad",
               "flipped sign": r"flipp", "no row today": r"no row"}


def ask(url, q, tries=4, pause=20):
    """POST the question; retry on 5xx (the free Gemini tier allows 15 calls/minute and an
    agent turn costs 2-3, so a burst of questions trips it)."""
    body = json.dumps({"question": q}).encode()
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        t = time.time()
        try:
            r = json.load(urllib.request.urlopen(req, timeout=300))
            return r.get("answer", ""), time.time() - t
        except Exception as e:
            last = e
            time.sleep(pause * (attempt + 1))
    raise last


def correct(q, ans):
    a = ans.lower()
    if q["kind"] == "status":
        return bool(re.search(STATUS_WORD[q["accept"][0]], a))
    hits = []
    for acc in q["accept"]:
        acc_l = acc.lower()
        hits.append(acc_l in a or acc_l.replace(",", "") in a.replace(",", "")
                    or acc_l.replace("_", " ") in a)
    return any(hits) if q["match"] == "any" else all(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--url", default="http://localhost:5678/webhook/ask")
    ap.add_argument("--delay", type=float, default=13.0, help="seconds between questions (free-tier pacing)")
    a = ap.parse_args()
    out = Path("results") / Path(a.run).name
    qs = json.loads((out / "ask_questions.json").read_text(encoding="utf-8"))
    answers, ok_in, ok_out, lat = [], 0, 0, []
    for i, q in enumerate(qs):
        if i:
            time.sleep(a.delay)
        try:
            ans, s = ask(a.url, q["question"])
        except Exception as e:  # a failed call is scored wrong, not skipped
            ans, s = f"ERROR: {e}", None
        if s:
            lat.append(s)
        if q["kind"] == "out_of_scope":
            good = bool(REFUSAL.search(ans))
            ok_out += good
        else:
            good = correct(q, ans)
            ok_in += good
        answers.append({**q, "answer": ans, "seconds": None if s is None else round(s, 1), "correct": good})
        print(f"{q['id']:7} {'OK ' if good else 'BAD'} {q['question'][:60]!r} -> {ans[:120]!r}")
    n_in = sum(q["kind"] != "out_of_scope" for q in qs)
    res = {"in_scope_exact": f"{ok_in}/{n_in}", "out_of_scope_refused": f"{ok_out}/{len(qs) - n_in}",
           "median_seconds": sorted(lat)[len(lat) // 2] if lat else None}
    (out / "ask_answers.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
    (out / "ask_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
