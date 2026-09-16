# Lovable prompt: Book Explainer dashboard

Paste everything between the two lines into a new Lovable project as the first message.
After it builds, set the n8n base URL in the app's Settings (the tunnel URL, e.g.
`https://xxxx.hooks.n8n.cloud` or the ngrok URL). If the tunnel is flaky on recording day,
use the app's "Load JSON file" button with `results/book_2026-09-11.json`.

---

Build a single-page React + Tailwind dashboard called **Book Explainer**. It is an
explainability tool for a systematic PAPER-trading book: it shows, for each position, a
plain-English explanation written by an LLM, checked by a second LLM and a deterministic
Python guard, next to the raw numbers it was checked against. It never trades.

**Data source.** A settings dialog (gear icon, top right) stores `n8nBaseUrl` in
localStorage. On load, `GET {n8nBaseUrl}/webhook/book` returns JSON shaped like:

```json
{
  "asof": "2026-09-11", "run": "run_2026-09-11",
  "disclaimer": "This agent explains a PAPER book. It does not trade...",
  "refused_shorts": ["AAPL", "NVDA"],
  "heartbeat": {"available": true, "run_at": "2026-09-14 08:18", "n_stale": 1,
                "sources": [{"source": "ibes_pro_sentiment", "status": "STALE", "newest_print": "2026-05-14", "age_days": 123, "coverage_pct": 0.0}]},
  "positions": [{
    "symbol": "ABBV", "name": "AbbVie Inc.", "sector": "Healthcare", "side": "long",
    "target_dollars": 1919, "entry_date": "2026-09-08", "agg_z": 1.41, "n_sources": 10,
    "entry_score": 0.129, "entry_pct": 94, "latest_score": 0.059, "latest_pct": 74,
    "votes": [{"source": "finra_short_ratio", "label": "FINRA daily short-volume ratio", "family": "positioning",
               "pct": 96, "sign": 1, "fit": "fitted", "contribution": 0.046}],
    "history": [{"day": "2026-08-27", "score": 0.147, "pct": 96}],
    "news": [{"date": "2026-09-12", "publisher": "24/7 Wall St.", "title": "..."}],
    "card": {"symbol": "ABBV", "headline": "...", "body": "paragraphs separated by blank lines",
             "drivers": ["finra_short_ratio"], "dissenters": ["wiki_attention"], "status_today": "faded toward middle"},
    "status_today": "faded toward middle", "verifier_ok": false,
    "verify_problems": ["Body said 'Two of the four...' - corrected to one."],
    "guard_pass": true, "guard_fails": [{"check": "status_today", "detail": "..."}],
    "company_fact_unsupported": []
  }]
}
```

If the fetch fails, show a friendly empty state with a **Load JSON file** button that
reads a local file with the same shape.

**Layout (top to bottom).**
1. Header: "Book Explainer" + "as of {asof}" + a permanent amber banner with the
   `disclaimer` text and a lock icon: "Read-only - this agent does not trade."
2. Health strip: one small pill per heartbeat source (green OK, red STALE/MISSING, tooltip
   with newest print and age in days). Summary text: "{n_stale} stale source(s)". Hide if
   `available` is false.
3. KPI row (4 tiles): positions; long $ vs short $ (sum of target_dollars by side);
   verifier corrected (count where verifier_ok is false, and %); guard pass (count where
   guard_pass, and %).
4. Book table (sortable, filter by side / status / "needs review"): Symbol, Name, Side
   (green long / red short badge), Target $ (comma-formatted), agg_z (2 dp), Sources,
   Status today (badge: "still in decile" blue, "faded toward middle" grey,
   "flipped sign" orange, "no row today" outline), Checks (two small badges:
   "Verifier: clean" or "Verifier: corrected (n)", and "Guard: pass" or "Guard: n flags" in red).
   "Needs review" = guard_pass false OR company_fact_unsupported non-empty.
5. Clicking a row opens a right-side drawer (full height, ~640px wide, full-screen on mobile):
   - Headline (large), then the body rendered as paragraphs; a paragraph that starts with
     "News context:" is styled as a muted callout.
   - "Drivers" and "Dissenters" chips using the vote `label`, each with its contribution.
   - "Checked against" section: a table of `votes` (label, family, percentile, sign as
     "contrarian (-1)" / "momentum (+1)", fitted/thesis, contribution to 3 dp) with
     contributions shown as a small horizontal diverging bar (green right = long vote,
     red left = short vote), plus entry score / percentile vs latest score / percentile.
   - A small line chart of `history` score by day.
   - "Verifier corrections" list (verify_problems) and "Guard flags" list (guard_fails) -
     show "none" explicitly when empty, so a reviewer sees the check happened.
   - News list (date, publisher, title) labelled "Context only - never a reason a rank moved".
6. "Ask the book" chat panel (floating button bottom-right opening a panel): user types a
   question, app `POST {n8nBaseUrl}/webhook/ask` with `{"question": "..."}` and shows
   `answer` from the response `{question, answer}`. Show a typing indicator; 90 s timeout
   with a clear error. Under the input: "Answers only from this book's checked data."
   Provide three example-question chips: "Why are we short C?",
   "What is the largest dissenter on ABT?", "Which positions have flipped sign?".
7. Footer: "Pipeline: n8n - Gemini writer -> Gemini verifier -> Python guard. Paper account only."

**Style.** Clean financial-terminal feel but light by default with a dark-mode toggle;
Inter font; tabular numbers; no stock photos; no emojis. Dollars before percentages in
every label. Mobile-friendly (table becomes cards under 640px).

Do not add login, a database or any trading buttons.

---

## Follow-up prompts if needed
- "The /webhook/book call is blocked by CORS" -> the n8n webhooks already allow `*`; check the
  base URL has no trailing slash and uses https.
- "Add a 'Run explainer for this symbol' button in the drawer that POSTs
  `{symbol}` to `{n8nBaseUrl}/webhook/explain` and shows the returned card and metrics
  (takes ~30 s)."
