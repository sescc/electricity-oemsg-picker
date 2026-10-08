"""analysis.build.build_model: the composition rules of the Analysis component (ARCHITECTURE section 6).

Each test breaks if its rule is broken: where a natural fixture would satisfy a rule by accident
(selection, anchoring, GST scaling) the test forces the situation (a stubbed backtest, a biased
seasonal forecast, a known set of simulated paths).
"""
import copy
import json
import pathlib

import numpy as np
import pytest

from analysis import build, models as M
from analysis.build import build_model
from common.tariff import GST_FACTOR
from fixtures_build import make_datasets, months, quote, write_root

AT = "2026-10-08T00:00:00+00:00"
Q4 = quote("Q4 2026", 31.16)


def inputs(current=Q4, quotes=None, **dataset_kw):
    return make_datasets(**dataset_kw), {"regulated_tariff": current}, quotes or {}


def model_of(**kw):
    ds, plans, quotes = inputs(**kw)
    return build_model(ds, plans, quotes, generated_at=AT)


@pytest.fixture(scope="module")
def baseline():
    return model_of()


# ------------------------------------------------------------------ build_model is pure
def test_build_model_does_no_file_io_and_leaves_its_inputs_alone(monkeypatch):
    ds, plans, quotes = inputs(quotes={"2026Q3": {"cents_incl_gst": 34.78}})
    before = copy.deepcopy((ds, plans, quotes))

    def boom(*a, **k):
        raise AssertionError("build_model touched the file system")

    for name in ("read_text", "write_text", "read_bytes", "write_bytes", "open", "mkdir"):
        monkeypatch.setattr(pathlib.Path, name, boom)
    model = build_model(ds, plans, quotes, generated_at=AT)
    assert model["generated_at"] == AT
    assert (ds, plans, quotes) == before


def test_generated_at_defaults_to_now(baseline):
    ds, plans, quotes = inputs()
    assert build_model(ds, plans, quotes)["generated_at"] > "2026-10-08"


def test_main_writes_exactly_what_build_model_returns(tmp_path):
    root = write_root(tmp_path, current=Q4)
    model = build.main(root)
    written = json.loads((root / "site" / "data" / "model.json").read_text(encoding="utf-8"))
    ds = json.loads((root / "data" / "snapshots" / "datasets.json").read_text(encoding="utf-8"))
    plans = json.loads((root / "site" / "data" / "plans.json").read_text(encoding="utf-8"))
    assert written == json.loads(json.dumps(model))
    assert written == json.loads(json.dumps(build_model(ds, plans, {}, generated_at=model["generated_at"])))


def test_main_refuses_nan_and_leaves_no_model_file(tmp_path, monkeypatch):
    root = write_root(tmp_path, current=Q4)
    monkeypatch.setattr(build, "build_model", lambda *a, **k: {"generated_at": AT, "x": float("nan")})
    with pytest.raises(ValueError):
        build.main(root)
    assert not (root / "site" / "data" / "model.json").exists()


# ------------------------------------------------------------------ rule 1: chosen = argmin backtest
def test_simulation_model_is_the_argmin_of_the_backtest(baseline):
    t = baseline["tariff"]
    rmse = t["backtest"]["rmse_log"]
    assert set(rmse) == {"model", "ar_only", "random_walk"}
    assert t["simulation_model"] == min(rmse, key=rmse.get)


@pytest.mark.parametrize("winner", ["model", "ar_only", "random_walk"])
def test_each_backtest_winner_is_the_mode_actually_simulated(monkeypatch, winner):
    rmse = {k: (0.01 if k == winner else 0.05 + i / 100) for i, k in enumerate(["model", "ar_only", "random_walk"])}
    monkeypatch.setattr(M, "backtest", lambda ds: {"n": 9, "from": "2014Q1", "rmse_log": rmse, "coverage_80": 0.8})
    modes = []
    real = M.simulate_tariff
    monkeypatch.setattr(M, "simulate_tariff", lambda *a, **k: modes.append(k["mode"]) or real(*a, **k))
    model = model_of()
    # (the ARX candidate is named "model" by the backtest and "full" by simulate_tariff: it used to raise)
    assert model["tariff"]["simulation_model"] == winner and modes == [winner]
    assert model["tariff"]["n_paths"] == 4000


# ------------------------------------------------------------------ rule 4: seasonal level anchored
def test_seasonal_forecast_is_anchored_to_climatology_and_keeps_its_shape():
    ds, plans, quotes = inputs()
    for rec in ds["weather_seasonal"].values():                 # raw forecast 1 CDD/day too hot
        rec["cdd_mean"] += 30.4
        rec["cdd_p10"] += 30.4
        rec["cdd_p90"] += 30.4
    w = build_model(ds, plans, quotes, generated_at=AT)["weather"]
    fc, clim = w["forecast"], {int(k): v for k, v in w["climatology_cdd_per_day"].items()}
    assert len(fc) == 6
    # precondition: without anchoring the level would be about 1 CDD/day off
    assert np.mean([fc[m]["raw_cdd_per_day"] - clim[int(m[5:])] for m in fc]) > 0.8
    # rule: after anchoring the mean difference to climatology is zero
    assert np.mean([fc[m]["cdd_per_day"] - clim[int(m[5:])] for m in fc]) == pytest.approx(0, abs=1e-3)
    # shape: month-to-month pattern (and the ensemble spread) is the raw one, shifted by one constant
    shift = {fc[m]["raw_cdd_per_day"] - fc[m]["cdd_per_day"] for m in fc}
    assert max(shift) - min(shift) < 2e-4 and 0.8 < np.mean(list(shift)) < 1.2
    for m, rec in fc.items():
        raw = ds["weather_seasonal"][m]
        assert rec["raw_cdd_per_day"] == pytest.approx(raw["cdd_mean"] / 30.4, abs=1e-4)
        assert rec["p90"] - rec["cdd_per_day"] == pytest.approx((raw["cdd_p90"] - raw["cdd_mean"]) / 30.4, abs=2e-4)
        assert rec["cdd_per_day"] - rec["p10"] == pytest.approx((raw["cdd_mean"] - raw["cdd_p10"]) / 30.4, abs=2e-4)


def test_no_seasonal_forecast_gives_an_empty_forecast_not_an_error():
    ds, plans, quotes = inputs()
    ds["weather_seasonal"] = None
    assert build_model(ds, plans, quotes, generated_at=AT)["weather"]["forecast"] == {}


# ------------------------------------------------------------------ rule 5: GST-inclusive outputs
def test_fan_and_markov_levels_are_ex_gst_paths_times_gst_factor(monkeypatch):
    rng = np.random.default_rng(3)
    paths = 28.0 * np.exp(np.cumsum(rng.normal(0.005, 0.04, (600, 12)), axis=1))   # ex-GST, known
    monkeypatch.setattr(M, "simulate_tariff", lambda *a, **k: paths)
    t = model_of()["tariff"]
    assert t["n_paths"] == 600 and len(t["fan_incl_gst"]) == 12
    for h, row in enumerate(t["fan_incl_gst"]):
        for p in (5, 10, 25, 50, 75, 90, 95):
            assert row[f"p{p}"] == pytest.approx(np.percentile(paths[:, h], p) * GST_FACTOR, abs=1.5e-3)
        assert row["mean"] == pytest.approx(paths[:, h].mean() * GST_FACTOR, abs=1.5e-3)
    ex_chain = M.markov_chain(paths, 28.0, k=5)
    assert t["markov"]["levels_incl_gst"] == pytest.approx([x * GST_FACTOR for x in ex_chain["levels"]], abs=1.5e-3)
    assert t["markov"]["edges_incl_gst"] == pytest.approx([x * GST_FACTOR for x in ex_chain["edges"]], abs=1.5e-3)


def test_history_and_current_tariff_are_gst_inclusive(baseline):
    t, gf = baseline["tariff"], baseline["gst_factor"]
    assert gf == GST_FACTOR
    official = [h for h in t["history"] if h["source"] == "official"]
    assert len(official) > 50
    for h in official:
        assert h["incl_gst"] == pytest.approx(h["ex_gst"] * GST_FACTOR, abs=0.0051)
    # the quote-sourced current quarter is published exactly as quoted
    assert t["current_quarter"] == "2026Q4" and t["current_incl_gst"] == 31.16


def test_fan_starts_at_the_quarter_after_the_current_one_and_is_ordered(baseline):
    fan = baseline["tariff"]["fan_incl_gst"]
    assert fan[0]["quarter"] == "2027Q1"
    for row in fan:
        assert row["p5"] <= row["p10"] <= row["p25"] <= row["p50"] <= row["p75"] <= row["p90"] <= row["p95"]


# ------------------------------------------------------------------ rule 6: < 36 months omitted
def test_dwelling_with_fewer_than_36_months_is_omitted_and_36_is_kept():
    ds, plans, quotes = inputs()
    overall = ds["ses"]["kwh_per_account"]["Overall"]
    span = months("2020-01", "2022-12")                          # spans the COVID dummy, so the fit is identified
    ds["ses"]["kwh_per_account"]["3-room"] = {m: overall[m] for m in span[:35]}
    ds["ses"]["kwh_per_account"]["4-room"] = {m: overall[m] for m in span}
    ds["ses"]["kwh_per_account"]["Landed Properties"] = {}
    c = build_model(ds, plans, quotes, generated_at=AT)["consumption"]
    assert "hdb3" not in c and "landed" not in c and "hdb5" not in c
    assert c["hdb4"]["n"] == 36 and c["overall"]["n"] > 150
    assert 0 < c["overall"]["cdd_coef"] < 0.2                   # the fixture's true value is 0.055


# ------------------------------------------------------------------ rule 2: Markov chain is stochastic
def test_markov_rows_and_initial_distribution_sum_to_one(baseline):
    mk = baseline["tariff"]["markov"]
    assert mk["k"] == 5 and len(mk["transition"]) == 5
    for row in mk["transition"]:
        assert sum(row) == pytest.approx(1, abs=1e-4) and min(row) > 0
    assert sum(mk["initial"]) == pytest.approx(1, abs=1e-4)
    assert mk["levels_incl_gst"] == sorted(mk["levels_incl_gst"])
    assert 0 <= mk["start_bin"] < 5


# ------------------------------------------------------------------ rule 3: reproducible
def test_same_inputs_give_an_identical_model_apart_from_generated_at():
    a = model_of()
    b = model_of()
    assert a == b
    ds, plans, quotes = inputs()
    c = build_model(ds, plans, quotes, generated_at="2030-01-01T00:00:00+00:00")
    assert c["generated_at"] != a["generated_at"]
    assert {k: v for k, v in c.items() if k != "generated_at"} == {k: v for k, v in a.items() if k != "generated_at"}


def test_different_inputs_do_change_the_model(baseline):
    other = model_of(current=quote("Q4 2026", 33.33))
    assert other["tariff"]["current_incl_gst"] == 33.33 != baseline["tariff"]["current_incl_gst"]
    assert other["tariff"]["fan_incl_gst"] != baseline["tariff"]["fan_incl_gst"]
