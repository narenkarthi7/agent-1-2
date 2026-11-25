"""AGENT 1 — Weather Intelligence (standalone).

Real data only, never fabricated. OpenWeatherMap with Open-Meteo fallback
for history (OpenWeatherMap history requires a paid plan).

Usage:
    python agent1_weather.py "What is the weather in Chennai today?"
    python agent1_weather.py --city Chennai --mode last_10_days
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

OWM = "https://api.openweathermap.org"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def _key():
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key:
        raise RuntimeError("OPENWEATHER_API_KEY missing in .env / environment")
    return key


def _get(url, **params):
    r = requests.get(url, params=params, timeout=15)
    if r.status_code == 401:
        raise PermissionError("Not allowed on this API plan")
    r.raise_for_status()
    return r.json()


def geocode(city):
    """City name -> lat, lon, display name."""
    if not re.fullmatch(r"[A-Za-z .,'-]{2,60}", city or ""):
        raise ValueError("Please give a valid city name.")
    res = _get(f"{OWM}/geo/1.0/direct", q=city, limit=1, appid=_key())
    if not res:
        raise ValueError(f"City '{city}' was not found.")
    return res[0]["lat"], res[0]["lon"], res[0]["name"]


def current(lat, lon):
    d = _get(f"{OWM}/data/2.5/weather", lat=lat, lon=lon, units="metric", appid=_key())
    return {
        "Temperature °C": d["main"]["temp"],
        "Feels like °C": d["main"]["feels_like"],
        "Humidity %": d["main"]["humidity"],
        "Wind m/s": d["wind"]["speed"],
        "Condition": d["weather"][0]["description"],
    }


def forecast(lat, lon):
    """5-day forecast (3-hourly), grouped day by day."""
    d = _get(f"{OWM}/data/2.5/forecast", lat=lat, lon=lon, units="metric", appid=_key())
    days = {}
    for x in d["list"]:
        day = days.setdefault(x["dt_txt"][:10], {"t": [], "rain": 0, "c": []})
        day["t"].append(x["main"]["temp"])
        day["rain"] += x.get("rain", {}).get("3h", 0)
        day["c"].append(x["weather"][0]["main"])
    rows = [
        {
            "date": k,
            "min_temp": round(min(v["t"]), 1),
            "max_temp": round(max(v["t"]), 1),
            "rain_mm": round(v["rain"], 1),
            "condition": max(set(v["c"]), key=v["c"].count),
        }
        for k, v in days.items()
    ]
    pie = dict(Counter(c for v in days.values() for c in v["c"]))
    return rows, pie


def history(lat, lon, n):
    """Past n days. Falls back to Open-Meteo when OpenWeatherMap history is not
    available on the current plan. Nothing is invented."""
    try:
        rows = []
        for i in range(n, 0, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            x = _get(
                f"{OWM}/data/3.0/onecall/day_summary",
                lat=lat,
                lon=lon,
                date=d,
                units="metric",
                appid=_key(),
            )
            rows.append(
                {
                    "date": d,
                    "min_temp": x["temperature"]["min"],
                    "max_temp": x["temperature"]["max"],
                    "rain_mm": x["precipitation"]["total"],
                    "wind_ms": x["wind"]["max"]["speed"],
                }
            )
        return rows, "OpenWeatherMap"
    except (PermissionError, requests.HTTPError):
        x = _get(
            "https://api.open-meteo.com/v1/forecast",
            latitude=lat,
            longitude=lon,
            past_days=n,
            forecast_days=1,
            wind_speed_unit="ms",
            timezone="auto",
            daily="temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        )["daily"]
        rows = [
            {
                "date": x["time"][i],
                "min_temp": x["temperature_2m_min"][i],
                "max_temp": x["temperature_2m_max"][i],
                "rain_mm": x["precipitation_sum"][i],
                "wind_ms": x["wind_speed_10m_max"][i],
            }
            for i in range(n)
        ]
        return rows, "Open-Meteo (OpenWeatherMap history needs a paid plan)"


def get_weather(city, mode):
    lat, lon, name = geocode(city)
    res = {
        "city": name,
        "mode": mode,
        "source": "OpenWeatherMap",
        "current": None,
        "rows": None,
        "pie": None,
    }
    if mode == "current":
        res["current"] = current(lat, lon)
    elif mode == "forecast":
        res["rows"], res["pie"] = forecast(lat, lon)
    else:  # "history" = yesterday, "last_10_days"
        res["rows"], res["source"] = history(
            lat, lon, 10 if mode == "last_10_days" else 1
        )
    return res


def summarize(question, res):
    """Ask the LLM to write a 2-3 sentence grounded summary using only the data."""
    data = json.dumps(res["current"] or res["rows"])
    prompt = (
        "Summarize this weather data in 2-3 simple sentences. Use ONLY the given "
        "numbers (°C, mm, m/s). Answer the user's question.\n\n"
        f"Question: {question}\nCity: {res['city']}\nData: {data}"
    )
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": "You are a concise weather summarizer."},
            {"role": "user", "content": prompt},
        ],
    }
    r = requests.post(OLLAMA_URL + "/api/chat", json=body, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


def run(city, mode):
    res = get_weather(city, mode)
    text = summarize(f"Weather in {city} ({mode})", res)
    return {"tool": "weather", "city": res["city"], "mode": mode, "source": res["source"],
            "text": text, "data": res}


def main():
    ap = argparse.ArgumentParser(description="Agent 1 — Weather Intelligence")
    ap.add_argument("question", nargs="?", help="Natural-language weather question")
    ap.add_argument("--city", help="City name")
    ap.add_argument(
        "--mode",
        choices=["current", "history", "forecast", "last_10_days"],
        default="current",
        help="Weather mode",
    )
    args = ap.parse_args()

    try:
        if args.question:
            # Very light keyword->mode mapping for the CLI demo
            q = args.question.lower()
            if "last 10" in q or "past 10" in q:
                mode = "last_10_days"
            elif any(w in q for w in ("tomorrow", "forecast", "will be")):
                mode = "forecast"
            elif any(w in q for w in ("yesterday", "was", "history")):
                mode = "history"
            else:
                mode = "current"
            m = re.search(r"in\s+([A-Za-z .,'-]+)", args.question, re.I)
            city = m.group(1).strip() if m else args.city
            if not city:
                print("Please specify a city, e.g. 'Weather in Chennai today'.")
                sys.exit(1)
            result = run(city, mode)
        elif args.city:
            result = run(args.city, args.mode)
        else:
            ap.print_help()
            sys.exit(1)

        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, RuntimeError, PermissionError, requests.RequestException) as e:
        print(f"⚠️  {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
