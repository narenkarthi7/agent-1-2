"""AGENT 1 - Weather. Uses only REAL API data, never invents numbers."""
import os
import re
from collections import Counter
from datetime import date, timedelta

import requests

OWM = "https://api.openweathermap.org"


def _key():
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key:
        raise RuntimeError("OPENWEATHER_API_KEY is missing in .env")
    return key


def _get(url, **params):
    r = requests.get(url, params=params, timeout=15)
    if r.status_code == 401:
        raise PermissionError("Not allowed on this API plan")
    r.raise_for_status()
    return r.json()


def geocode(city):
    """City name -> latitude, longitude."""
    if not re.fullmatch(r"[A-Za-z .,'-]{2,60}", city or ""):
        raise ValueError("Please give a valid city name.")
    res = _get(f"{OWM}/geo/1.0/direct", q=city, limit=1, appid=_key())
    if not res:
        raise ValueError(f"City '{city}' was not found.")
    return res[0]["lat"], res[0]["lon"], res[0]["name"]


def current(lat, lon):
    d = _get(f"{OWM}/data/2.5/weather", lat=lat, lon=lon, units="metric", appid=_key())
    return {"Temperature °C": d["main"]["temp"], "Feels like °C": d["main"]["feels_like"],
            "Humidity %": d["main"]["humidity"], "Wind m/s": d["wind"]["speed"],
            "Condition": d["weather"][0]["description"]}


def forecast(lat, lon):
    """5-day forecast comes every 3 hours. We group it day by day."""
    d = _get(f"{OWM}/data/2.5/forecast", lat=lat, lon=lon, units="metric", appid=_key())
    days = {}
    for x in d["list"]:
        day = days.setdefault(x["dt_txt"][:10], {"t": [], "rain": 0, "c": []})
        day["t"].append(x["main"]["temp"])
        day["rain"] += x.get("rain", {}).get("3h", 0)
        day["c"].append(x["weather"][0]["main"])
    rows = [{"date": k, "min_temp": round(min(v["t"]), 1), "max_temp": round(max(v["t"]), 1),
             "rain_mm": round(v["rain"], 1), "condition": max(set(v["c"]), key=v["c"].count)}
            for k, v in days.items()]
    pie = dict(Counter(c for v in days.values() for c in v["c"]))
    return rows, pie


def history(lat, lon, n):
    """Past n days. OpenWeatherMap history is a paid plan; if not allowed we use the
    free Open-Meteo API and clearly say so (nothing is invented)."""
    try:
        rows = []
        for i in range(n, 0, -1):
            d = (date.today() - timedelta(days=i)).isoformat()
            x = _get(f"{OWM}/data/3.0/onecall/day_summary", lat=lat, lon=lon,
                     date=d, units="metric", appid=_key())
            rows.append({"date": d, "min_temp": x["temperature"]["min"],
                         "max_temp": x["temperature"]["max"],
                         "rain_mm": x["precipitation"]["total"],
                         "wind_ms": x["wind"]["max"]["speed"]})
        return rows, "OpenWeatherMap"
    except (PermissionError, requests.HTTPError):
        x = _get("https://api.open-meteo.com/v1/forecast", latitude=lat, longitude=lon,
                 past_days=n, forecast_days=1, wind_speed_unit="ms", timezone="auto",
                 daily="temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max")["daily"]
        rows = [{"date": x["time"][i], "min_temp": x["temperature_2m_min"][i],
                 "max_temp": x["temperature_2m_max"][i], "rain_mm": x["precipitation_sum"][i],
                 "wind_ms": x["wind_speed_10m_max"][i]} for i in range(n)]
        return rows, "Open-Meteo (OpenWeatherMap history needs a paid plan)"


def get_weather(city, mode):
    lat, lon, name = geocode(city)
    res = {"city": name, "mode": mode, "source": "OpenWeatherMap",
           "current": None, "rows": None, "pie": None}
    if mode == "current":
        res["current"] = current(lat, lon)
    elif mode == "forecast":
        res["rows"], res["pie"] = forecast(lat, lon)
    else:                                   # "history" = yesterday, "last_10_days"
        res["rows"], res["source"] = history(lat, lon, 10 if mode == "last_10_days" else 1)
    return res
