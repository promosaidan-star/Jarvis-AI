# Book Explainer — n8n agent + evaluation

Turns a live systematic paper-trading book into a **traceable plain-English explanation
per position**, where every percentile, contribution and dollar figure is checked against
the source data before a human sees it. It is an explainability layer, **not** a trading
layer: it never submits, cancels or sizes an order, and the LLMs never see prices,
returns or the account.

- What it does and why: [`../ai_agent_n8n_brief.md`](../ai_agent_n8n_brief.md)
- Results: [`EVALUATION.md`](EVALUATION.md)
- Submission checklist: [`SUBMISSION.md`](SUBMISSION.md)

## Pipeline

```
agg_explain (deterministic, upstream)  ->  glossary.json + batch_k.json
        |
        v  n8n workflow "Book Explainer"
  Writer LLM  ->  Verifier LLM  ->  Deterministic Python guard  ->  explanations.json
        |
        +-> GET  /webhook/book    -> dashboard payload (Lovable front-end)
        +-> POST /webhook/explain -> one symbol or the whole book
        +-> POST /webhook/ask     -> grounded Q&A agent (tools: list_book, get_position)
```

## Run it

```bash
# 1. start the self-hosted n8n (free, localhost:5678); --tunnel for a public webhook URL
pwsh -File n8n/start_n8n.ps1
```

```bash
# 2. the whole book (about 110 s), or one symbol (about 5 s)
curl -s -X POST http://localhost:5678/webhook/explain -H "Content-Type: application/json" -d "{}"
curl -s -X POST http://localhost:5678/webhook/explain -H "Content-Type: application/json" -d "{\"symbol\":\"ABBV\"}"
```

```bash
# 3. the evaluation
python eval/run_eval.py run_2026-09-11      # metrics 1-3 over the reference run
python eval/mutation_test.py run_2026-09-11 # guard recall / false positives
python eval/score_ask.py run_2026-09-11     # Ask-the-book faithfulness (live webhook)
python eval/make_figures.py                 # figures + summary table
```

Run every Python command from this folder with `PYTHONIOENCODING=utf-8:replace`.

## Layout

| Path | What |
|---|---|
| `run_2026-09-11/` | reference run (Claude writer+verifier): glossary, batches, drafts, verified, prompts |
| `runs/` | n8n run outputs (`LATEST.txt` points at the newest) |
| `n8n/code/*.js` | the Code-node JavaScript, kept as files so it is diffable |
| `n8n/build_workflows.py` | assembles `n8n/workflows/*.json` (what gets imported and submitted) |
| `n8n/start_n8n.ps1` | the env n8n needs: file access to this folder, `fs` in Code nodes, Execute Command |
| `eval/checks.py` | the deterministic guard + company-fact check (single source of truth) |
| `eval/guard_cli.py` | guard as a CLI — the n8n Execute Command node calls this |
| `eval/book_cli.py` | builds the dashboard payload (`GET /book` calls this) |
| `eval/run_eval.py`, `mutation_test.py`, `ask_questions.py`, `score_ask.py`, `rating_packet.py` | the six evaluation metrics |
| `lovable/LOVABLE_PROMPT.md` | the prompt that builds the front-end, plus the data contract |
| `results/` | metrics, figures, book payloads, rating packet |

## Setup notes

- **Model.** The workflow calls `gemini-3.5-flash-lite` through a `googlePalmApi`
  credential named "Gemini (Book Explainer)". The exported workflow JSON contains **no
  key** — import it, then add the credential in the n8n UI. The design targets Claude;
  the project's Anthropic key is unfunded (see EVALUATION.md §Model note).
- **Free-tier limit.** 15 requests/minute. The whole-book run fits; scripted question
  batches pace themselves.
- **n8n 2.x.** `publish:workflow --id=<id>` (not `update:workflow --active`) plus a
  restart is what registers the webhooks.

## Safety properties (by construction)

1. The agent reads JSON files and writes JSON files. It has no order path, no broker
   client and no account credentials.
2. The LLM context contains the decomposition and company backgrounds only — no prices,
   no returns, no P&L, no positions beyond the dollar target being explained.
3. Every card ships with its checks attached: which claims the verifier corrected and
   which checks the guard failed. Failures are surfaced in the UI, never hidden.
4. Efficacy claims ("the aggregate predicts…") are forbidden in both prompts and flagged
   by the guard. The book is an untested forward arm and the UI says so permanently.
