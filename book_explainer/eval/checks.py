"""Deterministic guard + hallucination checks for Book Explainer cards.

Pure functions over (position, glossary, card). No LLM, no network, no prices.
Used three ways: the eval scripts, the n8n Code node (a JS port lives in
n8n/guard.js), and as the "machine score" on every card in the front-end.

A card is {symbol, headline, body, drivers, dissenters, status_today}.
A position is one entry of batch_k.json["positions"].
"""
from __future__ import annotations

import itertools
import re
import unicodedata

NUM_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}

EFFICACY = re.compile(
    r"\b(predicts?|predictive|has (an )?edge|proven|will (rise|fall|outperform|underperform|go up|go down)"
    r"|expected to (rise|fall|outperform)|the aggregate works|strategy works|profitable signal)\b", re.I)
CAUSAL_NEWS = re.compile(r"\b(explains?|because of|caused|driving|drove|reflected in|behind the|due to)\b", re.I)

STOP = set("""the a an and or of in on at to for with by from as is are was were be been its it this that
which who whose into through about than then also plus company companies corporation inc group
headquartered based offers provides sells makes maker firm business operates operating together
subsidiaries worldwide globally internationally united states market value worth roughly about some
around nearly under over more most other such their them they one two three four five segments segment
sector industry billion trillion employees staff people selling sells running runs making owns
combining including spanning across serving through""".split())

US_STATES = dict(x.split(":") for x in """AL:alabama AK:alaska AZ:arizona AR:arkansas CA:california CO:colorado CT:connecticut
DE:delaware FL:florida GA:georgia IL:illinois IN:indiana IA:iowa KS:kansas KY:kentucky LA:louisiana MA:massachusetts
MD:maryland MI:michigan MN:minnesota MO:missouri NC:north-carolina NJ:new-jersey NY:new-york OH:ohio OK:oklahoma
OR:oregon PA:pennsylvania RI:rhode-island TN:tennessee TX:texas VA:virginia WA:washington WI:wisconsin DC:washington""".split())


LITERAL_ESCAPE = re.compile(r"\\u[0-9a-fA-F]{4}|\\n|\\t")


def _norm(s: str) -> str:
    # Some models emit literal "“" instead of the character; decode so the other
    # checks see real quotes (the escape itself is reported by the bad_escape check).
    s = LITERAL_ESCAPE.sub(lambda m: m.group(0).encode().decode("unicode_escape"), s)
    s = unicodedata.normalize("NFKC", s)
    return (s.replace("’", "'").replace("‘", "'").replace("“", '"')
             .replace("”", '"').replace("−", "-").replace("—", " - ").replace("–", "-"))


def _rows(pos):
    return [r for r in (pos.get("entry"), pos.get("latest")) if r]


def expected_status(pos) -> str:
    lt = pos.get("latest")
    if not lt:
        return "no row today"
    side, agg = pos["position"], lt["agg"]
    if (side > 0 and agg > lt["hi_thr"]) or (side < 0 and agg < lt["lo_thr"]):
        return "still in decile"
    if agg * side < 0:
        return "flipped sign"
    return "faded toward middle"


def _allowed(pos, batch_positions):
    rows = _rows(pos)
    pct = {round(v["pct"] * 100) for r in rows for v in r["votes"]}
    pct |= {round(r["agg_pct"] * 100) for r in rows}
    pct |= {round(h["agg_pct"] * 100) for h in pos.get("history", [])}
    three = set()
    for r in rows:
        cs = [v["contribution"] for v in r["votes"]]
        three |= {abs(round(c, 3)) for c in cs}
        # sums of 2-3 legs ("the two short-interest legs supply -0.053") are legitimate
        for k in (2, 3):
            three |= {abs(round(sum(c), 3)) for c in itertools.combinations(cs, k)}
        three |= {abs(round(r[k], 3)) for k in ("agg", "hi_thr", "lo_thr")}
    hist = pos.get("history", [])
    for h in hist:
        three |= {abs(round(h[k], 3)) for k in ("agg", "hi_thr", "lo_thr")}
    aggs = [h["agg"] for h in hist] + [r["agg"] for r in rows]
    three |= {abs(round(a - b, 3)) for a, b in itertools.combinations(aggs, 2)}  # score changes
    # per-source vote swing entry -> latest
    if pos.get("entry") and pos.get("latest"):
        le = {v["source"]: v["contribution"] for v in pos["latest"]["votes"]}
        three |= {abs(round(le[v["source"]] - v["contribution"], 3))
                  for v in pos["entry"]["votes"] if v["source"] in le}
    z = {abs(round(r["agg_z"], 2)) for r in rows if r.get("agg_z") is not None}
    raw = {abs(v["value"]) for r in rows for v in r["votes"] if isinstance(v.get("value"), (int, float))}
    three |= raw
    z |= raw | {abs(round(x[k], 2)) for x in rows + hist for k in ("agg", "hi_thr", "lo_thr")}
    dollars = {abs(round(pos["target_dollars"])), abs(round(pos.get("current_dollars") or 0))}
    dollars |= {abs(round(p["target_dollars"])) for p in batch_positions} | {round(x) for x in raw}
    days = {r["day"] for r in rows} | {h["day"] for h in hist} | {pos["entry_date"]}
    nsrc = {r["n_sources"] for r in rows} | {h["n_sources"] for h in hist}
    return pct, three, z, dollars, days, nsrc


def _near(x, allowed, tol):
    return any(abs(x - a) <= tol + 1e-9 for a in allowed)


def guard(card, pos, glossary, batch_positions=()) -> list[dict]:
    """Return a list of {check, detail} failures. Empty list = card passes."""
    out = []
    sym = pos["symbol"]
    bg = glossary.get("backgrounds", {}).get(sym, {})
    text = _norm(card.get("headline", "") + "\n\n" + card.get("body", ""))
    text = re.sub(r'"[^"]{12,}"', '"<quote>"', text)  # quoted headlines are checked by news_checks
    pct, three, z, dollars, days, nsrc = _allowed(pos, batch_positions)
    allday = days | {n["date"] for n in bg.get("news", [])}

    for m in re.finditer(r"\b(\d{1,3})(?:st|nd|rd|th)\b", text):
        if int(m.group(1)) not in pct:
            out.append({"check": "percentile", "detail": m.group(0)})
    for m in re.finditer(r"(?<![\d.$])[-+]?\d+\.\d{3}(?!\d)", text):
        if not _near(abs(float(m.group(0))), three, 0.0011):
            out.append({"check": "3dp_number", "detail": m.group(0)})
    for m in re.finditer(r"(?<![\d.$])[-+]?\d\.\d{2}(?![\d%BT])", text):
        if not _near(abs(float(m.group(0))), z, 0.011):
            out.append({"check": "agg_z", "detail": m.group(0)})
    for m in re.finditer(r"\$(\d{1,3}(?:,\d{3})+|\d+)(?![.\d]*\s?[BTMK]\b)(?!\.\d)", text):
        if not _near(int(m.group(1).replace(",", "")), dollars, 1):
            out.append({"check": "dollars", "detail": m.group(0)})
    for m in re.finditer(r"\$(\d+(?:\.\d)?)\s?([BT])\b", text):
        if bg.get("market_cap_str") and m.group(0).replace(" ", "") != bg["market_cap_str"]:
            out.append({"check": "market_cap", "detail": m.group(0)})
    for m in re.finditer(r"\b20\d\d-\d\d-\d\d\b", text):
        if m.group(0) not in allday:
            out.append({"check": "date", "detail": m.group(0)})
    for m in re.finditer(r"(?<![\d-])(\d\d-\d\d)(?![\d-])", text):
        if not any(d.endswith(m.group(1)) for d in allday):
            out.append({"check": "date", "detail": m.group(0)})
    for m in re.finditer(r"\b(?:on |with |from )?(\w+)(?:-source\b| sources voted\b(?! (?:short|long|the other|against))| voting sources\b)", text, re.I):
        w = m.group(1).lower()
        n = NUM_WORDS.get(w, int(w) if w.isdigit() else None)
        if n is not None and n not in nsrc:
            out.append({"check": "n_sources", "detail": m.group(0)})

    exp = expected_status(pos)
    if card.get("status_today") != exp:
        out.append({"check": "status_today", "detail": f"{card.get('status_today')!r} != {exp!r}"})

    entry = pos.get("entry") or pos.get("latest")
    if entry:
        contrib = {v["source"]: v["contribution"] for v in entry["votes"]}
        for key, want_sign in (("drivers", 1), ("dissenters", -1)):
            keys = card.get(key) or []
            bad = [k for k in keys if k not in contrib]
            if bad:
                out.append({"check": f"{key}_unknown", "detail": ",".join(bad)})
                continue
            wrong = [k for k in keys if contrib[k] * pos["position"] * want_sign < 0]
            if wrong:
                out.append({"check": f"{key}_direction", "detail": ",".join(wrong)})
            mags = [round(abs(contrib[k]), 3) for k in keys]
            if mags != sorted(mags, reverse=True):
                out.append({"check": f"{key}_order", "detail": ",".join(keys)})

    if LITERAL_ESCAPE.search(card.get("headline", "") + card.get("body", "")):
        out.append({"check": "bad_escape", "detail": "literal \\uXXXX escape in the text a reader sees"})
    if len(card.get("headline", "").split()) > 20:
        out.append({"check": "headline_length", "detail": f"{len(card['headline'].split())} words"})
    if (m := EFFICACY.search(text)):
        out.append({"check": "efficacy_claim", "detail": m.group(0)})
    out += news_checks(card, bg)
    return out


def _news_para(body):
    paras = [p for p in _norm(body).split("\n\n") if p.strip().lower().startswith("news context")]
    return paras[0] if paras else ""


def news_checks(card, bg) -> list[dict]:
    out = []
    para = _news_para(card.get("body", ""))
    if not para:
        return out
    para = re.sub(r"\s+", " ", para)
    titles = [re.sub(r"\s+", " ", _norm(n["title"])).strip() for n in bg.get("news", [])]
    # A title may itself contain quotes ("Izzy"), so drop verbatim titles before looking at the rest.
    for t in sorted(titles, key=len, reverse=True):
        for form in (f'"{t}"', f'"{t.rstrip(".")}"', t):
            para = para.replace(form, "<title>")
    for q in re.findall(r'"([^"]{12,})"', para):
        q = q.strip().rstrip(",.")
        if not any(q == t or q == t.rstrip(".") for t in titles):
            kind = "headline_truncated" if any(t.startswith(q[:25]) for t in titles) else "headline_not_in_background"
            out.append({"check": kind, "detail": q[:90]})
    if (m := CAUSAL_NEWS.search(re.sub(r'"[^"]*"', '""', para))):  # words inside quoted titles don't count
        out.append({"check": "news_causal", "detail": m.group(0)})
    return out


def company_fact_check(card, bg) -> dict:
    """Token-overlap check on the orienting (first) sentence against the background.

    Returns {sentence, unsupported: [tokens]}; unsupported empty = pass.
    """
    body = _norm(card.get("body", "")).strip()
    first = re.split(r"(?<=[.!?])\s+", body, maxsplit=1)[0] if body else ""
    hq = str(bg.get("hq", ""))
    hq += " " + " ".join(US_STATES.get(t, "").replace("-", " ") for t in re.findall(r"\b[A-Z]{2}\b", hq))
    blob = _norm(" ".join(str(bg.get(k, "")) for k in ("name", "sector", "industry", "summary", "market_cap_str")) + " " + hq).lower()
    blob_tokens = set(re.findall(r"[a-z][a-z&'-]+", blob))
    blob_tokens |= {re.sub(r"ies$", "y", t) for t in blob_tokens} | {t.rstrip("s") for t in blob_tokens}
    stems = {t[:5] for t in blob_tokens if len(t) >= 5}
    unsupported = []
    for tok in re.findall(r"[A-Za-z][A-Za-z&'-]+", first):
        t = tok.lower().strip("'-")
        if len(t) < 4 or t in STOP or t in blob_tokens:
            continue
        if len(t) >= 5 and t[:5] in stems:  # manufacturer/manufactures, semiconductor(s)
            continue
        unsupported.append(t)
    return {"sentence": first, "unsupported": unsupported}
