"""Adapter parsers against saved pages (captured 2026-09-22). No network access."""
from pathlib import Path

import pytest

from scraper.retailers import ADAPTERS, Flo, Geneco, Keppel, PacificLight, Sembcorp, Senoko, Tuas
from scraper.retailers.pacificlight import parse_price_text
from scraper.schema import parse_hour, validate_plan

FX = Path(__file__).parent / "fixtures"


def read(name):
    return (FX / name).read_text(encoding="utf-8-sig")


def by_name(plans):
    return {(p["name"], p["contract_months"]): p for p in plans}


def assert_valid(plans):
    for p in plans:
        assert validate_plan(p) == [], (p["name"], validate_plan(p))


def test_seven_retailers_registered():
    assert {a.id for a in ADAPTERS} == {"flo", "geneco", "keppel", "pacificlight", "sembcorp", "senoko", "tuas"}


def test_senoko():
    res = Senoko().parse(read("senoko.html"))
    assert_valid(res.plans)
    p = by_name(res.plans)
    assert p[("LifePower24", 24)]["rates"] == {"rate": 29.80}
    assert p[("LifeSteady36", 36)]["price_type"] == "dot_cents"
    savvy = p[("LifeSavvy24", 24)]
    assert savvy["rates"]["periods"][0]["windows"] == [{"days": "all", "start": 7, "end": 23}]
    assert savvy["rates"]["default_rate"] == 20.05
    assert len(res.plans) == 7  # promotion cards are not mistaken for plans
    assert res.observations["regulated_tariff_cents_incl_gst"] == 34.78


def test_geneco_converts_ex_gst_rates():
    res = Geneco().parse(read("geneco.html"))
    assert_valid(res.plans)
    p = by_name(res.plans)
    assert p[("Get It Fixed 24", 24)]["rates"]["rate"] == 29.80   # 0.2734 SGD ex GST * 1.09
    assert p[("Get It Fixed 24", 24)]["rebate_sgd"] == 200 and p[("Get It Fixed 24", 24)]["rebate_sgd_non_sp"] == 100
    tou = p[("Get It 7 To 7", 24)]["rates"]
    assert tou["periods"][0]["rate"] == 32.50 and tou["default_rate"] == 27.90


def test_tuas():
    res = Tuas().parse(read("tuas.html"))
    assert_valid(res.plans)
    p = by_name(res.plans)
    assert p[("PowerFIX 36", 36)]["rates"]["rate"] == 29.40
    assert p[("PowerDOT 6", 6)]["rates"] == {"discount_pct": 10.0}
    assert p[("PowerFIX 24", 24)]["rebate_sgd"] == 100


def test_pacificlight_uses_full_tier_structure_not_headline():
    res = PacificLight().parse(read("pacificlight_plan.json"))
    assert_valid(res.plans)
    p = by_name(res.plans)
    nine = p[("9 to 9", 0)]
    assert nine["price_type"] == "tou" and nine["daily_charge_cents"] == 101
    assert nine["rates"]["periods"][0]["rate"] == 38.0   # the headline showed only the 18.50 tier
    stack = p[("Stack It Up", 24)]["rates"]["blocks"]
    assert [b["upto_kwh"] for b in stack] == [300, 600, None]
    assert p[("Classic 60", 60)]["rates"]["discount_pct"] == 8.0
    assert p[("Easy Save", 0)]["daily_charge_cents"] == 55


def test_pacificlight_unknown_price_text_is_rejected():
    assert parse_price_text("Something new: pay what you like") is None


def test_flo_reports_no_residential_plans():
    res = Flo().parse(read("flo.html"))
    assert res.status == "no_residential_plans" and res.plans == []


def test_flo_raises_when_page_changes():
    with pytest.raises(ValueError):
        Flo().parse("<html><body>Our plans: 28.00 ¢/kWh</body></html>")


@pytest.mark.parametrize("cls", [Keppel, Sembcorp])
def test_curated(cls):
    res, doc = cls().load()
    assert doc["verified_at"] and res.plans
    assert_valid(res.plans)


def test_parse_hour():
    assert [parse_hour(x) for x in ("12am", "7am", "12pm", "11pm", "9")] == [0, 7, 12, 23, 9]


def test_validation_catches_nonsense():
    bad = {"price_type": "fixed", "rates": {"rate": 2.98}, "contract_months": 24}
    assert validate_plan(bad)  # e.g. a SGD/kWh value mistaken for cents
