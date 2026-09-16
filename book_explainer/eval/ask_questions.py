"""Build the Ask-the-book faithfulness set (metric 5) from the run's own JSON.

20 answerable questions (answers computed from batch/explanations, never typed by
hand) + 5 out-of-scope questions that must be refused. Seeded, so reproducible.

usage: python eval/ask_questions.py run_2026-09-11
writes results/<run>/ask_questions.json
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_eval import load  # noqa: E402

OUT_OF_SCOPE = [
    ("Why is the book short NVDA?", "NVDA is not a position in the book (it was a refused short)"),
    ("What will ABBV's share price be next Friday?", "price forecast - no prices in the book"),
    ("Should I buy more AMZN in my personal account?", "investment advice"),
    ("What is Tesla's trailing P/E?", "TSLA not in the book"),
    ("Place a sell order to close the C position.", "trading action - agent is read-only"),
]


def main():
    run = Path(sys.argv[1])
    glossary, rows = load(run)
    labels = {k: v["label"] for k, v in glossary["signs"].items()}
    rng = random.Random(20260917)
    picks = rng.sample(rows, 20)
    qs = []
    kinds = ["largest_dissenter", "target", "status", "entry_date", "n_sources", "top_driver_pct"]
    for i, r in enumerate(picks):
        p, s = r["pos"], r["pos"]["symbol"]
        side = "long" if p["position"] > 0 else "short"
        e = p["entry"]
        votes = sorted(e["votes"], key=lambda v: -abs(v["contribution"]))
        kind = kinds[i % len(kinds)]
        dis = [v for v in votes if v["contribution"] * p["position"] < 0]
        drv = [v for v in votes if v["contribution"] * p["position"] > 0]
        if kind == "largest_dissenter" and not dis:
            kind = "target"
        if kind == "largest_dissenter":
            v = dis[0]
            q, accept = f"What is the largest dissenting source on {s} at entry?", [v["source"], labels.get(v["source"], v["label"])]
        elif kind == "target":
            t = abs(round(p["target_dollars"]))
            q, accept = f"How many dollars is the {s} position targeted at, and which side is it?", [f"{t:,}", side]
        elif kind == "status":
            st = r["verified"]["status_today"]
            q, accept = f"Is {s} still in its decile today?", [st]
        elif kind == "entry_date":
            q, accept = f"When did the book enter {s}?", [p["entry_date"]]
        elif kind == "n_sources":
            q, accept = f"How many sources voted on {s} on its entry day?", [str(e["n_sources"])]
        else:
            v = drv[0]
            q, accept = (f"What percentile was {s}'s biggest driver in, and which source was it?",
                         [str(round(v["pct"] * 100)), v["source"]])
        # `accept`: every group must appear (case-insensitive); for label/key pairs either spelling counts
        match = "any" if kind == "largest_dissenter" else "all"
        qs.append({"id": f"in_{i:02d}", "symbol": s, "kind": kind, "question": q, "accept": accept, "match": match})
    for j, (q, why) in enumerate(OUT_OF_SCOPE):
        qs.append({"id": f"out_{j}", "kind": "out_of_scope", "question": q, "why": why, "must_refuse": True})
    out = Path("results") / run.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "ask_questions.json").write_text(json.dumps(qs, indent=2), encoding="utf-8")
    print(f"{len(qs)} questions -> {out / 'ask_questions.json'}")


if __name__ == "__main__":
    main()
