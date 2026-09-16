"""Morning weather for the user's city. Open-Meteo: free, no key, no account.

    python -m jarvis.weather            # plain-English paragraph
    python -m jarvis.weather --json
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

from .config import USER

# WMO weather interpretation codes, in words a person uses.
CODES = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
         51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
         66: "freezing rain", 67: "heavy freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
         77: "snow grains", 80: "showers", 81: "heavy showers", 82: "violent showers", 85: "snow showers",
         86: "heavy snow showers", 95: "thunderstorms", 96: "thunderstorms with hail", 99: "severe thunderstorms"}


def fetch() -> dict:
    q = urllib.parse.urlencode({
        "latitude": USER["lat"], "longitude": USER["lon"], "timezone": "auto", "forecast_days": 1,
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,"
                 "weather_code,wind_speed_10m_max,sunrise,sunset",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
    })
    d = json.load(urllib.request.urlopen(f"https://api.open-meteo.com/v1/forecast?{q}", timeout=20))
    day = {k: v[0] for k, v in d["daily"].items()}
    hours = list(zip(d["hourly"]["time"], d["hourly"]["temperature_2m"],
                     d["hourly"]["precipitation_probability"], d["hourly"]["weather_code"]))
    commute_am = [h for h in hours if h[0][11:13] in ("07", "08", "09")]
    commute_pm = [h for h in hours if h[0][11:13] in ("17", "18", "19")]
    return {
        "city": USER["city"], "date": day["time"], "sky": CODES.get(day["weather_code"], "mixed"),
        "high_f": round(day["temperature_2m_max"]), "low_f": round(day["temperature_2m_min"]),
        "rain_chance_pct": day["precipitation_probability_max"], "rain_in": day["precipitation_sum"],
        "wind_mph": round(day["wind_speed_10m_max"]),
        "sunrise": day["sunrise"][11:16], "sunset": day["sunset"][11:16],
        "commute_am": {"temp_f": round(commute_am[1][1]) if len(commute_am) > 1 else None,
                       "rain_chance_pct": max(h[2] for h in commute_am) if commute_am else None},
        "commute_pm": {"temp_f": round(commute_pm[1][1]) if len(commute_pm) > 1 else None,
                       "rain_chance_pct": max(h[2] for h in commute_pm) if commute_pm else None},
    }


def report(w: dict | None = None) -> str:
    w = w or fetch()
    line = (f"{w['city']}: {w['sky']}, high {w['high_f']}°F, low {w['low_f']}°F, "
            f"{w['rain_chance_pct']}% chance of rain, wind to {w['wind_mph']} mph. "
            f"Sunrise {w['sunrise']}, sunset {w['sunset']}.")
    tips = []
    if w["rain_chance_pct"] >= 40 or (w["commute_pm"]["rain_chance_pct"] or 0) >= 40:
        tips.append("take a jacket or umbrella")
    if w["high_f"] >= 85:
        tips.append("hot afternoon")
    if w["low_f"] <= 35:
        tips.append("near freezing in the morning")
    am, pm = w["commute_am"], w["commute_pm"]
    if am["temp_f"] is not None and pm["temp_f"] is not None:
        line += f" Morning commute about {am['temp_f']}°F, evening about {pm['temp_f']}°F."
    if tips:
        line += " " + "; ".join(tips).capitalize() + "."
    return line


if __name__ == "__main__":
    w = fetch()
    print(json.dumps(w, indent=1) if "--json" in sys.argv else report(w))
