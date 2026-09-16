# Submission checklist and video script — Book Explainer

Due **Wednesday 2026-09-17**. Deliverables: 8-minute video, n8n workflow export,
front-end screenshots, evaluation folder.

## Checklist

| # | Item | State | Where |
|---|---|---|---|
| 1 | n8n workflow JSON export (3 workflows, no credentials inside) | done | `n8n/workflows/*.json` |
| 2 | Working back end: writer → verifier → deterministic guard | done, ran the full 45-position book | `results/explain_full_gemini.json` |
| 3 | Second tool: grounded Q&A agent | done | `POST /webhook/ask` |
| 4 | Evaluation: draft error rate + taxonomy | done | `EVALUATION.md` §1 |
| 5 | Evaluation: verifier recall vs deterministic guard | done | §2 |
| 6 | Evaluation: guard recall / false positives (mutation test) | done | §3 |
| 7 | Evaluation: hallucination checks | done | §4 |
| 8 | Evaluation: Ask-the-book faithfulness | done | §5 |
| 9 | Evaluation: cost and latency | done | §6 |
| 10 | Human rating by 3 teammates | **packet built, needs raters** | `results/run_2026-09-11/rating/rating_sheet.xlsx` |
| 11 | Lovable front end | **needs AJ's Lovable account** | `lovable/LOVABLE_PROMPT.md` |
| 12 | Screenshots of the front end | after 11 | — |
| 13 | 8-minute video | after 11-12 | script below |

## The three things only AJ can do

0. **Create the local n8n owner account** (30 seconds, needed before the canvas is
   visible for the video and screenshots). n8n is already running and the webhooks
   already work headlessly — this is only the UI login. Open http://localhost:5678,
   fill in the "Set up owner account" form with any email and password you keep, then
   open the three workflows to screenshot the canvas. I don't create accounts or type
   passwords, so this one is yours.
1. **Lovable.** Open lovable.dev, new project, paste `lovable/LOVABLE_PROMPT.md`
   (everything between the `---` lines). Then either point it at the n8n tunnel URL, or
   use the "Load JSON file" button with `results/book_n8n_gemini.json`.
   For a public webhook URL: `pwsh -File n8n/start_n8n.ps1 --tunnel`.
2. **Human rating.** Send `rating_sheet.xlsx` to the two teammates, fill one tab each
   (about 25 minutes), then `python eval/rating_packet.py score run_2026-09-11`.
   Do not open `KEY_do_not_open.json` before rating — it says which cards were corrected.

## Video script (8 minutes)

**0:00–2:00 — The problem.** A systematic desk holds 45 positions chosen by code. At 9:31
a risk officer asks "why are we short Citigroup?" and the honest answer is a parquet file.
Show the raw decomposition JSON on screen: 106 names, 14 sources, a contribution per
source. Say the cost in one line: unexplainable positions get cut at the wrong time, model
risk reviews stall, and every number a human retypes into a memo is a chance to be wrong.
State the design rule up front: the agent explains, it never trades.

**2:00–4:00 — The n8n back end.** Walk the "Book Explainer" canvas left to right:
webhook/manual trigger → Load run (Code) → loop over batches → **Writer LLM** → **Verifier
LLM** → **deterministic Python guard** (Execute Command) → merge → respond. Say what goes
into the model: glossary + batch JSON only, no prices, no returns, no account. Open one
execution and show the guard's JSON verdict attached to a card. Then show the second
workflow, "Ask the book": an agent with two tools (`list_book`, `get_position`) and a
system prompt that forbids outside facts.

**4:00–6:00 — The front end.** Load the dashboard. Book table → click Citigroup → the
explanation card next to the numbers it was checked against: each source's percentile,
its contribution, whether its sign is fitted or declared, and the score's path since
entry. Point at the two badges on the row ("Verifier: corrected", "Guard: 1 flag") and say
the system publishes its own failures. Then the chat box: ask "What is the largest
dissenter on ABT?" (correct, sourced), then ask "Should I buy more AMZN?" and show the
refusal. Point at the health strip: one stale source, named.

**6:00–8:00 — The evaluation.** Four numbers, in this order:
1. A single LLM is not good enough: the Claude verifier corrected **20 of 45 cards** and
   made **29 corrections** — mostly counts, orderings and direction words, not typos
   (fig 1).
2. An LLM verifier is not enough either: swap in the cheaper model and it corrected
   **0 of 45**, while the deterministic guard flagged **20 of 45** — nine wrong decile
   labels, six direction errors, nine cards with broken escape characters (fig 2, fig 4).
3. The guard itself was measured, not assumed: **528 of 585 planted errors caught (90%),
   0 false positives on 45 clean cards** — and its blind spots are stated (fig 3).
4. It is deployable: about **9,300 input tokens and 7.7 seconds per position**; one
   symbol end-to-end in under 5 seconds.
Close on the limitation slide: one day, 45 positions, no claim that the strategy works —
this measures explanation fidelity, not P&L.

## Recording notes

- Start n8n before recording (`pwsh -File n8n/start_n8n.ps1`); confirm
  `curl http://localhost:5678/webhook/book` returns JSON.
- The free Gemini tier allows 15 requests/minute. Don't run the whole book and the chat
  demo back to back on camera; run the book first, then wait a minute.
- If the tunnel is flaky, load the dashboard from `results/book_n8n_gemini.json` instead —
  it is the same payload the webhook returns.
