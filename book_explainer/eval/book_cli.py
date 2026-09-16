"""Book payload for the front-end (n8n GET /book -> Execute Command -> this script).

usage: python eval/book_cli.py [run_dir]
  run_dir defaults to runs/LATEST.txt if present, else run_2026-09-11.

Prints one JSON object: asof, disclaimer, heartbeat strip, and one row per position
with the checked-against numbers, the verified card, verifier problems and the guard
verdict. Reads files only: no network, no prices, no account.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from checks import company_fact_check, guard  # noqa: E402
from run_eval import load  # noqa: E402

HEARTBEAT = Path("C:/Users/ajwal/Documents/AJ-Algo-Trader/data/logs/heartbeat.json")
DISCLAIMER = ("This agent explains a PAPER book. It does not trade, size or cancel orders, and nothing here "
              "is evidence the strategy works: the aggregate is an untested forward arm.")


def pick_run(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    latest = ROOT / "runs" / "LATEST.txt"
    if latest.exists():
        p = Path(latest.read_text(encoding="utf-8").strip())
        if (p / "verified_0.json").exists():
            return p
    return ROOT / "run_2026-09-11"


def heartbeat():
    if not HEARTBEAT.exists():
        return {"available": False}
    d = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
    return {"available": True, "run_at": d.get("run_at"), "n_stale": d.get("n_stale"),
            "sources": [{k: s.get(k) for k in ("source", "status", "newest_print", "age_days", "coverage_pct")}
                        for s in d.get("sources", [])]}


def main():
    run = pick_run(sys.argv[1] if len(sys.argv) > 1 else None)
    glossary, rows = load(run)
    labels = {k: v["label"] for k, v in glossary["signs"].items()}
    out = []
    for r in rows:
        p, card = r["pos"], r["verified"]
        sym = p["symbol"]
        e, lt = p.get("entry") or {}, p.get("latest")
        g = guard(card, p, glossary, r["positions"]) if card else [{"check": "missing_card", "detail": ""}]
        bg = glossary["backgrounds"].get(sym, {})
        out.append({
            "symbol": sym, "name": bg.get("name"), "sector": bg.get("sector"),
            "side": "long" if p["position"] > 0 else "short",
            "target_dollars": round(abs(p["target_dollars"])), "entry_date": p["entry_date"],
            "agg_z": round(e.get("agg_z", 0), 2), "n_sources": e.get("n_sources"),
            "entry_score": round(e.get("agg", 0), 3), "entry_pct": round(e.get("agg_pct", 0) * 100),
            "latest_score": None if not lt else round(lt["agg"], 3),
            "latest_pct": None if not lt else round(lt["agg_pct"] * 100),
            "votes": [{"source": v["source"], "label": labels.get(v["source"], v["label"]), "family": v["family"],
                       "pct": round(v["pct"] * 100), "sign": v["sign"], "fit": v["fit"],
                       "contribution": round(v["contribution"], 3)}
                      for v in sorted(e.get("votes", []), key=lambda v: -abs(v["contribution"]))],
            "history": [{"day": h["day"], "score": round(h["agg"], 3), "pct": round(h["agg_pct"] * 100)}
                        for h in p.get("history", [])],
            "news": bg.get("news", []),
            "card": card, "status_today": card["status_today"] if card else None,
            "verifier_ok": r["ok"], "verify_problems": r["problems"],
            "guard_pass": not g, "guard_fails": g,
            "company_fact_unsupported": company_fact_check(card, bg)["unsupported"] if card else [],
        })
    print(json.dumps({"asof": glossary["asof"], "run": run.name, "disclaimer": DISCLAIMER,
                      "refused_shorts": glossary.get("refused_shorts", []), "heartbeat": heartbeat(),
                      "positions": out}))


if __name__ == "__main__":
    main()
