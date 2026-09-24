"""Statistical models, fitted in CI and exported as JSON for the browser.

1. Consumption (weather -> kWh):  per dwelling type,
       ln(kWh/day)_t = a + b * CDD/day_t + c * trend_t + d * covid_t + e_t
   b is the % change in daily use per extra cooling degree (°C above 24) per day.

2. Regulated tariff (quarterly, demand/weather/wholesale as exogenous inputs):
       dy_t = c + phi*dy_{t-1} - kappa*(y_{t-1} - mean) + b1*du_{t-1} + b2*dd_{t-1} + b3*w_{t-1} + e_t
   y = ln tariff (ex GST), u = ln USEP (wholesale), d = ln peak system demand, w = CDD anomaly.
   Residential plans are fixed-rate or discount-off-tariff, so wholesale/weather volatility reaches
   households only through this quarterly tariff path.

3. Monte-Carlo tariff paths (joint block bootstrap of exogenous shocks and residuals) ->
   fan chart + a K-state Markov chain used by the MDP in the browser.
"""
from __future__ import annotations

import calendar
import math

import numpy as np

from .ols import ols

COVID = ("2020-04", "2021-12")  # circuit breaker + work-from-home period
FIT_FROM = "2012-01"


def days_in(month: str) -> int:
    y, m = map(int, month.split("-"))
    return calendar.monthrange(y, m)[1]


def quarter_of(month: str) -> str:
    y, m = month.split("-")
    return f"{y}Q{(int(m) - 1) // 3 + 1}"


def month_of_quarter(q: str) -> str:
    y, n = q.split("Q")
    return f"{y}-{(int(n) - 1) * 3 + 1:02d}"


def next_quarter(q: str, k: int = 1) -> str:
    y, n = map(int, q.split("Q"))
    idx = y * 4 + (n - 1) + k
    return f"{idx // 4}Q{idx % 4 + 1}"


# ---------------------------------------------------------------- consumption
def cdd_climatology(weather: dict[str, dict], years: int = 10) -> dict[int, float]:
    """Mean CDD per day for each calendar month over the last `years` full years."""
    last_year = max(int(k[:4]) for k in weather if k.endswith("-12"))
    out = {}
    for m in range(1, 13):
        vals = [weather[f"{y}-{m:02d}"]["cdd"] / weather[f"{y}-{m:02d}"]["days"]
                for y in range(last_year - years + 1, last_year + 1) if f"{y}-{m:02d}" in weather]
        out[m] = float(np.mean(vals))
    return out


def fit_consumption(kwh: dict[str, float], weather: dict[str, dict]) -> dict:
    months = sorted(m for m in kwh if m >= FIT_FROM and m in weather)
    y = np.array([math.log(kwh[m] / days_in(m)) for m in months])
    cddpd = np.array([weather[m]["cdd"] / weather[m]["days"] for m in months])
    trend = np.array([(int(m[:4]) - 2012) + (int(m[5:]) - 1) / 12 for m in months])
    covid = np.array([1.0 if COVID[0] <= m <= COVID[1] else 0.0 for m in months])
    X = np.column_stack([np.ones_like(y), cddpd, trend, covid])
    fit = ols(y, X, ["intercept", "cdd_per_day", "trend_per_year", "covid_wfh"])
    return {
        "n": fit["n"], "r2": round(fit["r2"], 4), "sigma": fit["sigma"],
        "coefs": fit["coefs"], "cdd_coef": float(fit["beta"][1]),
        "fitted_from": months[0], "fitted_to": months[-1],
        "last_12m_avg_kwh": float(np.mean([kwh[m] for m in months[-12:]])),
        "series": [{"month": m, "kwh": kwh[m], "fitted": round(math.exp(f) * days_in(m), 1)}
                   for m, f in zip(months, X @ fit["beta"])],
    }


# ---------------------------------------------------------------- tariff
def quarterly(series: dict[str, float], how: str = "first") -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for m, v in sorted(series.items()):
        buckets.setdefault(quarter_of(m), []).append(v)
    return {q: (vs[0] if how == "first" else float(np.mean(vs))) for q, vs in buckets.items()
            if how == "first" or len(vs) == 3}


def build_tariff_dataset(tariff_m: dict[str, float], usep_m: dict[str, float],
                         demand_m: dict[str, float], weather: dict[str, dict]) -> dict:
    tq = quarterly(tariff_m, "first")
    uq = quarterly(usep_m, "mean")
    dq = quarterly(demand_m, "mean")
    clim = cdd_climatology(weather, years=15)
    wq_raw = {}
    for m, w in weather.items():
        wq_raw.setdefault(quarter_of(m), []).append(w["cdd"] / w["days"] - clim[int(m[5:])])
    wq = {q: float(np.mean(v)) for q, v in wq_raw.items() if len(v) == 3}
    return {"tariff": tq, "usep": uq, "demand": dq, "cdd_anom": wq}


def _design(ds: dict, quarters: list[str], mean_y: float):
    rows, ys, used = [], [], []
    for q in quarters:
        p1, p2 = next_quarter(q, -1), next_quarter(q, -2)
        need = [(ds["tariff"], q), (ds["tariff"], p1), (ds["tariff"], p2), (ds["usep"], p1), (ds["usep"], p2),
                (ds["demand"], p1), (ds["demand"], p2), (ds["cdd_anom"], p1)]
        if not all(k in d for d, k in need):
            continue
        y0, y1, y2 = (math.log(ds["tariff"][x]) for x in (q, p1, p2))
        du = math.log(ds["usep"][p1]) - math.log(ds["usep"][p2])
        dd = math.log(ds["demand"][p1]) - math.log(ds["demand"][p2])
        rows.append([1.0, y1 - y2, y1 - mean_y, du, dd, ds["cdd_anom"][p1]])
        ys.append(y0 - y1)
        used.append(q)
    return np.array(ys), np.array(rows), used


TARIFF_TERMS = ["intercept", "dy_lag1", "level_gap_lag1", "d_ln_usep_lag1", "d_ln_demand_lag1", "cdd_anom_lag1"]


def fit_tariff(ds: dict) -> dict:
    qs = sorted(ds["tariff"])
    mean_y = float(np.mean([math.log(ds["tariff"][q]) for q in qs]))
    y, X, used = _design(ds, qs, mean_y)
    full = ols(y, X, TARIFF_TERMS)
    ar = ols(y, X[:, :3], TARIFF_TERMS[:3])
    # nested-model F test: do the exogenous inputs (wholesale, demand, weather) add information?
    rss_f, rss_r = float(full["resid"] @ full["resid"]), float(ar["resid"] @ ar["resid"])
    q_ = X.shape[1] - 3
    F = ((rss_r - rss_f) / q_) / (rss_f / (len(y) - X.shape[1]))
    return {"full": full, "ar_only": ar, "mean_log_tariff": mean_y, "quarters": used,
            "X": X, "y": y, "f_test_exog": {"F": F, "df1": q_, "df2": len(y) - X.shape[1]}}


def backtest(ds: dict, start: str = "2014Q1") -> dict:
    """Expanding-window one-quarter-ahead forecasts: full model vs AR-only vs random walk."""
    qs = sorted(ds["tariff"])
    errs = {"model": [], "ar_only": [], "random_walk": []}
    covered = 0
    for i, q in enumerate(qs):
        if q < start:
            continue
        train = {k: {kk: vv for kk, vv in v.items() if kk < q} for k, v in ds.items()}
        try:
            fit = fit_tariff(train)
        except (np.linalg.LinAlgError, ValueError):
            continue
        y, X, used = _design(ds, [q], fit["mean_log_tariff"])
        if not used:
            continue
        pred_full = float(X[0] @ fit["full"]["beta"])
        pred_ar = float(X[0, :3] @ fit["ar_only"]["beta"])
        errs["model"].append(y[0] - pred_full)
        errs["ar_only"].append(y[0] - pred_ar)
        errs["random_walk"].append(y[0])
        covered += abs(y[0] - pred_full) <= 1.2816 * fit["full"]["sigma"]
    n = len(errs["model"])
    rmse = {k: float(np.sqrt(np.mean(np.square(v)))) for k, v in errs.items()}
    return {"n": n, "from": start, "rmse_log": rmse, "coverage_80": covered / n if n else None}


def simulate_tariff(fit: dict, ds: dict, start_quarter: str, start_value_ex: float, prev_value_ex: float,
                    horizon: int = 12, n_paths: int = 4000, block: int = 4, seed: int = 7,
                    mode: str = "full") -> np.ndarray:
    """Paths of the ex-GST tariff for quarters start+1 .. start+horizon.

    Shocks are drawn from historical quarters in blocks of `block`, which keeps the joint
    behaviour of wholesale price, demand and weather and some persistence (a fuel shock lasts
    more than a quarter). `mode` picks the dynamics: the full ARX model, the AR-only model, or
    a random walk; build.py chooses the one with the lowest out-of-sample error.
    """
    rng = np.random.default_rng(seed)
    X = fit["X"]
    if mode == "full":
        beta = fit["full"]["beta"]
        exog_contrib = X[:, 3:] @ beta[3:]       # b1*du + b2*dd + b3*w for each historical quarter
        # everything not explained by own dynamics; not re-centred, because the intercept was
        # estimated jointly with the exogenous terms and relies on their historical mean
        shocks = exog_contrib + fit["full"]["resid"]
    elif mode == "ar_only":
        beta = fit["ar_only"]["beta"]
        shocks = fit["ar_only"]["resid"]
    elif mode == "random_walk":
        beta = np.zeros(3)
        shocks = fit["y"]                         # historical quarterly log changes, incl. their drift
    else:
        raise ValueError(mode)
    T = len(shocks)
    paths = np.empty((n_paths, horizon))
    for p in range(n_paths):
        y1, y0 = math.log(start_value_ex), math.log(prev_value_ex)
        idx = []
        while len(idx) < horizon:
            s = rng.integers(0, T - block + 1)
            idx.extend(range(s, s + block))
        for h in range(horizon):
            dy_prev = y1 - y0
            mu = beta[0] + beta[1] * dy_prev + beta[2] * (y1 - fit["mean_log_tariff"])
            y_new = y1 + mu + shocks[idx[h]]
            y0, y1 = y1, y_new
            paths[p, h] = math.exp(y_new)
    return paths


def markov_chain(paths: np.ndarray, start_value: float, k: int = 5) -> dict:
    """Discretise simulated paths into k tariff levels; estimate a homogeneous transition matrix.

    k is kept small on purpose: ~80 quarterly observations cannot support a finer chain.
    """
    pooled = paths.ravel()
    edges = np.quantile(pooled, [i / k for i in range(1, k)])
    bins = np.digitize(paths, edges)
    levels = [float(np.median(pooled[np.digitize(pooled, edges) == i])) for i in range(k)]
    counts = np.full((k, k), 0.5)                 # Jeffreys-style smoothing
    for row in bins:
        for a, b in zip(row[:-1], row[1:]):
            counts[a, b] += 1
    P = counts / counts.sum(axis=1, keepdims=True)
    init = np.bincount(bins[:, 0], minlength=k) / len(bins)
    return {"k": k, "edges": edges.tolist(), "levels": levels, "transition": P.tolist(),
            "initial": init.tolist(), "start_bin": int(np.digitize([start_value], edges)[0])}


def fan(paths: np.ndarray, first_quarter: str) -> list[dict]:
    qs = [next_quarter(first_quarter, h) for h in range(paths.shape[1])]
    out = []
    for h, q in enumerate(qs):
        col = paths[:, h]
        out.append({"quarter": q, **{f"p{p}": float(np.percentile(col, p)) for p in (5, 10, 25, 50, 75, 90, 95)},
                    "mean": float(col.mean())})
    return out


def ewma_vol(series: list[float], lam: float = 0.9) -> list[float]:
    """EWMA volatility of log changes (RiskMetrics-style), per quarter."""
    r = np.diff(np.log(series))
    v = float(np.var(r[:8])) if len(r) >= 8 else float(np.var(r))
    out = []
    for x in r:
        v = lam * v + (1 - lam) * x * x
        out.append(math.sqrt(v))
    return out
