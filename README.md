# Jarvis-AI

A personal daily-ops assistant: **n8n is the agentic back end, Lovable is the front end,
small Python modules do the work.** It reads your mail, calendar, tickets, weather and paper
portfolio, tells you what needs doing, drafts replies for you to send, writes a morning
brief and an end-of-day report, builds slide decks, and recommends music from what you
already play.

It is read-mostly by design: it saves email replies as **Gmail drafts** (never sends), the
Alpaca account is **paper and read-only**, and nothing here places a trade.

| Capability | How | Status |
|---|---|---|
| Read email + calendar, list what you need to do | n8n Gmail/Calendar nodes → `jarvis.inbox` (Gemini) | needs your Google OAuth in n8n |
| Respond to email | `jarvis.inbox drafts` → one Gmail **draft** per reply, in-thread, your voice | needs Google OAuth |
| Open tickets | GitHub issues assigned to you, via `gh` | working |
| Morning brief (07:00 weekdays) | `jarvis.morning_brief` → mailed to you | working (mail step needs OAuth) |
| End-of-day report (18:00 weekdays) | `jarvis.eod_report`: done / still open / tomorrow / tickets / close | working |
| Morning weather | Open-Meteo, keyless | working |
| Investment performance | Alpaca paper: equity, day and month P&L, best/worst | working |
| PowerPoint slides | `jarvis.pptx_builder` from an outline or a topic (LLM drafts the outline) | working |
| Spotify recommendations | your top artists → their tracks you have not played → optional private playlist | needs one-time `spotify auth` |
| Ask Jarvis | n8n agent with `today` and `log` tools, for the dashboard chat | working |
| Daily Digest (team build, n8n Cloud) | `daily_digest/`: v3 two-agent workflow, `GET /webhook/digest` API, `eval.py`, Lovable prompt | see `daily_digest/README.md` |
| Book Explainer | the course project this grew out of: LLM writer → LLM verifier → deterministic guard | see `book_explainer/` |

## Quick start

```bash
pip install -r requirements.txt
```

```bash
copy .env.example .env
```
Fill in what you have (each key is optional; a missing one shows as "not configured").

```bash
python -m jarvis.morning_brief --no-llm
```

```bash
python -m jarvis.portfolio
```

```bash
python -m jarvis.pptx_builder examples/deck_outline.json out/deck.pptx
```

```bash
python -m jarvis.journal done "shipped the thing"
```

## The n8n back end

```bash
npm install -g n8n
```

```bash
pwsh -File n8n/start_n8n.ps1
```
(that script sets the env n8n needs: file access to this folder, `fs` in Code nodes, Execute Command enabled).

```bash
n8n import:workflow --separate --input=n8n/workflows
```
Then in the n8n UI create two credentials with exactly these names — **"Google (Jarvis)"**
(Gmail + Google Calendar OAuth2) and **"Gemini (Jarvis)"** (Google PaLM/Gemini API key) — put
your address in the "Mail it to me" nodes, and publish each workflow. Workflows:

| Workflow | Trigger | What it does |
|---|---|---|
| `jarvis_morning.json` | 07:00 Mon–Fri | calendar + unread mail → JSON → `morning_brief` → email to you |
| `jarvis_eod.json` | 18:00 Mon–Fri | tomorrow's calendar → `eod_report` → email to you |
| `jarvis_email_drafts.json` | 11:00 and 16:00 Mon–Fri | unread mail → reply drafts → **Gmail drafts** (never sent) |
| `jarvis_api.json` | webhooks | `GET /jarvis/today`, `POST /jarvis/slides`, `POST /jarvis/spotify`, `POST /jarvis/ask` (agent) |

## The Lovable front end

`lovable/LOVABLE_PROMPT.md` is the whole spec, including the JSON contract for
`GET /webhook/jarvis/today`. Paste it into Lovable, point the app at your n8n URL.

## Journal

`journal/YYYY-MM-DD.md` is the day's ledger. Workflows append what they did; you append
what you did (`python -m jarvis.journal done ...`, or tell the chat "log this as done: …").
The end-of-day report is built from it, and todos not marked done carry forward for a week.

## What lives where

```
jarvis/            the modules (each is a CLI: python -m jarvis.<name>)
n8n/               build_workflows.py -> workflows/*.json (no credentials inside)
lovable/           the front-end prompt + data contract
daily_digest/      the team's Daily Digest workflow + eval + its own Lovable prompt (n8n Cloud)
book_explainer/    the Book Explainer agent and its evaluation (own README)
examples/          a slide outline to try
journal/ inbox/ out/   runtime files, git-ignored
```

## Safety rules, stated once

- Email: **drafts only**. There is no node that sends a reply.
- Alpaca: paper account, and the module imports only read calls (account, positions, history).
- Spotify: creating a playlist is an explicit `--playlist` flag / button, private by default.
- Keys live in `.env`, which is git-ignored; the workflow JSON references credentials by name.

## For agents

Start with [`HANDOFF.md`](HANDOFF.md): status, hard rules, how to verify.
