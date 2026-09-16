"""Smoke test: the exact n8n request shape (prompt verbatim + runtime adapter) on one batch, in Python.

usage: python eval/smoke_gemini.py <k> [--symbols ABBV,ABT]
writes runs/smoke_<k>/ with glossary, batch, draft, verified; then run guard_cli on it.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "run_2026-09-11"
MODEL = "gemini-3.5-flash-lite"
ADAPTER = (Path(__file__).parent.parent / "n8n" / "code" / "load_run.js").read_text(encoding="utf-8").split("const ADAPTER = `", 1)[1].split("`;", 1)[0]


def key():
    for line in open("C:/Users/ajwal/Documents/AJ-Algo-Trader/.env", encoding="utf-8"):
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')


def call(system, user):
    body = json.dumps({"systemInstruction": {"parts": [{"text": system}]},
                       "contents": [{"role": "user", "parts": [{"text": user}]}],
                       "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key()})
    t = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=600))
    text = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
    return json.loads(text), r.get("usageMetadata", {}), time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("k", type=int)
    ap.add_argument("--symbols")
    a = ap.parse_args()
    glossary = json.loads((SRC / "glossary.json").read_text(encoding="utf-8"))
    positions = json.loads((SRC / f"batch_{a.k}.json").read_text(encoding="utf-8"))["positions"]
    if a.symbols:
        positions = [p for p in positions if p["symbol"] in a.symbols.split(",")]
    out = ROOT / "runs" / f"smoke_{a.k}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "glossary.json").write_text(json.dumps(glossary), encoding="utf-8")
    (out / "batch_0.json").write_text(json.dumps({"positions": positions}), encoding="utf-8")
    syms = {p["symbol"] for p in positions}
    g = {**glossary, "backgrounds": {s: v for s, v in glossary["backgrounds"].items() if s in syms}}
    wp = (SRC / "prompts" / "writer_prompt.md").read_text(encoding="utf-8").replace("{S}", ".").replace("{k}", "0") + ADAPTER
    vp = (SRC / "prompts" / "verifier_prompt.md").read_text(encoding="utf-8").replace("{S}", ".").replace("{k}", "0") + ADAPTER
    files = f"=== glossary.json ===\n{json.dumps(g)}\n\n=== batch_0.json ===\n{json.dumps({'positions': positions})}"
    draft, u1, s1 = call(wp, files)
    (out / "draft_0.json").write_text(json.dumps(draft, indent=1), encoding="utf-8")
    ver, u2, s2 = call(vp, files + f"\n\n=== draft_0.json ===\n{json.dumps(draft)}")
    (out / "verified_0.json").write_text(json.dumps(ver, indent=1), encoding="utf-8")
    print(json.dumps({"n": len(positions), "writer": {"s": round(s1, 1), **{k: u1.get(k) for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount")}},
                      "verifier": {"s": round(s2, 1), **{k: u2.get(k) for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount")}},
                      "corrected": sum(1 for r in ver.get("results", []) if r.get("ok") is False)}, indent=1))


if __name__ == "__main__":
    main()
