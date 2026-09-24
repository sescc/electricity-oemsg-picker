from pathlib import Path

import numpy as np

from analysis import models as M
from scraper.http import PoliteSession
from scraper.sources.tariff import consensus_current, parse_datagov
from scraper.sources.weather import monthly_from_daily
from scraper.terms import document_text, extract_terms

FX = Path(__file__).parent / "fixtures"


def test_senoko_factsheet_etf_schedule():
    t = extract_terms(document_text((FX / "senoko_fs.pdf").read_bytes()))
    assert t["etf_schedule"] == [{"from_month": 1, "to_month": 12, "fee_sgd": 545.0},
                                 {"from_month": 13, "to_month": 24, "fee_sgd": 327.0}]
    assert t["deposit_waived"] is True
    assert t["contract_months_factsheet"] == 24
    assert t["standard"] is True


def test_standard_flag_from_template_header():
    assert extract_terms("FACT SHEET FOR NON-STANDARD PRICE PLAN Early Termination Charge: $100")["standard"] is False


def test_tuas_factsheet_flat_etf():
    t = extract_terms(document_text((FX / "tuas_dot_fs.pdf").read_bytes()))
    assert t["early_termination_fee_sgd"] == 200.0
    assert t["auto_renews"] is True


def test_pacificlight_html_factsheet_by_dwelling():
    t = extract_terms(document_text((FX / "pacificlight_factsheet.html").read_bytes()))
    assert t["etf_by_dwelling"]["hdb4"] == 320 and t["etf_by_dwelling"]["condo"] == 480
    assert t["deposit_by_dwelling"]["hdb4"] == 160


def test_tariff_consensus_flags_disagreement():
    c = consensus_current({"a": {"regulated_tariff_cents_incl_gst": 34.78, "tariff_quarter": "Q3 2026"},
                           "b": {"regulated_tariff_cents_incl_gst": 34.78}, "c": {"regulated_tariff_cents_incl_gst": 29.11}})
    assert c["cents_incl_gst"] == 34.78 and c["disagreeing_sources"] == {"c": 29.11} and c["quarter"] == "Q3 2026"


def test_datagov_parse():
    payload = {"result": {"records": [{"DataSeries": "Low Tension Supplies - Domestic", "2026Jun": "27.27", "2026Jan": "26.71"},
                                      {"DataSeries": "Other", "2026Jun": "1"}]}}
    assert parse_datagov(payload) == {"2026-01": 26.71, "2026-06": 27.27}


def test_cdd():
    m = monthly_from_daily(["2026-01-01", "2026-01-02"], [26.0, 23.0])
    assert m["2026-01"]["cdd"] == 2.0 and m["2026-01"]["days"] == 2


def test_rate_limiter_spaces_requests():
    slept, t = [], [0.0]
    s = PoliteSession(min_interval=5, sleep=lambda x: slept.append(x), clock=lambda: t[0])
    s._throttle("example.com")
    t[0] = 1.0
    s._throttle("example.com")
    assert slept == [4.0]


def test_markov_chain_rows_sum_to_one_and_simulation_is_reproducible():
    rng = np.random.default_rng(0)
    paths = 30 * np.exp(np.cumsum(rng.normal(0, 0.05, (500, 12)), axis=1))
    ch = M.markov_chain(paths, 30.0, k=5)
    assert np.allclose(np.sum(ch["transition"], axis=1), 1)
    assert sorted(ch["levels"]) == ch["levels"]


def test_quarter_helpers():
    assert M.next_quarter("2026Q4") == "2027Q1" and M.next_quarter("2026Q1", -1) == "2025Q4"
    assert M.quarter_of("2026-08") == "2026Q3"
