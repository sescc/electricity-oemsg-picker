"""Fit all models from data/snapshots/datasets.json and write site/data/model.json."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import numpy as np

from scraper.sources.tariff import merge_history

from . import models as M

ROOT = Path(__file__).resolve().parents[1]
GST = 1.09
DWELLING_KEYS = {
    "1-room / 2-room": "hdb12", "3-room": "hdb3", "4-room": "hdb4", "5-room and Executive": "hdb5",
    "Private Apartments and Condominiums": "condo", "Landed Properties": "landed", "Overall": "overall",
}


def r(x, n=4):
    return None if x is None else round(float(x), n)


def main() -> None:
    ds = json.loads((ROOT / "data" / "snapshots" / "datasets.json").read_text(encoding="utf-8"))
    plans = json.loads((ROOT / "site" / "data" / "plans.json").read_text(encoding="utf-8"))
    ses, weather = ds["ses"], ds["weather_history"]

    # ---------------- weather
    clim = M.cdd_climatology(weather, years=10)
    seasonal = ds.get("weather_seasonal") or {}
    fc_months = sorted(seasonal)
    weather_fc = {}
    if fc_months:
        raw = {m: seasonal[m]["cdd_mean"] / 30.4 for m in fc_months}
        # Level bias of the raw seasonal model cannot be estimated without hindcasts, so the level is
        # anchored to the recent climatology and only the forecast's month-to-month shape is kept.
        bias = np.mean([raw[m] - clim[int(m[5:])] for m in fc_months])
        for m in fc_months:
            s = seasonal[m]
            weather_fc[m] = {"cdd_per_day": r(raw[m] - bias), "raw_cdd_per_day": r(raw[m]),
                             "p10": r(s["cdd_p10"] / 30.4 - bias), "p90": r(s["cdd_p90"] / 30.4 - bias),
                             "members": s["members"]}

    # ---------------- consumption
    consumption = {}
    for name, key in DWELLING_KEYS.items():
        series = ses["kwh_per_account"].get(name) or {}
        if len(series) < 36:
            continue
        fit = M.fit_consumption(series, weather)
        consumption[key] = {
            "label": name, "cdd_coef": r(fit["cdd_coef"]), "r2": fit["r2"], "n": fit["n"],
            "sigma": r(fit["sigma"]), "fitted_from": fit["fitted_from"], "fitted_to": fit["fitted_to"],
            "typical_monthly_kwh": round(fit["last_12m_avg_kwh"], 1),
            "coefs": [{k: (r(v) if isinstance(v, float) else v) for k, v in c.items()} for c in fit["coefs"]],
            "series": fit["series"][-48:],
        }

    # ---------------- tariff
    history_m = merge_history(ses["tariff_ex_gst"], ds.get("tariff_datagov") or {})
    cur = plans.get("regulated_tariff") or {}
    tds = M.build_tariff_dataset(history_m, ses["usep"], ses["peak_demand_mw"], weather)
    last_q = max(tds["tariff"])
    if cur.get("cents_incl_gst") and cur.get("quarter"):
        qlabel = cur["quarter"].replace(" ", "")          # "Q3 2026" -> "Q32026"
        q = f"{qlabel[2:]}Q{qlabel[1]}"
        if q > last_q:
            tds["tariff"][q] = round(cur["cents_incl_gst"] / GST, 2)
            last_q = q
    fit = M.fit_tariff(tds)
    bt = M.backtest(tds)
    start_ex = tds["tariff"][last_q]
    prev_ex = tds["tariff"][M.next_quarter(last_q, -1)]
    horizon = 12
    # Model selection by out-of-sample error, not in-sample fit: the exogenous inputs are
    # significant in sample but may not improve one-quarter-ahead forecasts.
    chosen = min(bt["rmse_log"], key=bt["rmse_log"].get)
    paths = M.simulate_tariff(fit, tds, last_q, start_ex, prev_ex, horizon=horizon, mode=chosen)
    chain = M.markov_chain(paths * GST, start_ex * GST, k=5)
    qs = sorted(tds["tariff"])
    vol = M.ewma_vol([tds["tariff"][q] for q in qs])
    dlog = np.diff(np.log([tds["tariff"][q] for q in qs]))

    def coef_table(f):
        return [{"name": c["name"], "coef": r(c["coef"], 5), "se": r(c["se"], 5), "t": r(c["t"], 3),
                 "p": r(c["p"], 4)} for c in f["coefs"]]

    model = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "sources": ds.get("sources", {}),
        "gst_factor": GST,
        "weather": {
            "cdd_base_c": 24.0,
            "climatology_cdd_per_day": {str(k): r(v) for k, v in clim.items()},
            "forecast": weather_fc,
            "recent": [{"month": m, "cdd_per_day": r(weather[m]["cdd"] / weather[m]["days"]),
                        "mean_temp": weather[m]["mean_temp"]} for m in sorted(weather)[-36:]],
        },
        "consumption": consumption,
        "tariff": {
            "history": [{"quarter": q, "ex_gst": tds["tariff"][q], "incl_gst": round(tds["tariff"][q] * GST, 2)}
                        for q in qs],
            "current_quarter": last_q,
            "current_incl_gst": round(start_ex * GST, 2),
            "model": {
                "equation": "dy_t = c + phi*dy_{t-1} + g*(y_{t-1}-mean) + b1*dln(USEP)_{t-1} + b2*dln(peak demand)_{t-1} + b3*CDD_anom_{t-1} + e_t",
                "n": fit["full"]["n"], "r2": r(fit["full"]["r2"]), "adj_r2": r(fit["full"]["adj_r2"]),
                "sigma": r(fit["full"]["sigma"]), "coefs": coef_table(fit["full"]),
                "ar_only": {"r2": r(fit["ar_only"]["r2"]), "adj_r2": r(fit["ar_only"]["adj_r2"]),
                            "sigma": r(fit["ar_only"]["sigma"])},
                "f_test_exog": {k: r(v) for k, v in fit["f_test_exog"].items()},
                "sample": [fit["quarters"][0], fit["quarters"][-1]],
            },
            "backtest": {**bt, "rmse_log": {k: r(v) for k, v in bt["rmse_log"].items()},
                         "coverage_80": r(bt["coverage_80"], 3)},
            "simulation_model": chosen,
            "volatility": {"hist_sd_quarterly_dlog": r(float(np.std(dlog))), "ewma_latest": r(vol[-1]),
                           "ewma": [{"quarter": q, "vol": r(v)} for q, v in zip(qs[1:], vol)][-40:]},
            "fan_incl_gst": [{k: (r(v, 3) if isinstance(v, float) else v) for k, v in row.items()}
                             for row in M.fan(paths * GST, M.next_quarter(last_q))],
            # built on GST-inclusive paths, so levels/edges are cents/kWh incl. GST
            "markov": {"k": chain["k"], "levels_incl_gst": [r(x, 3) for x in chain["levels"]],
                       "edges_incl_gst": [r(x, 3) for x in chain["edges"]],
                       "transition": [[r(p, 5) for p in row] for row in chain["transition"]],
                       "initial": [r(p, 5) for p in chain["initial"]], "start_bin": chain["start_bin"]},
            "n_paths": int(paths.shape[0]), "horizon_quarters": horizon,
        },
    }
    out = ROOT / "site" / "data" / "model.json"
    out.write_text(json.dumps(model, indent=1) + "\n", encoding="utf-8")
    m = model["tariff"]["model"]
    print(f"tariff model n={m['n']} R2={m['r2']} adjR2={m['adj_r2']} vs AR-only adjR2={m['ar_only']['adj_r2']} "
          f"F(exog)={m['f_test_exog']['F']}; backtest RMSE {model['tariff']['backtest']['rmse_log']} "
          f"cov80={model['tariff']['backtest']['coverage_80']} -> simulating with {chosen}")
    fan_last = model["tariff"]["fan_incl_gst"][-1]
    print(f"fan {fan_last['quarter']}: p10={fan_last['p10']:.2f} p50={fan_last['p50']:.2f} p90={fan_last['p90']:.2f}; "
          f"markov levels {model['tariff']['markov']['levels_incl_gst']}")
    for k, c in consumption.items():
        print(f"consumption {k:7s} cdd_coef={c['cdd_coef']} R2={c['r2']} typical={c['typical_monthly_kwh']}")


if __name__ == "__main__":
    main()
