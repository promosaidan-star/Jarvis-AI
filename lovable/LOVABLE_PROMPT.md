# Lovable prompt: Jarvis dashboard

Paste everything between the two lines into a new Lovable project. Set the n8n base URL in
the app's settings (local: `http://localhost:5678`; public: the `n8n start --tunnel` URL).

---

Build a single-page React + Tailwind personal dashboard called **Jarvis**. It is a daily
operations view for one person, fed by an n8n back end. It is read-mostly: it shows the
day, lets the user ask questions, and lets them log what got done. It never sends email or
trades.

**Data.** A settings dialog (gear icon) stores `n8nBaseUrl` in localStorage. On load and every
5 minutes, `GET {n8nBaseUrl}/webhook/jarvis/today` returns:

```json
{
  "date": "2026-09-15", "generated_at": "2026-09-15T07:02:11-04:00",
  "weather": {"city": "Cambridge, MA", "sky": "clear", "high_f": 66, "low_f": 48, "rain_chance_pct": 0,
              "wind_mph": 8, "sunrise": "06:24", "sunset": "18:53",
              "commute_am": {"temp_f": 53, "rain_chance_pct": 0}, "commute_pm": {"temp_f": 63, "rain_chance_pct": 0}},
  "portfolio": {"account": "paper", "equity": 96782.1, "cash": 48370.0, "today_pl": 3.1, "today_pl_pct": 0.003,
                "month_pl": -2118.0, "n_positions": 25, "gross_long": 69234.0, "gross_short": 20823.0,
                "best_today": [{"symbol": "DHR", "side": "long", "market_value": 2900.0, "unrealized_pl": 120.0, "unrealized_pl_pct": 4.3, "today_pl": 147.0}],
                "worst_today": [{"symbol": "CL", "side": "long", "market_value": 2800.0, "unrealized_pl": -40.0, "unrealized_pl_pct": -1.4, "today_pl": -50.0}],
                "positions": []},
  "tickets": [{"repo": "ml-trader", "number": 52, "title": "Define the top-100 universe", "url": "https://github.com/...", "labels": [], "days_since_update": 50, "milestone": null}],
  "calendar": ["09:00 Standup · Zoom", "14:00 Datadog interview"],
  "journal": {"done": ["18:20 Built the n8n pipeline"], "todo": ["18:21 Send rating sheet"], "note": [], "auto": ["07:02 morning brief written"]},
  "carry_forward": ["Send rating sheet to teammates"],
  "morning_brief_md": "# Morning brief — ...", "eod_report_md": null,
  "spotify": {"date": "2026-09-15", "based_on": ["Artist A", "Artist B"], "tracks": [{"artist": "A", "track": "T", "album": "X", "popularity": 70, "url": "https://open.spotify.com/track/...", "because": "you play A"}], "playlist_url": null},
  "drafts_pending": [{"to": "x@y.com", "subject": "Re: ...", "body": "...", "reason": "asked for a time"}],
  "disclaimer": "Read-only assistant. Emails are saved as drafts for you to send; the Alpaca account is paper and never traded from here."
}
```
Any field may be `{"error": "..."}` or null when a feed is not configured: show "not connected" in that card, never crash.

**Layout.**
1. Header: "Jarvis" + the date + a one-line weather strip (sky, high/low, rain %, commute temps) + a permanent small banner with `disclaimer`.
2. Row of three cards: **Today** (calendar lines, then `carry_forward` as "still open" checkboxes), **Needs doing** (parsed from `morning_brief_md` under "Needs doing", or the journal `todo` list), **Tickets** (count, grouped by repo, red "stale" chip when days_since_update > 21, each links to `url`).
3. **Paper portfolio** card: equity, today P&L in dollars then percent (green/red), month P&L, long/short gross, two mini tables best/worst today. Label it "paper account" visibly.
4. **Journal** panel: today's done/todo/note entries with timestamps, and a one-line input with a kind selector (done / todo / note) that `POST {n8nBaseUrl}/webhook/jarvis/ask` with `{"question": "log this as <kind>: <text>"}` and then refreshes.
5. **Reply drafts pending** card: list `drafts_pending` (to, subject, reason) with the note "saved in Gmail Drafts — review and send there". No send button.
6. **Music** card: `spotify.tracks` (artist — track, link) with "because" text; a "Refresh picks" button that `POST {n8nBaseUrl}/webhook/jarvis/spotify` with `{"playlist": false}` and a "Make playlist" button that sends `{"playlist": true}` and shows `playlist_url`.
7. **Slides** card: topic input + slide count, `POST {n8nBaseUrl}/webhook/jarvis/slides` with `{"topic": "...", "slides": 6}`, show the returned `deck` path.
8. Tabs at the bottom to read `morning_brief_md` and `eod_report_md` rendered as markdown.
9. Floating chat button → panel that `POST {n8nBaseUrl}/webhook/jarvis/ask` with `{"question"}` and shows `answer`; three example chips: "What do I need to do today?", "How is the paper book doing?", "Which tickets are stale?".

**Style.** Calm, dense, readable: light by default with a dark toggle, IBM Plex Sans + IBM Plex Mono for numbers, tabular numerals, no stock photos, no emojis, dollars before percentages. Mobile stacks to one column.

Do not add login, a database, a send-email button, or any trading control.

---
