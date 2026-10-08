"""analysis.build when the official tariff lags the retailer quotes, and when the build itself fails.

Regression: on 2026-10-01 the quote moved to Q4 while the official series still ended at 2026Q2, and
`prev_ex = tariff[2026Q3]` raised KeyError, failing the daily refresh.
"""
import json
import math

import numpy as np
import pytest

from analysis import models as M
from analysis.build import build_or_keep, main
from fixtures_build import quote, write_root

Q3_REC = {"cents_incl_gst": 34.78, "observed_at": "2026-09-30T08:00:00+00:00", "sources": ["pacificlight"]}
Q4_NOW = quote("Q4 2026", 31.16)


def read_model(root):
    return json.loads((root / "site" / "data" / "model.json").read_text(encoding="utf-8"))


def read_status(root):
    return json.loads((root / "site" / "data" / "model_status.json").read_text(encoding="utf-8"))


def adjacent_changes(history):
    by_q = {h["quarter"]: h["ex_gst"] for h in history}
    return [(q, math.log(v) - math.log(by_q[M.next_quarter(q, -1)])) for q, v in by_q.items()
            if M.next_quarter(q, -1) in by_q]


def test_first_of_october_regression_recorded_q3_quote_bridges_the_gap(tmp_path):
    root = write_root(tmp_path, quotes={"2026Q3": Q3_REC}, current=Q4_NOW)
    main(root)
    t = read_model(root)["tariff"]
    assert t["current_quarter"] == "2026Q4" and t["current_incl_gst"] == 31.16
    rows = {h["quarter"]: h for h in t["history"]}
    assert rows["2026Q3"]["source"] == "retailer_quote" and rows["2026Q3"]["incl_gst"] == 34.78
    assert rows["2026Q4"]["source"] == "retailer_quote" and rows["2026Q2"]["source"] == "official"
    assert t["history_gaps"] == []
    assert t["fan_incl_gst"][0]["quarter"] == "2027Q1"


def test_missing_quarter_is_a_reported_gap_not_an_interpolation(tmp_path):
    root = write_root(tmp_path, current=Q4_NOW)          # no tariff_quotes.json at all
    main(root)
    t = read_model(root)["tariff"]
    quarters = [h["quarter"] for h in t["history"]]
    assert t["history_gaps"] == ["2026Q3"] and "2026Q3" not in quarters
    assert t["current_quarter"] == "2026Q4" and t["current_incl_gst"] == 31.16
    # nothing may be measured across the gap
    ewma_quarters = [e["quarter"] for e in t["volatility"]["ewma"]]
    assert "2026Q4" not in ewma_quarters and "2026Q2" in ewma_quarters
    changes = adjacent_changes(t["history"])
    assert "2026Q4" not in [q for q, _ in changes]
    sd = float(np.std([c for _, c in changes]))
    assert t["volatility"]["hist_sd_quarterly_dlog"] == pytest.approx(sd, abs=1e-4)
    assert t["volatility"]["ewma_latest"] is not None and t["volatility"]["ewma_latest"] > 0


def test_exact_pre_fix_failure_input_no_longer_raises(tmp_path):
    # official ends 2026-06, no quotes file, live quote is Q4: this raised KeyError('2026Q3')
    root = write_root(tmp_path, official_end="2026-06", current=Q4_NOW)
    assert not (root / "data" / "snapshots" / "tariff_quotes.json").exists()
    main(root)
    assert read_model(root)["tariff"]["current_quarter"] == "2026Q4"


def test_official_series_alone_still_builds_when_there_is_no_live_quote(tmp_path):
    root = write_root(tmp_path, current=None)
    main(root)
    t = read_model(root)["tariff"]
    assert t["current_quarter"] == "2026Q2" and t["history_gaps"] == []
    assert {h["source"] for h in t["history"]} == {"official"}


def test_live_quote_overrides_a_recorded_one_for_the_same_quarter(tmp_path):
    root = write_root(tmp_path, quotes={"2026Q3": Q3_REC}, current=quote("Q3 2026", 35.00))
    main(root)
    t = read_model(root)["tariff"]
    assert t["current_quarter"] == "2026Q3" and t["current_incl_gst"] == 35.0


# ------------------------------------------------------------------ extend_history
def test_extend_history_precedence_sources_and_gaps():
    official = {"2026Q1": 20.0, "2026Q2": 21.0}
    out, src, gaps = M.extend_history(official, {"2026Q3": {"cents_incl_gst": 21.8}}, None, 1.09)
    assert out == {"2026Q1": 20.0, "2026Q2": 21.0, "2026Q3": 20.0} and gaps == []
    assert src == {"2026Q1": "official", "2026Q2": "official", "2026Q3": "retailer_quote"}

    # recorded quotes never replace official quarters
    out, _, _ = M.extend_history(official, {"2026Q2": {"cents_incl_gst": 99.0}}, None, 1.09)
    assert out["2026Q2"] == 21.0

    # a current quote older than a recorded one is ignored; same quarter -> current wins
    quotes = {"2026Q3": {"cents_incl_gst": 21.8}, "2026Q4": {"cents_incl_gst": 22.89}}
    out, _, gaps = M.extend_history(official, quotes, {"cents_incl_gst": 25.0, "quarter": "Q3 2026"}, 1.09)
    assert out["2026Q3"] == 20.0 and out["2026Q4"] == 21.0 and gaps == []
    out, _, _ = M.extend_history(official, quotes, {"cents_incl_gst": 25.0, "quarter": "Q4 2026"}, 1.09)
    assert out["2026Q4"] == round(25.0 / 1.09, 2)

    # a hole between the official end and the newest quote is reported and left empty
    out, _, gaps = M.extend_history(official, {"2026Q4": {"cents_incl_gst": 22.89}}, None, 1.09)
    assert gaps == ["2026Q3"] and "2026Q3" not in out


def test_adjacent_dlog_skips_changes_across_a_gap_and_ewma_survives_it():
    t = {"2026Q1": 20.0, "2026Q2": 22.0, "2026Q4": 30.0}
    ch = M.adjacent_dlog(t)
    assert [q for q, _ in ch] == ["2026Q2"] and ch[0][1] == pytest.approx(math.log(1.1))
    assert len(M.ewma_vol([c for _, c in ch])) == 1
    assert M.ewma_vol([]) == [] and M.adjacent_dlog({"2026Q1": 1.0, "2026Q3": 2.0}) == []


# ------------------------------------------------------------------ build_or_keep
def test_build_or_keep_success_writes_ok_status(tmp_path):
    root = write_root(tmp_path, quotes={"2026Q3": Q3_REC}, current=Q4_NOW)
    assert build_or_keep(root) == 0
    st = read_status(root)
    assert st["state"] == "ok" and st["model_as_of"] == read_model(root)["generated_at"]
    assert "error" not in st and st["checked_at"] >= st["model_as_of"]    # checked after the build, not before


def test_build_or_keep_keeps_previous_model_when_inputs_are_corrupt(tmp_path, capsys):
    root = write_root(tmp_path, current=Q4_NOW)
    model_path = root / "site" / "data" / "model.json"
    previous = b'{"generated_at": "2026-09-01T00:00:00+00:00", "marker": "old model"}\n'
    model_path.write_bytes(previous)
    (root / "data" / "snapshots" / "datasets.json").write_text("{ not json", encoding="utf-8")
    assert build_or_keep(root) == 0                       # never fails the pipeline
    assert model_path.read_bytes() == previous            # untouched
    st = read_status(root)
    assert st["state"] == "stale" and st["model_as_of"] == "2026-09-01T00:00:00+00:00"
    assert st["error"].startswith("JSONDecodeError") and len(st["error"]) <= 300
    assert "Traceback" in capsys.readouterr().err         # the traceback is still printed for the CI log


def test_build_or_keep_with_no_previous_model_still_exits_zero(tmp_path):
    root = write_root(tmp_path, current=Q4_NOW)
    (root / "data" / "snapshots" / "datasets.json").unlink()
    assert build_or_keep(root) == 0
    st = read_status(root)
    assert st["state"] == "stale" and st["model_as_of"] is None and "FileNotFoundError" in st["error"]
    assert not (root / "site" / "data" / "model.json").exists()


def test_build_or_keep_keeps_previous_model_when_a_model_step_fails(tmp_path):
    root = write_root(tmp_path, current=Q4_NOW)
    assert build_or_keep(root) == 0
    first = (root / "site" / "data" / "model.json").read_bytes()
    # too little history for the tariff regressions -> the fit raises somewhere inside main()
    write_root(root, official_end="2006-12", exog_end="2006-12", weather_end="2006-12", kwh_end="2006-12")
    assert build_or_keep(root) == 0
    assert (root / "site" / "data" / "model.json").read_bytes() == first
    assert read_status(root)["state"] == "stale"
