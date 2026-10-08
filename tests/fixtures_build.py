"""Deterministic synthetic inputs for `analysis.build`, written into a throwaway root.

`write_root(tmp_path, ...)` creates exactly the files `analysis.build.main(root)` reads:

    data/snapshots/datasets.json     ses{tariff_ex_gst, usep, peak_demand_mw, kwh_per_account},
                                     tariff_datagov, weather_history, weather_seasonal
    data/snapshots/tariff_quotes.json   only when `quotes` is given
    site/data/plans.json             regulated_tariff = `current` (None -> null)

Everything is seeded, so the same arguments always give the same series. The data are statistically
plausible rather than real (quarterly random-walk tariff, seasonal CDD, consumption responding to
CDD), which is enough for every model in `analysis.models` to fit.

Parameters let a test move the edges: the last month of the official tariff (`official_end`), of the
wholesale/demand inputs (`exog_end`), of the weather (`weather_end`) and of the consumption series
(`kwh_end`).
"""
from __future__ import annotations

import calendar
import json
import math
from pathlib import Path

import numpy as np


def months(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _after(month: str, k: int) -> str:
    y, m = map(int, month.split("-"))
    idx = y * 12 + (m - 1) + k
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")


def make_datasets(*, official_end="2026-06", exog_end="2026-09", weather_end="2026-09", kwh_end="2026-06",
                  last_official_ex_gst=27.27, datagov=None, seed=11) -> dict:
    rng = np.random.default_rng(seed)

    # weather: CDD/day with a seasonal cycle (hot May-Jun) + noise
    weather = {}
    for m in months("2005-01", weather_end):
        days = calendar.monthrange(int(m[:4]), int(m[5:]))[1]
        cddpd = max(0.1, 3.0 + 1.4 * math.sin(2 * math.pi * (int(m[5:]) - 3) / 12) + rng.normal(0, 0.35))
        weather[m] = {"mean_temp": round(26.5 + cddpd / 2, 3), "cdd": round(cddpd * days, 2), "days": days}

    # tariff: quarterly log random walk, constant within a quarter, rescaled to end on a known value
    tariff_months = months("2005-01", official_end)
    quarters = sorted({f"{m[:4]}Q{(int(m[5:]) - 1) // 3 + 1}" for m in tariff_months})
    logs = np.cumsum(rng.normal(0.01, 0.05, len(quarters)))
    level = {q: math.exp(v - logs[-1]) * last_official_ex_gst for q, v in zip(quarters, logs)}
    tariff = {m: round(level[f"{m[:4]}Q{(int(m[5:]) - 1) // 3 + 1}"], 2) for m in tariff_months}

    # wholesale price and peak demand (monthly)
    ex = months("2005-01", exog_end)
    usep = {m: round(110 + 30 * math.sin(i / 5.0) + rng.normal(0, 8), 2) for i, m in enumerate(ex)}
    demand = {m: round(6500 + 8 * i + 150 * math.sin(i / 6.0) + rng.normal(0, 60), 1) for i, m in enumerate(ex)}

    # household consumption responding to cooling degrees (kWh / account / month)
    kwh = {}
    for i, m in enumerate(months("2012-01", kwh_end)):
        w = weather[m]
        kwh[m] = round(7.0 * w["days"] * math.exp(0.055 * w["cdd"] / w["days"] + 0.001 * i + rng.normal(0, 0.02)), 1)

    # seasonal ensemble forecast for the six months after the weather archive ends
    seasonal = {}
    for k in range(1, 7):
        m = _after(weather_end, k)
        base = (3.0 + 1.4 * math.sin(2 * math.pi * (int(m[5:]) - 3) / 12)) * 30.4
        seasonal[m] = {"cdd_mean": round(base, 2), "cdd_p10": round(base * 0.85, 2),
                       "cdd_p90": round(base * 1.15, 2), "members": 50}

    return {"generated_at": "2026-09-30T00:00:00+00:00", "sources": {},
            "ses": {"tariff_ex_gst": tariff, "usep": usep, "peak_demand_mw": demand,
                    "kwh_per_account": {"Overall": kwh}},
            "tariff_datagov": datagov or {}, "weather_history": weather, "weather_seasonal": seasonal}


def write_root(root: Path, *, quotes: dict | None = None, current: dict | None = None, **dataset_kw) -> Path:
    """Write a minimal project root under `root` and return it. See the module docstring."""
    root = Path(root)
    _dump(root / "data" / "snapshots" / "datasets.json", make_datasets(**dataset_kw))
    if quotes is not None:
        _dump(root / "data" / "snapshots" / "tariff_quotes.json", quotes)
    _dump(root / "site" / "data" / "plans.json",
          {"generated_at": "2026-10-01T00:00:00+00:00", "regulated_tariff": current, "plans": []})
    return root


def quote(quarter: str, cents: float, **extra) -> dict:
    """A `regulated_tariff` block as run.py writes it into plans.json."""
    return {"cents_incl_gst": cents, "quarter": quarter, "agreeing_sources": ["pacificlight"],
            "disagreeing_sources": {}, "n_sources": 1, "observed_at": "2026-10-01T02:00:00+00:00",
            "stale": False, **extra}
