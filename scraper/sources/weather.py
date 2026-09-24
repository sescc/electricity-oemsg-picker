"""Weather inputs from Open-Meteo (free, no key): ERA5 history and the seasonal ensemble forecast.

Cooling degree days (CDD, base 24 °C) are the weather driver of household consumption:
in Singapore almost all weather-sensitive load is air-conditioning.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

LAT, LON = 1.3521, 103.8198
CDD_BASE = 24.0
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
SEASONAL = "https://seasonal-api.open-meteo.com/v1/seasonal"


def monthly_from_daily(dates: list[str], temps: list[float | None]) -> dict[str, dict]:
    acc = defaultdict(lambda: {"t": 0.0, "cdd": 0.0, "n": 0})
    for d, t in zip(dates, temps):
        if t is None:
            continue
        a = acc[d[:7]]
        a["t"] += t
        a["cdd"] += max(0.0, t - CDD_BASE)
        a["n"] += 1
    return {k: {"mean_temp": round(v["t"] / v["n"], 3), "cdd": round(v["cdd"], 2), "days": v["n"]}
            for k, v in sorted(acc.items())}


def fetch_history(session, start="2005-01-01", end: str | None = None) -> dict[str, dict]:
    end = end or (dt.date.today() - dt.timedelta(days=7)).isoformat()
    r = session.get(ARCHIVE, check_robots=False, params={
        "latitude": LAT, "longitude": LON, "start_date": start, "end_date": end,
        "daily": "temperature_2m_mean", "timezone": "Asia/Singapore"}).json()
    months = monthly_from_daily(r["daily"]["time"], r["daily"]["temperature_2m_mean"])
    # drop a trailing partial month
    return {k: v for k, v in months.items() if v["days"] >= 28}


def fetch_seasonal(session) -> dict[str, dict]:
    """Ensemble-mean monthly CDD for the coming months, with the ensemble spread."""
    r = session.get(SEASONAL, check_robots=False, params={
        "latitude": LAT, "longitude": LON, "daily": "temperature_2m_mean", "forecast_days": 183}).json()
    daily = r["daily"]
    dates = daily["time"]
    members = [k for k in daily if k.startswith("temperature_2m_mean_member")] or ["temperature_2m_mean"]
    per_member = [monthly_from_daily(dates, daily[m]) for m in members]
    out = {}
    for month in per_member[0]:
        vals = [pm[month]["cdd"] * 30.4 / pm[month]["days"] for pm in per_member if month in pm and pm[month]["days"] >= 20]
        if not vals:
            continue
        vals.sort()
        out[month] = {"cdd_mean": round(sum(vals) / len(vals), 2),
                      "cdd_p10": round(vals[int(0.1 * (len(vals) - 1))], 2),
                      "cdd_p90": round(vals[int(0.9 * (len(vals) - 1))], 2),
                      "members": len(vals)}
    return out
