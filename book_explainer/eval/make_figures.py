"""Figures for the evaluation write-up.

usage: python eval/make_figures.py
reads results/run_2026-09-11/*.json + results/explain_full_gemini.json
writes results/figures/fig1..fig5.png and results/figures/summary_table.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from checks import guard  # noqa: E402
from run_eval import load  # noqa: E402

R = Path("results")
RUN = R / "run_2026-09-11"
FIG = R / "figures"
INK, GOOD, BAD, MID = "#1f2a36", "#2f7d5c", "#b23a48", "#8a94a6"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK, "ytick.color": INK,
                     "figure.facecolor": "white", "axes.titlesize": 12, "font.size": 10})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / name)


def gemini_guard_counts():
    """Guard verdicts on the n8n/Gemini run, by check."""
    glossary, rows = load(Path(json.loads((R / "explain_full_gemini.json").read_text(encoding="utf-8"))["metrics"]["outDir"]))
    flagged, by_check = 0, {}
    for r in rows:
        f = guard(r["verified"], r["pos"], glossary, r["positions"])
        flagged += bool(f)
        for x in f:
            by_check[x["check"]] = by_check.get(x["check"], 0) + 1
    return len(rows), flagged, by_check


def main():
    res = json.loads((RUN / "eval_results.json").read_text(encoding="utf-8"))
    mut = json.loads((RUN / "mutation_results.json").read_text(encoding="utf-8"))
    gem = json.loads((R / "explain_full_gemini.json").read_text(encoding="utf-8"))["metrics"]
    n_gem, gem_flagged, gem_checks = gemini_guard_counts()

    # Fig 1 - what the verifier corrected, by error type
    tax = res["metric1_draft_error_rate"]["taxonomy"]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ks = list(tax)[::-1]
    ax.barh(ks, [tax[k] for k in ks], color=BAD)
    for i, k in enumerate(ks):
        ax.text(tax[k] + 0.12, i, str(tax[k]), va="center", fontsize=9)
    ax.set_title(f"What the second LLM had to fix: {res['metric1_draft_error_rate']['problems_total']} corrections "
                 f"in {res['metric1_draft_error_rate']['corrected']} of {res['positions']} cards")
    ax.set_xlabel("corrections")
    ax.set_xlim(0, max(tax.values()) + 1)
    save(fig, "fig1_error_taxonomy.png")

    # Fig 2 - who catches what: two verifier models, same prompts, same 45 positions
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    labels = ["Cards the verifier\ncorrected", "Cards the Python guard\nstill flags"]
    claude = [res["metric1_draft_error_rate"]["corrected"], res["metric2_guard"]["verified_cards_flagged"]]
    gemini = [gem["corrected_by_verifier"], gem_flagged]
    x = range(len(labels))
    ax.bar([i - 0.2 for i in x], claude, 0.38, label="Claude writer+verifier (09-11 run)", color=INK)
    ax.bar([i + 0.2 for i in x], gemini, 0.38, label="Gemini writer+verifier (n8n run)", color=MID)
    for i, (a, b) in enumerate(zip(claude, gemini)):
        ax.text(i - 0.2, a + 0.4, f"{a}/45", ha="center", fontsize=9)
        ax.text(i + 0.2, b + 0.4, f"{b}/45", ha="center", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("cards (of 45)")
    ax.set_ylim(0, 48)
    ax.set_title("A weak verifier passes everything - the deterministic guard does not")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "fig2_verifier_vs_guard.png")

    # Fig 3 - guard recall by planted error
    rec = mut["recall_by_mutation"]
    ks = sorted(rec, key=lambda k: int(rec[k].split("/")[0]) / int(rec[k].split("/")[1]))
    vals = [100 * int(rec[k].split("/")[0]) / int(rec[k].split("/")[1]) for k in ks]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.barh(ks, vals, color=[GOOD if v >= 85 else (MID if v >= 60 else BAD) for v in vals])
    for i, v in enumerate(vals):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=9)
    ax.set_xlim(0, 108)
    ax.set_xlabel("planted errors caught (%)")
    ax.set_title(f"Guard recall on planted errors ({mut['overall_recall']} overall); "
                 f"false positives on clean cards: {mut['clean_cards_flagged (false positives)']}")
    save(fig, "fig3_guard_recall.png")

    # Fig 4 - what the guard flagged on the Gemini run, by check
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ks = sorted(gem_checks, key=gem_checks.get)
    ax.barh(ks, [gem_checks[k] for k in ks], color=BAD)
    for i, k in enumerate(ks):
        ax.text(gem_checks[k] + 0.1, i, str(gem_checks[k]), va="center", fontsize=9)
    ax.set_xlabel("flags")
    ax.set_title(f"Guard flags on the n8n/Gemini run: {gem_flagged} of {n_gem} cards, "
                 f"{sum(gem_checks.values())} flags")
    save(fig, "fig4_gemini_guard_flags.png")

    # Fig 5 - hallucination pass rates, before and after the verifier
    h = res["metric3_hallucination"]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    cats = ["Quoted headline\nexists verbatim", "Company sentence\nfully supported"]
    pre = [int(h["draft"]["news_quote_pass"].split("/")[0]), int(h["draft"]["company_fact_pass"].split("/")[0])]
    post = [int(h["verified"]["news_quote_pass"].split("/")[0]), int(h["verified"]["company_fact_pass"].split("/")[0])]
    x = range(2)
    ax.bar([i - 0.2 for i in x], pre, 0.38, label="writer draft", color=MID)
    ax.bar([i + 0.2 for i in x], post, 0.38, label="after verifier", color=GOOD)
    for i, (a, b) in enumerate(zip(pre, post)):
        ax.text(i - 0.2, a + 0.4, f"{a}/45", ha="center", fontsize=9)
        ax.text(i + 0.2, b + 0.4, f"{b}/45", ha="center", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats)
    ax.set_ylim(0, 50)
    ax.set_ylabel("cards passing (of 45)")
    ax.set_title("Grounding checks, before and after the verifier")
    ax.legend(frameon=False, fontsize=9)
    save(fig, "fig5_hallucination.png")

    # Summary table
    ask = json.loads((RUN / "ask_results.json").read_text(encoding="utf-8")) if (RUN / "ask_results.json").exists() else {}
    rows_md = [
        "| Metric | Result |", "|---|---|",
        f"| Positions explained (one n8n run) | {gem['positions']} |",
        f"| Draft cards the Claude verifier corrected | {res['metric1_draft_error_rate']['corrected']}/45 "
        f"({res['metric1_draft_error_rate']['rate']:.0%}), {res['metric1_draft_error_rate']['problems_total']} distinct corrections |",
        f"| Draft cards the Gemini verifier corrected | {gem['corrected_by_verifier']}/45 |",
        f"| Cards the deterministic guard flags after verification (Claude run) | {res['metric2_guard']['verified_cards_flagged']}/45 |",
        f"| Cards the deterministic guard flags after verification (Gemini run) | {gem_flagged}/45 |",
        f"| Guard recall on planted errors | {mut['overall_recall']} ({100 * eval(mut['overall_recall']):.0f}%) |",
        f"| Guard false positives on clean cards | {mut['clean_cards_flagged (false positives)']} |",
        f"| Quoted headline exists verbatim (draft -> verified) | {h['draft']['news_quote_pass']} -> {h['verified']['news_quote_pass']} |",
        f"| Company sentence fully supported (draft -> verified) | {h['draft']['company_fact_pass']} -> {h['verified']['company_fact_pass']} |",
        f"| Tokens per position (writer + verifier) | {gem['per_position']['tokens_in']:,} in, {gem['per_position']['tokens_out']:,} out |",
        f"| Seconds per position (LLM time) | {gem['per_position']['seconds']} |",
        f"| Whole book, wall clock | {gem['seconds_llm']:.0f} s of LLM time over {len(gem['batches'])} batches |",
    ]
    if ask:
        rows_md += [f"| Ask-the-book exact answers | {ask['in_scope_exact']} |",
                    f"| Ask-the-book out-of-scope refused | {ask['out_of_scope_refused']} |"]
    (FIG / "summary_table.md").write_text("\n".join(rows_md), encoding="utf-8")
    print("\n".join(rows_md))


if __name__ == "__main__":
    main()
