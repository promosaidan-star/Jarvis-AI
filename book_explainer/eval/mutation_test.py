"""Guard recall by planted error (mutation test).

The 09-11 verified cards pass the guard cleanly, so real data alone cannot show
what the guard catches. Here each verified card gets ONE planted error of each
type; recall = share of planted errors the guard flags. Unmutated cards are the
false-positive baseline.

usage: python eval/mutation_test.py run_2026-09-11 [--out results/run_2026-09-11]
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from checks import expected_status, guard  # noqa: E402
from run_eval import load  # noqa: E402

STATUSES = ["still in decile", "faded toward middle", "flipped sign", "no row today"]


def _sub_first(pattern, repl, text):
    new, n = re.subn(pattern, repl, text, count=1)
    return new if n else None


def mutations(card, pos, bg):
    b = card["body"]
    out = {}
    out["percentile +9"] = _sub_first(r"\b(\d{1,2})(st|nd|rd|th) percentile",
                                      lambda m: f"{int(m.group(1)) + 9}th percentile", b)
    out["contribution +0.02"] = _sub_first(r"(?<![\d.])([-+]?)(0\.\d{3})(?!\d)",
                                           lambda m: f"{m.group(1)}{float(m.group(2)) + 0.02:.3f}", b)
    t = abs(round(pos["target_dollars"]))
    out["dollar target +$250"] = _sub_first(re.escape(f"${t:,}"), f"${t + 250:,}", b)
    z = pos["entry"]["agg_z"] if pos.get("entry") else None
    out["agg_z +0.40"] = None if z is None else _sub_first(re.escape(f"{abs(z):.2f}"), f"{abs(z) + 0.40:.2f}", b)
    out["date shifted"] = _sub_first(r"2026-09-(\d\d)", lambda m: f"2026-10-{m.group(1)}", b)
    ns = pos["entry"]["n_sources"] if pos.get("entry") else None
    words = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen".split()
    out["n_sources wrong"] = None if ns is None else b + f" {words[min(ns + 3, 16)].capitalize()} sources voted on this name."
    out["efficacy claim"] = b + " The aggregate predicts this name will outperform."
    news = bg.get("news", [])
    if news and "News context" in b:
        tt = news[0]["title"]
        out["fake headline"] = b + f' Also "{tt.split()[0]} Announces Surprise Merger With Rival Firm" ran.'
        out["causal news link"] = b + " That coverage explains the rank move."
    muts = {k: {**card, "body": v} for k, v in out.items() if v is not None and v != b}
    wrong = [s for s in STATUSES if s != expected_status(pos)][0]
    muts["status_today wrong"] = {**card, "status_today": wrong}
    if len(card.get("drivers", [])) >= 2:
        d = list(card["drivers"])
        d[0], d[1] = d[1], d[0]
        muts["drivers order swapped"] = {**card, "drivers": d}
    if card.get("dissenters"):
        muts["dissenter listed as driver"] = {**card, "drivers": card["drivers"] + [card["dissenters"][0]]}
    muts["headline > 20 words"] = {**card, "headline": card["headline"] + " " + " ".join(["extra"] * 15)}
    return muts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--out")
    a = ap.parse_args()
    run = Path(a.run)
    out = Path(a.out or Path("results") / run.name)
    out.mkdir(parents=True, exist_ok=True)
    glossary, rows = load(run)
    planted, caught, fp = collections.Counter(), collections.Counter(), 0
    for r in rows:
        card, pos = r["verified"], r["pos"]
        bg = glossary["backgrounds"].get(pos["symbol"], {})
        fp += bool(guard(card, pos, glossary, r["positions"]))
        for name, m in mutations(copy.deepcopy(card), pos, bg).items():
            planted[name] += 1
            caught[name] += bool(guard(m, pos, glossary, r["positions"]))
    res = {"clean_cards_flagged (false positives)": f"{fp}/{len(rows)}",
           "recall_by_mutation": {k: f"{caught[k]}/{planted[k]}" for k in planted},
           "overall_recall": f"{sum(caught.values())}/{sum(planted.values())}"}
    (out / "mutation_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
