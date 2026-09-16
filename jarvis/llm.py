"""One thin LLM call, used for summaries and reply drafts. Gemini today; swap the URL and
key name here to move to another provider without touching the rest of the package."""
from __future__ import annotations

import json
import urllib.request

from .config import env

MODEL = env("JARVIS_LLM_MODEL", "gemini-3.5-flash-lite")

VOICE = ("Write the way AJ texts a colleague: short, plain, specific. No 'I hope this finds you well', "
         "no 'I appreciate', no 'looking forward', no exclamation marks. One idea per sentence.")


def ask(system: str, user: str, json_out: bool = False, temperature: float = 0.3) -> str:
    key = env("GEMINI_API_KEY", required=True)
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature}}
    if json_out:
        body["generationConfig"]["responseMimeType"] = "application/json"
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    r = json.load(urllib.request.urlopen(req, timeout=120))
    return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]).strip()


def ask_json(system: str, user: str):
    text = ask(system, user, json_out=True, temperature=0.2)
    return json.loads(text.replace("\\u201c", '"').replace("\\u201d", '"'))
