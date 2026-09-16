"""Assemble the importable n8n workflow JSON files from n8n/code/*.js.

usage: python n8n/build_workflows.py
writes n8n/workflows/book_explainer.json, ask_the_book.json, book_api.json

Keeping the JS in separate files keeps it diffable; the exported JSON is what gets
imported (`n8n import:workflow --separate --input=n8n/workflows`) and submitted.
Credentials are referenced by name only - no key ever lands in these files.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.as_posix()
CODE = HERE / "code"
OUT = HERE / "workflows"
GEMINI_CRED = {"googlePalmApi": {"id": "gemini-book-explainer", "name": "Gemini (Book Explainer)"}}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
PY = f'cmd /c "set PYTHONIOENCODING=utf-8:replace&& python {ROOT}/eval/'

V = {  # node typeVersions for the installed n8n (checked against node_modules)
    "manual": 1, "webhook": 2.1, "code": 2, "if": 2.3, "split": 3, "http": 4.5, "exec": 1, "respond": 1.5,
    "sticky": 1, "agent": 3.1, "gemini_chat": 1.1, "tool_code": 1.3,
}


def js(name):
    return (CODE / name).read_text(encoding="utf-8")


def node(name, type_, version, pos, params, **extra):
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, name + type_)), "name": name, "type": type_,
            "typeVersion": version, "position": pos, "parameters": params, **extra}


def code(name, pos, file):
    return node(name, "n8n-nodes-base.code", V["code"], pos, {"jsCode": js(file)})


def sticky(name, pos, text, w=380, h=220, color=7):
    return node(name, "n8n-nodes-base.stickyNote", V["sticky"], pos,
                {"content": text, "width": w, "height": h, "color": color})


def gemini_http(name, pos, system_expr, user_expr):
    body = ("={{ JSON.stringify({ systemInstruction: { parts: [{ text: " + system_expr + " }] }, "
            "contents: [{ role: 'user', parts: [{ text: " + user_expr + " }] }], "
            "generationConfig: { responseMimeType: 'application/json', temperature: 0.2 } }) }}")
    return node(name, "n8n-nodes-base.httpRequest", V["http"], pos, {
        "method": "POST", "url": GEMINI_URL, "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googlePalmApi", "sendBody": True, "specifyBody": "json", "jsonBody": body,
        "options": {"timeout": 300000},
    }, credentials=GEMINI_CRED, retryOnFail=True, maxTries=3, waitBetweenTries=5000)


def connect(pairs):
    c = {}
    for src, dst, *rest in pairs:
        out_idx = rest[0] if rest else 0
        kind = rest[1] if len(rest) > 1 else "main"
        slot = c.setdefault(src, {}).setdefault(kind, [])
        while len(slot) <= out_idx:
            slot.append([])
        slot[out_idx].append({"node": dst, "type": kind, "index": 0})
    return c


def wf(name, nodes, connections, wid):
    return {"id": wid, "name": name, "nodes": nodes, "connections": connections, "active": False,
            "settings": {"executionOrder": "v1"}, "pinData": {}, "tags": []}


def book_explainer():
    n = [
        sticky("About", [-520, -300],
               "## Book Explainer (read-only)\nTurns the paper book's decomposition JSON into one plain-English "
               "card per position.\n\n**Writer LLM -> Verifier LLM -> deterministic Python guard.**\n\n"
               "The LLMs see only glossary + batch JSON: no prices, no returns, no account, no orders.", 420, 260, 4),
        node("Run full book (manual)", "n8n-nodes-base.manualTrigger", V["manual"], [-460, 0], {}),
        node("POST /explain", "n8n-nodes-base.webhook", V["webhook"], [-460, 200],
             {"httpMethod": "POST", "path": "explain", "responseMode": "responseNode",
              "options": {"allowedOrigins": "*"}}, webhookId="book-explainer-explain"),
        code("Load run", [-220, 100], "load_run.js"),
        node("Symbol in book?", "n8n-nodes-base.if", V["if"], [0, 100], {
            "conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
                           "conditions": [{"id": "c1", "leftValue": "={{ $json.refused }}", "rightValue": False,
                                           "operator": {"type": "boolean", "operation": "false", "singleValue": True}}],
                           "combinator": "and"}, "options": {}}),
        node("Loop over batches", "n8n-nodes-base.splitInBatches", V["split"], [240, 0], {"options": {}}),
        gemini_http("Writer (Gemini)", [480, 100], "$json.writerSystem", "$json.files"),
        code("Parse draft", [700, 100], "parse_draft.js"),
        gemini_http("Verifier (Gemini)", [920, 100], "$json.verifierSystem", "$json.verifierUser"),
        code("Parse verified", [1140, 100], "parse_verified.js"),
        node("Deterministic guard (Python)", "n8n-nodes-base.executeCommand", V["exec"], [1360, 100],
             {"command": "=" + PY + 'guard_cli.py {{ $json.outDir }} {{ $json.k }}"'}),
        code("Attach guard", [1580, 100], "attach_guard.js"),
        code("Merge + write explanations.json", [480, -160], "merge_run.js"),
        node("Respond: cards", "n8n-nodes-base.respondToWebhook", V["respond"], [720, -160],
             {"respondWith": "firstIncomingItem", "options": {}}),
        node("Respond: not in book", "n8n-nodes-base.respondToWebhook", V["respond"], [240, 260],
             {"respondWith": "firstIncomingItem", "options": {"responseCode": 404}}),
        sticky("Guard note", [1300, -140],
               "### Deterministic guard\n`eval/guard_cli.py` re-checks every percentile, contribution, agg_z, dollar "
               "figure, date, status_today rule, driver order, headline quotes and efficacy claims against the JSON. "
               "Failures are attached to the card, never hidden.", 420, 200, 5),
    ]
    c = connect([
        ("Run full book (manual)", "Load run"), ("POST /explain", "Load run"), ("Load run", "Symbol in book?"),
        ("Symbol in book?", "Loop over batches", 0), ("Symbol in book?", "Respond: not in book", 1),
        ("Loop over batches", "Merge + write explanations.json", 0), ("Loop over batches", "Writer (Gemini)", 1),
        ("Writer (Gemini)", "Parse draft"), ("Parse draft", "Verifier (Gemini)"), ("Verifier (Gemini)", "Parse verified"),
        ("Parse verified", "Deterministic guard (Python)"), ("Deterministic guard (Python)", "Attach guard"),
        ("Attach guard", "Loop over batches"), ("Merge + write explanations.json", "Respond: cards"),
    ])
    return wf("Book Explainer - writer, verifier, guard", n, c, "bookExplainer001")


def ask_the_book():
    system = (HERE / "ask_system_prompt.md").read_text(encoding="utf-8")
    n = [
        node("POST /ask", "n8n-nodes-base.webhook", V["webhook"], [-400, 0],
             {"httpMethod": "POST", "path": "ask", "responseMode": "responseNode", "options": {"allowedOrigins": "*"}},
             webhookId="book-explainer-ask"),
        node("Ask the book (agent)", "@n8n/n8n-nodes-langchain.agent", V["agent"], [-120, 0], {
            "promptType": "define", "text": "={{ $json.body.question }}",
            "options": {"systemMessage": system, "maxIterations": 6}}),
        node("Gemini chat model", "@n8n/n8n-nodes-langchain.lmChatGoogleGemini", V["gemini_chat"], [-200, 240],
             {"modelName": "models/gemini-3.5-flash-lite", "options": {"temperature": 0}}, credentials=GEMINI_CRED),
        node("list_book", "@n8n/n8n-nodes-langchain.toolCode", V["tool_code"], [0, 240], {
            "name": "list_book", "description": "List every position in the paper book. Input is ignored (pass an empty string).",
            "language": "javaScript", "jsCode": js("tool_list_book.js")}),
        node("get_position", "@n8n/n8n-nodes-langchain.toolCode", V["tool_code"], [160, 240], {
            "name": "get_position",
            "description": "Get one position's checked numbers, verified explanation and news. Input: the ticker symbol, e.g. ABBV.",
            "language": "javaScript", "jsCode": js("tool_get_position.js")}),
        node("Respond: answer", "n8n-nodes-base.respondToWebhook", V["respond"], [220, 0], {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ question: $('POST /ask').item.json.body.question, answer: $json.output }) }}",
            "options": {}}),
    ]
    c = connect([("POST /ask", "Ask the book (agent)"), ("Ask the book (agent)", "Respond: answer")])
    for src, kind in (("Gemini chat model", "ai_languageModel"), ("list_book", "ai_tool"), ("get_position", "ai_tool")):
        c[src] = {kind: [[{"node": "Ask the book (agent)", "type": kind, "index": 0}]]}
    return wf("Ask the book - grounded Q&A agent", n, c, "askTheBook00001")


def book_api():
    n = [
        node("GET /book", "n8n-nodes-base.webhook", V["webhook"], [-300, 0],
             {"httpMethod": "GET", "path": "book", "responseMode": "responseNode", "options": {"allowedOrigins": "*"}},
             webhookId="book-explainer-book"),
        node("Build book payload (Python)", "n8n-nodes-base.executeCommand", V["exec"], [-60, 0],
             {"command": "=" + PY + 'book_cli.py"'}),
        code("Parse payload", [180, 0], "parse_book.js"),
        node("Respond: book", "n8n-nodes-base.respondToWebhook", V["respond"], [400, 0],
             {"respondWith": "firstIncomingItem", "options": {}}),
    ]
    c = connect([("GET /book", "Build book payload (Python)"), ("Build book payload (Python)", "Parse payload"),
                 ("Parse payload", "Respond: book")])
    return wf("Book API - payload for the dashboard", n, c, "bookApi00000001")


def main():
    OUT.mkdir(exist_ok=True)
    for fname, w in (("book_explainer.json", book_explainer()), ("ask_the_book.json", ask_the_book()),
                     ("book_api.json", book_api())):
        (OUT / fname).write_text(json.dumps(w, indent=2), encoding="utf-8")
        print("wrote", OUT / fname, len(w["nodes"]), "nodes")


if __name__ == "__main__":
    main()
