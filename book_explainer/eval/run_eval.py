"""Evaluation metrics 1-3 over a completed writer->verifier run.

usage: python eval/run_eval.py run_2026-09-11 [--out results/run_2026-09-11]

Reads <run>/batch_k.json, draft_k.json, verified_k.json, glossary.json.
Writes eval_results.json, cards.csv and a plain-English summary.md.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from checks import company_fact_check, guard, news_checks  # noqa: E402

# Problem taxonomy: first matching rule wins. Order matters (specific before generic).
TAXONOMY = [
    ("unsupported company fact", r"company (fact|description)|not in (the )?(glossary\.)?background|business lines|opening company sentence"),
    ("headline/quote fidelity", r"truncat|restored the full title|headline .*not in"),
    ("efficacy claim", r"predict|edge|works\b"),
    ("count wrong", r"vote count|source count|nine of|seven sources|two of the four|only (seven|two)|three (did|votes|fin)|implied only|wrong three ways"),
    ("ranking/ordering wrong", r"largest|loudest|third|bigger than|smaller than|larger|biggest|superlative|quietest"),
    ("direction word wrong", r"inside|above|below|cancel|opposite|direction|reads backwards|pointing"),
    ("magnitude/arithmetic wrong", r"halved|almost all|about half|\d+%"),
    ("history/timeline wrong", r"history|through late|one day old|entry was today"),
    ("source mislabelled", r"mislabel|fitted|bi-weekly|daily short-volume|attention source|mood leg"),
]


def classify(problem: str) -> str:
    for name, pat in TAXONOMY:
        if re.search(pat, problem, re.I):
            return name
    return "other"


def load(run: Path):
    glossary = json.loads((run / "glossary.json").read_text(encoding="utf-8"))
    rows = []
    for k in range(100):
        bf = run / f"batch_{k}.json"
        if not bf.exists():
            break
        positions = json.loads(bf.read_text(encoding="utf-8"))["positions"]
        drafts = {d["symbol"]: d for d in json.loads((run / f"draft_{k}.json").read_text(encoding="utf-8"))["explanations"]}
        vf = run / f"verified_{k}.json"
        verified = {v["symbol"]: v for v in json.loads(vf.read_text(encoding="utf-8"))["results"]} if vf.exists() else {}
        for p in positions:
            v = verified.get(p["symbol"])
            vcard = None if v is None else {
                "symbol": p["symbol"], "headline": v["corrected_headline"], "body": v["corrected_body"],
                "drivers": v["drivers"], "dissenters": v["dissenters"], "status_today": v["status_today"]}
            rows.append({"batch": k, "pos": p, "positions": positions, "draft": drafts.get(p["symbol"]),
                         "verified": vcard, "ok": None if v is None else v["ok"],
                         "problems": [] if v is None else v["problems"]})
    return glossary, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--out")
    a = ap.parse_args()
    run = Path(a.run)
    out = Path(a.out or Path("results") / run.name)
    out.mkdir(parents=True, exist_ok=True)
    glossary, rows = load(run)
    bgs = glossary["backgrounds"]

    n = len(rows)
    corrected = [r for r in rows if r["ok"] is False]
    per_batch = collections.Counter(r["batch"] for r in corrected)
    problems = [(r["pos"]["symbol"], p, classify(p)) for r in rows for p in r["problems"]]
    tax = collections.Counter(c for _, _, c in problems)

    card_rows, guard_draft, guard_ver = [], collections.Counter(), collections.Counter()
    hall = {"draft": {"news_ok": 0, "fact_ok": 0}, "verified": {"news_ok": 0, "fact_ok": 0}}
    for r in rows:
        sym, bg = r["pos"]["symbol"], bgs.get(r["pos"]["symbol"], {})
        rec = {"symbol": sym, "batch": r["batch"], "verifier_ok": r["ok"], "n_problems": len(r["problems"]),
               "problem_types": "|".join(sorted({classify(p) for p in r["problems"]}))}
        for stage in ("draft", "verified"):
            card = r[stage]
            if card is None:
                continue
            g = guard(card, r["pos"], glossary, r["positions"])
            (guard_draft if stage == "draft" else guard_ver).update(x["check"] for x in g)
            nc = [x for x in g if x["check"].startswith("headline_") and x["check"] != "headline_length"]
            fc = company_fact_check(card, bg)
            hall[stage]["news_ok"] += not nc
            hall[stage]["fact_ok"] += not fc["unsupported"]
            rec[f"{stage}_guard_fails"] = len(g)
            rec[f"{stage}_guard_detail"] = "; ".join(f"{x['check']}:{x['detail']}" for x in g)
            rec[f"{stage}_fact_unsupported"] = " ".join(fc["unsupported"])
        card_rows.append(rec)

    ver_fail_cards = sum(1 for c in card_rows if c.get("verified_guard_fails"))
    draft_fail_cards = sum(1 for c in card_rows if c.get("draft_guard_fails"))
    res = {
        "run": run.name, "positions": n,
        "metric1_draft_error_rate": {"corrected": len(corrected), "rate": round(len(corrected) / n, 4),
                                     "per_batch": dict(sorted(per_batch.items())),
                                     "problems_total": len(problems), "taxonomy": dict(tax.most_common())},
        "metric2_guard": {"draft_cards_flagged": draft_fail_cards, "verified_cards_flagged": ver_fail_cards,
                          "draft_flags_by_check": dict(guard_draft.most_common()),
                          "verified_flags_by_check": dict(guard_ver.most_common())},
        "metric3_hallucination": {s: {"news_quote_pass": f"{v['news_ok']}/{n}", "company_fact_pass": f"{v['fact_ok']}/{n}"}
                                  for s, v in hall.items()},
    }
    (out / "eval_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    with open(out / "problems_labelled.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "category", "problem"])
        w.writerows((s, c, p) for s, p, c in problems)
    with open(out / "cards.csv", "w", newline="", encoding="utf-8") as f:
        keys = sorted({k for c in card_rows for k in c}, key=lambda k: list(card_rows[0]).index(k) if k in card_rows[0] else 99)
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(card_rows)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
