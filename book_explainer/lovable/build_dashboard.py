"""Build the static dashboard: the Lovable page's data contract, rendered offline.

usage: python lovable/build_dashboard.py [book_json] [out_html]
defaults: results/book_n8n_gemini.json -> lovable/book_explainer_dashboard.html

Same payload the n8n `GET /book` webhook returns, embedded in the page, so the dashboard
works with no server (the recording fallback) and doubles as the visual reference for the
Lovable build.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Three recorded Q&A from the scored Ask-the-book run: one lookup, one comparison, one refusal.
PICK = ["in_06", "in_01", "out_4"]


def qa_pairs():
    f = ROOT / "results" / "run_2026-09-11" / "ask_answers.json"
    if not f.exists():
        return []
    ans = {a["id"]: a for a in json.loads(f.read_text(encoding="utf-8"))}
    return [{"q": ans[i]["question"], "a": ans[i]["answer"], "refuse": ans[i]["kind"] == "out_of_scope"}
            for i in PICK if i in ans]


def main():
    book_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "book_n8n_gemini.json"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "book_explainer_dashboard.html"
    book = json.loads(book_path.read_text(encoding="utf-8"))
    # trim to what the page draws, to keep the file small
    for p in book["positions"]:
        p["history"] = p.get("history", [])[-12:]
        p["news"] = p.get("news", [])[:5]
    html = (HERE / "dashboard_template.html").read_text(encoding="utf-8")
    dump = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")  # noqa: E731
    html = html.replace("__BOOK_JSON__", dump(book)).replace("__QA_JSON__", dump(qa_pairs()))
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB, {len(book['positions'])} positions, {book['asof']})")


if __name__ == "__main__":
    main()
