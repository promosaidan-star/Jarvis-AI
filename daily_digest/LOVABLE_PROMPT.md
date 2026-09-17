# Lovable prompt — Daily Digest dashboard

Paste everything below the line into a new Lovable project. When it asks for the API URL,
give it the production webhook URL of the "Daily Digest API" workflow, e.g.
`https://<workspace>.app.n8n.cloud/webhook/digest`.

---

Build a single-page React + Tailwind app called **Daily Digest**. It is the front end for
an n8n agent that reads one person's Gmail, Google Chat and Google Calendar every morning,
extracts the day's action items with an LLM agent (which calls tools), and every evening
classifies each item as completed / in progress / blocked / no progress from the day's
email, chat and Drive activity. This page shows the results and the evaluation of the agent.
It never sends email or writes anything back.

**Data.** A settings dialog (gear icon, top right) stores `apiUrl` in localStorage
(default `https://example.app.n8n.cloud/webhook/digest`). On load and on a "Refresh" button,
`GET {apiUrl}` returns:

```json
{
  "generated_at": "2026-09-16T18:05:00Z",
  "days": [
    {
      "date": "2026-09-16",
      "morning": {
        "summary": "3-5 bullet lines of prose",
        "items": [
          {"item_id": "2026-09-16-01", "task": "Send Q3 budget numbers to Alice", "why": "she is blocked on the review",
           "source": "email", "source_ref": "Re: Q3 budget review", "who": "alice@example.com",
           "due": "2026-09-17", "priority": "high"}
        ]
      },
      "evening": {
        "summary": "prose",
        "statuses": [
          {"item_id": "2026-09-16-01", "task": "Send Q3 budget numbers to Alice", "priority": "high", "who": "alice@example.com",
           "status": "completed", "evidence": "reply sent 14:02 with the numbers attached", "evidence_source": "email"}
        ]
      }
    }
  ],
  "eval": {
    "precision": 0.82, "recall": 0.71, "kappa": 0.66, "n_items_labelled": 48, "evening_accuracy": 0.79,
    "injection_test": "held: the injected email became an item for the user, nothing was auto-completed",
    "ablation": [{"config": "A_original", "precision": 0.6, "recall": 0.5},
                 {"config": "B_v3", "precision": 0.82, "recall": 0.71},
                 {"config": "C_v3_notools", "precision": 0.78, "recall": 0.64}],
    "note": "free text"
  }
}
```
`morning` or `evening` may be null for a day; eval numbers may be null or 0 (not yet scored):
show "not scored yet" rather than 0%.

**Layout.**
1. Header: "Daily Digest", a date picker (defaults to the newest day in `days`), a
   "Refresh" button, and a small line "Agent: Gmail + Chat + Calendar → morning items → evening
   status. Read-only view."
2. **Morning** card for the selected day: the summary as short paragraphs, then the items as
   a table: item_id, priority chip (high red, normal grey, low outline), task, who, due,
   source chip (email / chat / calendar), and `source_ref` in muted monospace under the task.
   Sort by item_id.
3. **Evening** card: one row per status, joined to the morning item by `item_id`: task, then
   a status pill — completed green, in_progress blue, blocked orange, no_progress grey —
   then evidence in italics with an `evidence_source` chip. Above the table, four small
   counters (completed / in progress / blocked / no progress). If `evening` is null,
   show "Evening run has not happened yet for this day."
4. **Week strip** below: one column per day in `days` (newest right), each with the item
   count and a tiny stacked bar of the four statuses, click to select that day.
5. **Evaluation** tab (top-level tab next to "Today"): four stat tiles — precision, recall,
   Cohen's kappa (label "inter-rater agreement"), evening accuracy — each with a one-line
   plain-English definition under it (e.g. "recall: share of the real action items the agent
   found"); then the ablation table (config, precision, recall) with a one-line caption
   "same days, three prompts: original prose, v3 structured with tools, v3 with tools
   disconnected"; then a small card "Prompt-injection test" showing `injection_test`; then
   `note`.
6. Footer: "Built with n8n + Lovable. The agent treats mail and chat as data, never as
   instructions."

**Style.** Calm and dense: light by default with a dark toggle, Inter or IBM Plex Sans,
tabular numbers, no stock photos, no emojis in the UI (the status pills use color + text).
Mobile stacks to one column. Show a friendly error with the URL when the fetch fails, and a
"Load sample data" button that fills the page with the JSON above so the layout can be seen
before the API exists.

Do not add login, a database, or any write action.

---
