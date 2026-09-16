"""Investment performance from the Alpaca PAPER account. Read-only by construction: this
module imports only the account, positions and portfolio-history calls. It has no order
path and never will; execution lives elsewhere.

    python -m jarvis.portfolio           # plain-English summary
    python -m jarvis.portfolio --json
"""
from __future__ import annotations

import json
import sys

from .config import env

TOP_N = 5


def _client():
    from alpaca.trading.client import TradingClient
    return TradingClient(env("ALPACA_API_KEY", required=True), env("ALPACA_SECRET_KEY", required=True), paper=True)


def snapshot() -> dict:
    from alpaca.trading.requests import GetPortfolioHistoryRequest
    c = _client()
    a = c.get_account()
    equity, last = float(a.equity), float(a.last_equity)
    positions = []
    for p in c.get_all_positions():
        positions.append({"symbol": p.symbol, "side": "long" if float(p.qty) > 0 else "short",
                          "market_value": round(float(p.market_value), 2),
                          "unrealized_pl": round(float(p.unrealized_pl), 2),
                          "unrealized_pl_pct": round(100 * float(p.unrealized_plpc), 2),
                          "today_pl": round(float(p.unrealized_intraday_pl), 2)})
    hist = c.get_portfolio_history(GetPortfolioHistoryRequest(period="1M", timeframe="1D"))
    eq = [float(x) for x in hist.equity if x]
    month_change = round(eq[-1] - eq[0], 2) if len(eq) > 1 else None
    positions.sort(key=lambda p: p["today_pl"])
    return {
        "account": "paper", "equity": round(equity, 2), "cash": round(float(a.cash), 2),
        "today_pl": round(equity - last, 2), "today_pl_pct": round(100 * (equity - last) / last, 3) if last else None,
        "month_pl": month_change, "n_positions": len(positions),
        "gross_long": round(sum(p["market_value"] for p in positions if p["side"] == "long"), 2),
        "gross_short": round(-sum(p["market_value"] for p in positions if p["side"] == "short"), 2),
        "worst_today": positions[:TOP_N], "best_today": positions[-TOP_N:][::-1],
        "positions": positions,
    }


def report(s: dict | None = None) -> str:
    s = s or snapshot()
    sign = "+" if s["today_pl"] >= 0 else "−"
    out = [f"Paper account: ${s['equity']:,.0f} equity, {sign}${abs(s['today_pl']):,.0f} today "
           f"({s['today_pl_pct']:+.2f}%), {s['n_positions']} positions "
           f"(${s['gross_long']:,.0f} long / ${s['gross_short']:,.0f} short)."]
    if s["month_pl"] is not None:
        out.append(f"Last month: {'+' if s['month_pl'] >= 0 else '−'}${abs(s['month_pl']):,.0f}.")
    if s["positions"]:
        b, w = s["best_today"][0], s["worst_today"][0]
        out.append(f"Best today {b['symbol']} ({b['today_pl']:+,.0f}), worst {w['symbol']} ({w['today_pl']:+,.0f}).")
    return " ".join(out)


if __name__ == "__main__":
    s = snapshot()
    print(json.dumps(s, indent=1) if "--json" in sys.argv else report(s))
