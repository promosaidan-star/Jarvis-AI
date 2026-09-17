"""Retarget the v3 + API workflow JSON at a different n8n project (credentials, data table, LLM).

    python3 retarget.py --gmail ID:NAME --calendar ID:NAME --gemini ID:NAME --table ID --to me@x.com

Writes daily_digest_v3.<tag>.json and daily_digest_api.<tag>.json (gitignored) next to the originals.
The OpenAI gateway model nodes become Gemini nodes when --gemini is given. Chat and Drive
nodes keep their (foreign) credential ids and fail soft — the merges tolerate an empty feed.
"""
import argparse, copy, json, pathlib

ap = argparse.ArgumentParser()
ap.add_argument("--gmail"); ap.add_argument("--calendar"); ap.add_argument("--gemini")
ap.add_argument("--table", required=True); ap.add_argument("--to")
ap.add_argument("--model", default="models/gemini-3.5-flash-lite")
ap.add_argument("--tag", default="local")
a = ap.parse_args()
here = pathlib.Path(__file__).parent


def cred(s):
    i, n = s.split(":", 1)
    return {"id": i, "name": n}


def retarget(wf):
    wf = copy.deepcopy(wf)
    for n in wf["nodes"]:
        c = n.get("credentials", {})
        if a.gmail and "gmailOAuth2" in c: c["gmailOAuth2"] = cred(a.gmail)
        if a.calendar and "googleCalendarOAuth2Api" in c: c["googleCalendarOAuth2Api"] = cred(a.calendar)
        if n["type"] == "@n8n/n8n-nodes-langchain.lmChatOpenAi" and a.gemini:
            temp = n["parameters"].get("options", {}).get("temperature", 0.2)
            n["type"] = "@n8n/n8n-nodes-langchain.lmChatGoogleGemini"; n["typeVersion"] = 1
            n["parameters"] = {"modelName": a.model, "options": {"temperature": temp}}
            n["credentials"] = {"googlePalmApi": cred(a.gemini)}
        if n["type"] == "n8n-nodes-base.dataTable":
            n["parameters"]["dataTableId"] = {"__rl": True, "mode": "id", "value": a.table,
                                              "cachedResultName": "Daily Digest Log"}
        if n["type"] == "n8n-nodes-base.set" and a.to:
            for asg in n["parameters"].get("assignments", {}).get("assignments", []):
                if asg["name"] == "digestTo": asg["value"] = a.to
    return wf


for name in ("daily_digest_v3", "daily_digest_api"):
    src = json.loads((here / f"{name}.json").read_text(encoding="utf-8"))
    out = retarget(src)
    (here / f"{name}.{a.tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", f"{name}.{a.tag}.json", len(out["nodes"]), "nodes")
