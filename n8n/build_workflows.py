"""Assemble the Jarvis n8n workflows (importable JSON, no credentials inside).

usage: python n8n/build_workflows.py
writes n8n/workflows/jarvis_morning.json, jarvis_eod.json, jarvis_email_drafts.json, jarvis_api.json

Import:  n8n import:workflow --separate --input=n8n/workflows
Publish: n8n publish:workflow --id=<id>   (then restart n8n)

Credentials are referenced by NAME. Create them in the n8n UI with these names:
  "Google (Jarvis)"  - Gmail + Google Calendar OAuth2 (gmailOAuth2 / googleCalendarOAuth2Api)
  "Gemini (Jarvis)"  - googlePalmApi
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.as_posix()
OUT = HERE / "workflows"
PY = f'cmd /c "cd /d {ROOT} && set PYTHONIOENCODING=utf-8:replace&& python -m '
GOOGLE = {"id": "google-jarvis", "name": "Google (Jarvis)"}
GEMINI = {"googlePalmApi": {"id": "gemini-jarvis", "name": "Gemini (Jarvis)"}}
V = {"schedule": 1.2, "gmail": 2.1, "calendar": 1.3, "code": 2, "exec": 1, "webhook": 2.1, "respond": 1.5,
     "sticky": 1, "agent": 3.1, "gemini_chat": 1.1, "tool_code": 1.3, "manual": 1}


def node(name, type_, version, pos, params, **extra):
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "jarvis" + name + type_)), "name": name, "type": type_,
            "typeVersion": version, "position": pos, "parameters": params, **extra}


def sticky(name, pos, text, w=380, h=200, color=4):
    return node(name, "n8n-nodes-base.stickyNote", V["sticky"], pos, {"content": text, "width": w, "height": h, "color": color})


def schedule(name, pos, hour, minute=0):
    return node(name, "n8n-nodes-base.scheduleTrigger", V["schedule"], pos,
                {"rule": {"interval": [{"field": "cronExpression", "expression": f"{minute} {hour} * * 1-5"}]}})


def gmail_unread(name, pos, hours=24):
    return node(name, "n8n-nodes-base.gmail", V["gmail"], pos, {
        "operation": "getAll", "returnAll": False, "limit": 40, "simple": True,
        "filters": {"readStatus": "unread", "receivedAfter": f"={{{{ $now.minus({{hours: {hours}}}).toISO() }}}}"},
    }, credentials={"gmailOAuth2": GOOGLE})


def calendar(name, pos, day_offset=0):
    return node(name, "n8n-nodes-base.googleCalendar", V["calendar"], pos, {
        "operation": "getAll", "calendar": {"__rl": True, "mode": "list", "value": "primary"}, "returnAll": True,
        "timeMin": f"={{{{ $now.plus({{days: {day_offset}}}).startOf('day').toISO() }}}}",
        "timeMax": f"={{{{ $now.plus({{days: {day_offset}}}).endOf('day').toISO() }}}}",
        "options": {"singleEvents": True, "orderBy": "startTime"},
    }, credentials={"googleCalendarOAuth2Api": GOOGLE})


def write_json(name, pos, filename, source_node, shape):
    js = f"""// Write what the {source_node} node returned to inbox/{filename} for the Python side.
const fs = require('fs');
const items = $('{source_node}').all().map(i => i.json);
const rows = items.map(m => ({shape}));
fs.mkdirSync('{ROOT}/inbox', {{ recursive: true }});
fs.writeFileSync('{ROOT}/inbox/{filename}', JSON.stringify(rows, null, 1));
return [{{ json: {{ written: '{filename}', n: rows.length }} }}];"""
    return node(name, "n8n-nodes-base.code", V["code"], pos, {"jsCode": js})


MAIL_SHAPE = ("{ id: m.id, threadId: m.threadId, from: m.From || m.from, subject: m.Subject || m.subject, "
              "date: m.date, snippet: m.snippet, labels: m.labels || m.labelIds }")
CAL_SHAPE = ("{ summary: m.summary, start: m.start?.dateTime || m.start?.date, end: m.end?.dateTime || m.end?.date, "
             "location: m.location, attendees: (m.attendees || []).map(a => a.email), description: m.description }")


def exec_py(name, pos, module_and_args):
    return node(name, "n8n-nodes-base.executeCommand", V["exec"], pos, {"command": "=" + PY + module_and_args + '"'})


def connect(pairs):
    c = {}
    for src, dst in pairs:
        c.setdefault(src, {"main": [[]]})["main"][0].append({"node": dst, "type": "main", "index": 0})
    return c


def wf(name, nodes, connections, wid):
    return {"id": wid, "name": name, "nodes": nodes, "connections": connections, "active": False,
            "settings": {"executionOrder": "v1", "timezone": "America/New_York"}, "pinData": {}, "tags": []}


def morning():
    n = [sticky("About", [-560, -260], "## Morning brief, 07:00 weekdays\nCalendar + unread mail -> JSON files -> "
                "`python -m jarvis.morning_brief` (weather, to-dos, tickets, paper portfolio) -> mailed to yourself.\n\n"
                "Set your address in the last node.", 420, 170),
         schedule("07:00 weekdays", [-560, 0], 7),
         calendar("Today's calendar", [-340, 0]),
         write_json("Save calendar", [-120, 0], "today_calendar.json", "Today's calendar", CAL_SHAPE),
         gmail_unread("Unread mail (24h)", [100, 0]),
         write_json("Save inbox", [320, 0], "today_inbox.json", "Unread mail (24h)", MAIL_SHAPE),
         exec_py("Build brief (Python)", [540, 0], "jarvis.morning_brief"),
         node("Mail it to me", "n8n-nodes-base.gmail", V["gmail"], [760, 0], {
             "sendTo": "me@example.com", "subject": "=Morning brief {{ $today.toFormat('ccc d LLL') }}",
             "emailType": "text", "message": "={{ $json.stdout }}", "options": {}}, credentials={"gmailOAuth2": GOOGLE})]
    c = connect([("07:00 weekdays", "Today's calendar"), ("Today's calendar", "Save calendar"),
                 ("Save calendar", "Unread mail (24h)"), ("Unread mail (24h)", "Save inbox"),
                 ("Save inbox", "Build brief (Python)"), ("Build brief (Python)", "Mail it to me")])
    return wf("Jarvis - morning brief", n, c, "jarvisMorning001")


def eod():
    n = [sticky("About", [-560, -260], "## End of day, 18:00 weekdays\nTomorrow's calendar -> "
                "`python -m jarvis.eod_report` (done today, still open, tomorrow, tickets, paper close) -> mailed to yourself.", 420, 150),
         schedule("18:00 weekdays", [-560, 0], 18),
         calendar("Tomorrow's calendar", [-340, 0], day_offset=1),
         write_json("Save tomorrow", [-120, 0], "tomorrow_calendar.json", "Tomorrow's calendar", CAL_SHAPE),
         exec_py("Build report (Python)", [100, 0], "jarvis.eod_report"),
         node("Mail it to me", "n8n-nodes-base.gmail", V["gmail"], [320, 0], {
             "sendTo": "me@example.com", "subject": "=End of day {{ $today.toFormat('ccc d LLL') }}",
             "emailType": "text", "message": "={{ $json.stdout }}", "options": {}}, credentials={"gmailOAuth2": GOOGLE})]
    c = connect([("18:00 weekdays", "Tomorrow's calendar"), ("Tomorrow's calendar", "Save tomorrow"),
                 ("Save tomorrow", "Build report (Python)"), ("Build report (Python)", "Mail it to me")])
    return wf("Jarvis - end of day report", n, c, "jarvisEod0000001")


def email_drafts():
    parse = f"""// Turn jarvis.inbox output into one item per draft.
const out = JSON.parse($input.first().json.stdout || '[]');
return out.map(d => ({{ json: d }}));"""
    n = [sticky("About", [-560, -280], "## Reply drafts (never sends)\nUnread mail -> `python -m jarvis.inbox drafts` "
                "(Gemini, AJ's voice) -> one Gmail DRAFT per reply, in the original thread. You read, edit, send.\n\n"
                "Runs at 11:00 and 16:00 weekdays.", 420, 170, 5),
         schedule("11:00 + 16:00 weekdays", [-560, 0], "11,16"),
         gmail_unread("Unread mail (24h)", [-340, 0]),
         write_json("Save inbox", [-120, 0], "today_inbox.json", "Unread mail (24h)", MAIL_SHAPE),
         exec_py("Draft replies (Python)", [100, 0], "jarvis.inbox drafts"),
         node("One item per draft", "n8n-nodes-base.code", V["code"], [320, 0], {"jsCode": parse}),
         node("Create Gmail draft", "n8n-nodes-base.gmail", V["gmail"], [540, 0], {
             "resource": "draft", "subject": "=Re: {{ $json.subject }}", "emailType": "text",
             "message": "={{ $json.body }}",
             "options": {"sendTo": "={{ $json.to }}", "threadId": "={{ $json.threadId }}"}},
              credentials={"gmailOAuth2": GOOGLE}),
         exec_py("Log to journal", [760, 0], "jarvis.journal auto \"drafted reply: {{ $json.subject }}\"")]
    c = connect([("11:00 + 16:00 weekdays", "Unread mail (24h)"), ("Unread mail (24h)", "Save inbox"),
                 ("Save inbox", "Draft replies (Python)"), ("Draft replies (Python)", "One item per draft"),
                 ("One item per draft", "Create Gmail draft"), ("Create Gmail draft", "Log to journal")])
    return wf("Jarvis - email reply drafts", n, c, "jarvisDrafts0001")


def api():
    parse_stdout = """const r = $input.first().json;
let d; try { d = JSON.parse(r.stdout); } catch (e) { throw new Error((r.stderr || r.stdout || '').slice(0, 500)); }
return [{ json: d }];"""
    # topic is quoted for cmd.exe; any quotes inside it are dropped, and the file name is derived from it
    slides_cmd = ('jarvis.pptx_builder --topic "{{ String($json.body.topic).replace(/["^&|<>]/g, '') }}" '
                  '--slides {{ Number($json.body.slides) || 6 }} '
                  f'{ROOT}/out/{{{{ String($json.body.topic).replace(/[^a-z0-9]+/gi, "_").slice(0, 40) }}}}.pptx')
    tool_today = f"""// Tool: today() -> the same JSON the dashboard reads (weather, calendar, tickets, portfolio, journal).
const {{ execSync }} = require('child_process');
return execSync('cmd /c "cd /d {ROOT} && set PYTHONIOENCODING=utf-8:replace&& python -m jarvis.api"', {{ maxBuffer: 1 << 24 }}).toString();"""
    tool_log = f"""// Tool: log(kind|text) -> append to today's journal. kind is done, todo or note.
const {{ execSync }} = require('child_process');
const [kind, ...rest] = String(query).split('|');
const text = rest.join('|').trim().replace(/"/g, "'");
if (!['done', 'todo', 'note'].includes(kind.trim())) return 'kind must be done, todo or note';
execSync('cmd /c "cd /d {ROOT} && python -m jarvis.journal ' + kind.trim() + ' \\"' + text + '\\""');
return 'logged [' + kind.trim() + '] ' + text;"""
    system = ("You are Jarvis, a daily-ops assistant for one person. Always call `today` before answering questions "
              "about their day, mail, tickets, weather or portfolio; answer only from what it returns. Use `log` when "
              "they tell you something is done, to do, or worth noting (input format: kind|text). You cannot send email, "
              "trade, or change anything else; say so if asked. Plain English, short, numbers before adjectives.")
    n = [sticky("About", [-600, -300], "## Jarvis API (for the Lovable dashboard)\n`GET /jarvis/today` payload · "
                "`POST /jarvis/slides {topic, slides}` -> .pptx · `POST /jarvis/spotify {playlist:bool}` -> picks · "
                "`POST /jarvis/ask {question}` -> agent with tools today + log.", 460, 150),
         node("GET /jarvis/today", "n8n-nodes-base.webhook", V["webhook"], [-600, 0],
              {"httpMethod": "GET", "path": "jarvis/today", "responseMode": "responseNode", "options": {"allowedOrigins": "*"}},
              webhookId="jarvis-today"),
         exec_py("Payload (Python)", [-380, 0], "jarvis.api"),
         node("Parse payload", "n8n-nodes-base.code", V["code"], [-160, 0], {"jsCode": parse_stdout}),
         node("Respond: today", "n8n-nodes-base.respondToWebhook", V["respond"], [60, 0], {"respondWith": "firstIncomingItem", "options": {}}),

         node("POST /jarvis/slides", "n8n-nodes-base.webhook", V["webhook"], [-600, 200],
              {"httpMethod": "POST", "path": "jarvis/slides", "responseMode": "responseNode", "options": {"allowedOrigins": "*"}},
              webhookId="jarvis-slides"),
         exec_py("Build deck (Python)", [-380, 200], slides_cmd),
         node("Respond: deck path", "n8n-nodes-base.respondToWebhook", V["respond"], [-160, 200], {
             "respondWith": "json", "responseBody": "={{ JSON.stringify({ deck: $json.stdout.trim(), error: $json.stderr }) }}", "options": {}}),

         node("POST /jarvis/spotify", "n8n-nodes-base.webhook", V["webhook"], [-600, 400],
              {"httpMethod": "POST", "path": "jarvis/spotify", "responseMode": "responseNode", "options": {"allowedOrigins": "*"}},
              webhookId="jarvis-spotify"),
         exec_py("Recommend (Python)", [-380, 400], "jarvis.spotify recs --json {{ $json.body.playlist ? '--playlist' : '' }}"),
         node("Parse picks", "n8n-nodes-base.code", V["code"], [-160, 400], {"jsCode": parse_stdout}),
         node("Respond: picks", "n8n-nodes-base.respondToWebhook", V["respond"], [60, 400], {"respondWith": "firstIncomingItem", "options": {}}),

         node("POST /jarvis/ask", "n8n-nodes-base.webhook", V["webhook"], [-600, 620],
              {"httpMethod": "POST", "path": "jarvis/ask", "responseMode": "responseNode", "options": {"allowedOrigins": "*"}},
              webhookId="jarvis-ask"),
         node("Jarvis (agent)", "@n8n/n8n-nodes-langchain.agent", V["agent"], [-380, 620], {
             "promptType": "define", "text": "={{ $json.body.question }}",
             "options": {"systemMessage": system, "maxIterations": 6}}),
         node("Gemini chat model", "@n8n/n8n-nodes-langchain.lmChatGoogleGemini", V["gemini_chat"], [-460, 840],
              {"modelName": "models/gemini-3.5-flash-lite", "options": {"temperature": 0}}, credentials=GEMINI),
         node("today", "@n8n/n8n-nodes-langchain.toolCode", V["tool_code"], [-280, 840], {
             "name": "today", "description": "Everything about the user's day: weather, calendar, to-dos, tickets, paper portfolio, journal. Input ignored.",
             "language": "javaScript", "jsCode": tool_today}),
         node("log", "@n8n/n8n-nodes-langchain.toolCode", V["tool_code"], [-120, 840], {
             "name": "log", "description": "Append to the user's journal. Input: 'done|text', 'todo|text' or 'note|text'.",
             "language": "javaScript", "jsCode": tool_log}),
         node("Respond: answer", "n8n-nodes-base.respondToWebhook", V["respond"], [-160, 620], {
             "respondWith": "json", "responseBody": "={{ JSON.stringify({ answer: $json.output }) }}", "options": {}})]
    c = connect([("GET /jarvis/today", "Payload (Python)"), ("Payload (Python)", "Parse payload"), ("Parse payload", "Respond: today"),
                 ("POST /jarvis/slides", "Build deck (Python)"), ("Build deck (Python)", "Respond: deck path"),
                 ("POST /jarvis/spotify", "Recommend (Python)"), ("Recommend (Python)", "Parse picks"), ("Parse picks", "Respond: picks"),
                 ("POST /jarvis/ask", "Jarvis (agent)"), ("Jarvis (agent)", "Respond: answer")])
    for src, kind in (("Gemini chat model", "ai_languageModel"), ("today", "ai_tool"), ("log", "ai_tool")):
        c[src] = {kind: [[{"node": "Jarvis (agent)", "type": kind, "index": 0}]]}
    return wf("Jarvis - API and ask agent", n, c, "jarvisApi0000001")


def main():
    OUT.mkdir(exist_ok=True)
    for fname, w in (("jarvis_morning.json", morning()), ("jarvis_eod.json", eod()),
                     ("jarvis_email_drafts.json", email_drafts()), ("jarvis_api.json", api())):
        (OUT / fname).write_text(json.dumps(w, indent=2), encoding="utf-8")
        print("wrote", OUT / fname, len(w["nodes"]), "nodes")


if __name__ == "__main__":
    main()
