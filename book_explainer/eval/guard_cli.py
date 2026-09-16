"""Guard CLI for the n8n Execute Command node.

usage: python eval/guard_cli.py <run_dir> <k> [--stage verified|draft]

Prints one JSON object: {"batch": k, "stage": ..., "cards": {SYMBOL: {"pass": bool,
"fails": [...], "company_fact_unsupported": [...]}}, "n_pass": int, "n": int}
Reads only <run_dir>/glossary.json, batch_k.json and draft_k.json / verified_k.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from checks import company_fact_check, guard  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("k", type=int)
    ap.add_argument("--stage", default="verified", choices=["verified", "draft"])
    a = ap.parse_args()
    run = Path(a.run_dir)
    glossary = json.loads((run / "glossary.json").read_text(encoding="utf-8"))
    positions = json.loads((run / f"batch_{a.k}.json").read_text(encoding="utf-8"))["positions"]
    if a.stage == "draft":
        cards = json.loads((run / f"draft_{a.k}.json").read_text(encoding="utf-8"))["explanations"]
    else:
        cards = [{"symbol": v["symbol"], "headline": v["corrected_headline"], "body": v["corrected_body"],
                  "drivers": v["drivers"], "dissenters": v["dissenters"], "status_today": v["status_today"]}
                 for v in json.loads((run / f"verified_{a.k}.json").read_text(encoding="utf-8"))["results"]]
    by_sym = {c["symbol"]: c for c in cards}
    out = {}
    for p in positions:
        c = by_sym.get(p["symbol"])
        if c is None:
            out[p["symbol"]] = {"pass": False, "fails": [{"check": "missing_card", "detail": ""}],
                                "company_fact_unsupported": []}
            continue
        fails = guard(c, p, glossary, positions)
        fact = company_fact_check(c, glossary["backgrounds"].get(p["symbol"], {}))
        out[p["symbol"]] = {"pass": not fails, "fails": fails, "company_fact_unsupported": fact["unsupported"]}
    print(json.dumps({"batch": a.k, "stage": a.stage, "cards": out,
                      "n_pass": sum(v["pass"] for v in out.values()), "n": len(out)}))


if __name__ == "__main__":
    main()
