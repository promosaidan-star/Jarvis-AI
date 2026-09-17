#!/usr/bin/env python3
"""Evaluation harness for the Daily Digest agent. Standard library only.

WORKFLOW
--------
1. Back-run the morning workflow over several past days and/or configs. After each run,
   copy the `action_items` cell from the Data Table (it is a JSON array) into:

       runs/<config>__<YYYY-MM-DD>.json

   Config names are yours; use them for the ablation, e.g.
       runs/A_original__2026-09-10.json     Carrie's original prose prompt
       runs/B_v3__2026-09-10.json           structured, with tools
       runs/C_v3_notools__2026-09-10.json   structured, tools disconnected

2. Build the labelling sheets:

       python3 eval.py sheet --runs runs --out labels.csv --missed missed.csv

3. TWO people label labels.csv independently (duplicate the file, one each, then
   concatenate — or fill the `labeller` column and append rows). While labelling,
   open the raw inbox for that day and add every action item the agent MISSED to
   missed.csv. That is what makes recall real.

4. Score:

       python3 eval.py score --labels labels.csv --missed missed.csv --out results.md

OTHER COMMANDS
--------------
    python3 eval.py reliability --runs runs --config B_v3 --date 2026-09-10
        Jaccard overlap across repeated runs of the same input (run it 3x, save as
        B_v3__2026-09-10.json, B_v3__2026-09-10__r2.json, ...).

    python3 eval.py confusion --file evening_labels.csv --out evening.md
        4-class confusion matrix for the evening classifier. CSV needs columns
        item_id,predicted,actual with values completed|in_progress|blocked|no_progress.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ITEM_FIELDS = ["item_id", "task", "source", "source_ref", "who", "due", "priority"]
LABEL_FIELDS = ["label_is_action", "label_priority", "label_source_ok", "labeller", "notes"]
STATUSES = ["completed", "in_progress", "blocked", "no_progress"]


# --------------------------------------------------------------------- loading
def load_runs(runs_dir: Path) -> list[dict]:
    """Each file is `<config>__<date>[__tag].json` holding a JSON array of items,
    or an object with an `items` key. Returns flat rows."""
    rows = []
    files = sorted(runs_dir.glob("*.json"))
    if not files:
        sys.exit(f"no .json files in {runs_dir}/ — see the docstring at the top of this file")

    for f in files:
        stem = f.stem
        if "__" not in stem:
            print(f"  ! skipping {f.name}: expected <config>__<date>.json", file=sys.stderr)
            continue
        parts = stem.split("__")
        config, date = parts[0], parts[1]
        tag = parts[2] if len(parts) > 2 else "r1"

        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  ! {f.name} is not valid JSON ({e}) — paste the whole cell including [ ]",
                  file=sys.stderr)
            continue

        items = data.get("items", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            print(f"  ! {f.name}: expected a list of items", file=sys.stderr)
            continue

        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            row = {"config": config, "digest_date": date, "run_tag": tag}
            row.update({k: it.get(k, "") for k in ITEM_FIELDS})
            if not row["item_id"]:
                row["item_id"] = f"{date}-{i + 1:02d}"
            rows.append(row)
        print(f"  loaded {len(items):>3} items  {config} / {date} / {tag}")
    return rows


def read_csv(path: Path) -> list[dict]:
    if not path or not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if any((v or "").strip() for v in r.values())]


# ----------------------------------------------------------------------- sheet
def cmd_sheet(args):
    rows = load_runs(Path(args.runs))
    out = Path(args.out)
    cols = ["config", "digest_date", "run_tag"] + ITEM_FIELDS + LABEL_FIELDS
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({**r, **{k: "" for k in LABEL_FIELDS}})

    missed = Path(args.missed)
    if missed.exists():
        print(f"\n{missed} already exists — leaving it alone")
    else:
        with missed.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["config", "digest_date", "missed_task", "source",
                        "should_have_been_priority", "labeller", "notes"])
        print(f"\nwrote {missed} (empty — add one row per action item the agent MISSED)")

    print(f"wrote {out}  ({len(rows)} items to label)")
    print("\nFill in, per row:")
    print("  label_is_action   1 if it is a genuine action item for this person, else 0")
    print("  label_priority    high / normal / low — what it SHOULD have been")
    print("  label_source_ok   1 if source_ref really appears in the original message, else 0")
    print("  labeller          your initials (two people, independently)")


# ----------------------------------------------------------------------- score
def _f(v, default=None):
    v = (v or "").strip()
    return v if v else default


def _prf(tp: int, fp: int, fn: int):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """pairs of (rater A label, rater B label)."""
    if not pairs:
        return None
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    a_counts, b_counts = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    labels = set(a_counts) | set(b_counts)
    pe = sum((a_counts[l] / n) * (b_counts[l] / n) for l in labels)
    return (po - pe) / (1 - pe) if pe != 1 else 1.0


def cmd_score(args):
    labels = read_csv(Path(args.labels))
    missed = read_csv(Path(args.missed)) if args.missed else []
    if not labels:
        sys.exit(f"{args.labels} has no rows")

    unlabelled = [r for r in labels if _f(r.get("label_is_action")) is None]
    if unlabelled:
        print(f"WARNING: {len(unlabelled)} of {len(labels)} rows have no label_is_action "
              f"— they are ignored below", file=sys.stderr)

    done = [r for r in labels if _f(r.get("label_is_action")) in ("0", "1")]

    # Repeat runs (r2, r3...) exist for the reliability check only — counting them here
    # would inflate whichever config you happened to re-run.
    if not args.include_repeats:
        repeats = [r for r in done if _f(r.get("run_tag"), "r1") != "r1"]
        if repeats:
            print(f"note: excluding {len(repeats)} rows from repeat runs "
                  f"(use --include-repeats to keep them)", file=sys.stderr)
        done = [r for r in done if _f(r.get("run_tag"), "r1") == "r1"]
    missed_by_cfg = Counter((r["config"], r["digest_date"]) for r in missed)

    # ---- per-config metrics (the ablation table)
    by_cfg = defaultdict(list)
    for r in done:
        by_cfg[r["config"]].append(r)

    lines = ["# Daily Digest — evaluation results", ""]
    dates = sorted({r["digest_date"] for r in done})
    labellers = sorted({_f(r.get("labeller"), "?") for r in done})
    lines += [f"Mornings evaluated: **{len(dates)}** ({', '.join(dates)})  ",
              f"Items labelled: **{len(done)}**  ",
              f"Labellers: **{', '.join(labellers)}**", ""]

    lines += ["## Extraction quality by configuration", "",
              "| Config | Items | True | False | Precision | Missed | Recall | F1 | Priority acc. | Attribution |",
              "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]

    for cfg in sorted(by_cfg):
        rows = by_cfg[cfg]
        tp = sum(1 for r in rows if r["label_is_action"].strip() == "1")
        fp = sum(1 for r in rows if r["label_is_action"].strip() == "0")
        fn = sum(v for (c, _d), v in missed_by_cfg.items() if c == cfg)
        p, rec, f1 = _prf(tp, fp, fn)

        true_rows = [r for r in rows if r["label_is_action"].strip() == "1"]
        pri_scored = [r for r in true_rows if _f(r.get("label_priority"))]
        pri_ok = sum(1 for r in pri_scored
                     if r["priority"].strip().lower() == r["label_priority"].strip().lower())
        pri = f"{pri_ok / len(pri_scored):.2f}" if pri_scored else "—"

        att_scored = [r for r in rows if _f(r.get("label_source_ok")) in ("0", "1")]
        att_ok = sum(1 for r in att_scored if r["label_source_ok"].strip() == "1")
        att = f"{att_ok / len(att_scored):.2f}" if att_scored else "—"

        lines.append(f"| {cfg} | {len(rows)} | {tp} | {fp} | {p:.2f} | {fn} | {rec:.2f} | "
                     f"{f1:.2f} | {pri} | {att} |")

    lines += ["", "_Precision = of what it surfaced, how much was a real action item. "
                  "Recall = of the real action items in that inbox, how many it found "
                  "(denominator includes the misses logged by hand). "
                  "Attribution = did `source_ref` really appear in the original message._", ""]

    # ---- inter-rater agreement (the human ceiling)
    seen = defaultdict(dict)
    for r in done:
        who = _f(r.get("labeller"), "?")
        seen[(r["config"], r["digest_date"], r["item_id"])][who] = r["label_is_action"].strip()

    pairs = []
    for _key, per_labeller in seen.items():
        if len(per_labeller) >= 2:
            vals = list(per_labeller.values())[:2]
            pairs.append((vals[0], vals[1]))

    lines += ["## Inter-rater agreement (your human ceiling)", ""]
    if pairs:
        agree = sum(1 for a, b in pairs if a == b) / len(pairs)
        k = cohens_kappa(pairs)
        lines += [f"- Items labelled independently by two people: **{len(pairs)}**",
                  f"- Raw agreement on *is this an action item*: **{agree:.2f}**",
                  f"- Cohen's kappa: **{k:.2f}**" if k is not None else "- Cohen's kappa: n/a",
                  "",
                  "_Two people do not agree perfectly either. Read the agent's precision "
                  "against this number, not against 1.00._", ""]
    else:
        lines += ["_No item was labelled by two people — fill the `labeller` column on two "
                  "passes to get this. It is worth the twenty minutes._", ""]

    # ---- what it missed
    lines += ["## What it missed", ""]
    if missed:
        lines += ["| Config | Date | Missed item | Source | Should have been |",
                  "|---|---|---|---|---|"]
        for m in missed[:30]:
            lines.append(f"| {m.get('config','')} | {m.get('digest_date','')} | "
                         f"{m.get('missed_task','')} | {m.get('source','')} | "
                         f"{m.get('should_have_been_priority','')} |")
        lines.append("")
    else:
        lines += ["_Nothing logged in the missed sheet. If that is genuinely true, say so "
                  "out loud in the video — a recall of 1.00 with no misses logged reads as "
                  "an unchecked claim._", ""]

    out = Path(args.out)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {out}", file=sys.stderr)


# ----------------------------------------------------------------- reliability
def cmd_reliability(args):
    rows = load_runs(Path(args.runs))
    sel = [r for r in rows if r["config"] == args.config and r["digest_date"] == args.date]
    if not sel:
        sys.exit(f"no rows for config={args.config} date={args.date}")

    by_run = defaultdict(set)
    for r in sel:
        by_run[r["run_tag"]].add(r["task"].strip().lower())

    tags = sorted(by_run)
    if len(tags) < 2:
        sys.exit(f"only one run ({tags[0]}) — save repeats as "
                 f"{args.config}__{args.date}__r2.json etc.")

    print(f"\nReliability across {len(tags)} runs of {args.config} on {args.date}\n")
    print(f"{'':>6} " + " ".join(f"{t:>6}" for t in tags))
    for a in tags:
        cells = []
        for b in tags:
            inter = len(by_run[a] & by_run[b])
            union = len(by_run[a] | by_run[b])
            cells.append(f"{inter / union:>6.2f}" if union else f"{'—':>6}")
        print(f"{a:>6} " + " ".join(cells))

    common = set.intersection(*by_run.values())
    everything = set.union(*by_run.values())
    print(f"\nItems per run: {', '.join(f'{t}={len(by_run[t])}' for t in tags)}")
    print(f"In every run: {len(common)} of {len(everything)} distinct items "
          f"({len(common) / len(everything):.2f})")
    print("\nStable across runs:")
    for t in sorted(common):
        print(f"  = {t}")
    unstable = everything - common
    if unstable:
        print("Appeared in some runs only:")
        for t in sorted(unstable):
            where = ",".join(tag for tag in tags if t in by_run[tag])
            print(f"  ~ {t}   [{where}]")


# ------------------------------------------------------------------ confusion
def cmd_confusion(args):
    rows = read_csv(Path(args.file))
    rows = [r for r in rows if _f(r.get("predicted")) and _f(r.get("actual"))]
    if not rows:
        sys.exit(f"{args.file} needs columns item_id,predicted,actual")

    cm = defaultdict(Counter)
    for r in rows:
        cm[r["actual"].strip()][r["predicted"].strip()] += 1

    w = max(len(s) for s in STATUSES) + 2
    lines = ["# Evening classifier — confusion matrix", "",
             f"n = {len(rows)} items across {len({r.get('digest_date','') for r in rows})} day(s)",
             "", "| actual \\ predicted | " + " | ".join(STATUSES) + " | total |",
             "|---" * (len(STATUSES) + 2) + "|"]
    correct = 0
    for a in STATUSES:
        row = [f"| **{a}** "]
        for p in STATUSES:
            n = cm[a][p]
            if a == p:
                correct += n
                row.append(f"| **{n}** ")
            else:
                row.append(f"| {n} ")
        row.append(f"| {sum(cm[a].values())} |")
        lines.append("".join(row))
    lines += ["", f"**Overall accuracy: {correct / len(rows):.2f}**", ""]

    for s in STATUSES:
        tp = cm[s][s]
        fp = sum(cm[a][s] for a in STATUSES if a != s)
        fn = sum(cm[s][p] for p in STATUSES if p != s)
        p, r, f1 = _prf(tp, fp, fn)
        lines.append(f"- `{s}`: precision {p:.2f}, recall {r:.2f}, F1 {f1:.2f}")

    lines += ["", "_The row that matters is `completed`: a false `completed` is the agent "
                  "telling you something is done when it is not, which is the failure that "
                  "would stop someone trusting it._"]

    out = Path(args.out)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {out}", file=sys.stderr)
    _ = w


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sheet", help="build the labelling CSVs from runs/")
    s.add_argument("--runs", default="runs")
    s.add_argument("--out", default="labels.csv")
    s.add_argument("--missed", default="missed.csv")
    s.set_defaults(func=cmd_sheet)

    s = sub.add_parser("score", help="metrics + ablation table from labelled CSVs")
    s.add_argument("--labels", default="labels.csv")
    s.add_argument("--missed", default="missed.csv")
    s.add_argument("--out", default="results.md")
    s.add_argument("--include-repeats", action="store_true",
                   help="also count r2/r3 reliability runs in the ablation (normally wrong)")
    s.set_defaults(func=cmd_score)

    s = sub.add_parser("reliability", help="overlap across repeated runs of one input")
    s.add_argument("--runs", default="runs")
    s.add_argument("--config", required=True)
    s.add_argument("--date", required=True)
    s.set_defaults(func=cmd_reliability)

    s = sub.add_parser("confusion", help="4-class matrix for the evening classifier")
    s.add_argument("--file", default="evening_labels.csv")
    s.add_argument("--out", default="evening.md")
    s.set_defaults(func=cmd_confusion)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
