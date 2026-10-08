"""Retailer tariff quotes: consensus across sources, and the persisted per-quarter record.

The official tariff series lags by a quarter or more, so recorded retailer quotes fill the gap.
"""
import json

from scraper import run
from scraper.retailers.base import Adapter, ScrapeResult
from scraper.schema import make_plan
from common.tariff import quarter_key, quarter_of_ts
from scraper.sources.tariff import consensus_current, record_quote, update_quotes

K = "regulated_tariff_cents_incl_gst"


# ------------------------------------------------------------------ consensus_current
def test_stale_old_quarter_snapshot_does_not_outvote_fresh_read():
    c = consensus_current({
        "pacificlight": {K: 34.78, "tariff_quarter": "Q3 2026", "as_of": "2026-09-30T08:00:00+00:00"},
        "senoko": {K: 31.16, "as_of": "2026-10-02T03:00:00+00:00"},
    })
    assert c["cents_incl_gst"] == 31.16
    assert c["quarter"] is None                      # the only label belongs to the dropped source
    assert c["ignored_sources"] == {"pacificlight": 34.78}
    assert c["agreeing_sources"] == ["senoko"] and c["disagreeing_sources"] == {} and c["n_sources"] == 1


def test_old_quarter_sources_are_dropped_even_when_they_are_the_majority():
    c = consensus_current({
        "a": {K: 34.78, "as_of": "2026-09-29T00:00:00+00:00"}, "b": {K: 34.78, "as_of": "2026-09-30T00:00:00+00:00"},
        "c": {K: 31.16, "as_of": "2026-10-03T00:00:00+00:00"},
    })
    assert c["cents_incl_gst"] == 31.16 and c["ignored_sources"] == {"a": 34.78, "b": 34.78}


def test_quarter_boundary_is_singapore_time():
    assert quarter_of_ts("2026-09-30T17:00:00+00:00") == "2026Q4"      # 01:00 on 1 Oct in Singapore
    assert quarter_of_ts("2026-09-30T15:00:00+00:00") == "2026Q3"
    assert quarter_of_ts(None) is None and quarter_of_ts("not a date") is None


def test_tie_goes_to_most_recent_read():
    c = consensus_current({"a": {K: 30.0, "as_of": "2026-10-02T01:00:00+00:00"},
                           "b": {K: 31.0, "as_of": "2026-10-02T05:00:00+00:00"}})
    assert c["cents_incl_gst"] == 31.0 and c["disagreeing_sources"] == {"a": 30.0}


def test_quarter_label_comes_only_from_an_agreeing_source():
    c = consensus_current({
        "a": {K: 31.16, "as_of": "2026-10-02T00:00:00+00:00"},
        "b": {K: 31.16, "as_of": "2026-10-02T00:00:00+00:00"},
        "c": {K: 29.11, "tariff_quarter": "Q4 2026", "as_of": "2026-10-02T00:00:00+00:00"},   # disagrees
    })
    assert c["cents_incl_gst"] == 31.16 and c["quarter"] is None


def test_quarter_label_must_be_plausible_for_when_it_was_read():
    def label_for(label, as_of="2026-10-02T00:00:00+00:00"):
        return consensus_current({"p": {K: 31.16, "tariff_quarter": label, "as_of": as_of}})["quarter"]

    assert label_for("Q4 2026") == "Q4 2026"                                  # this quarter
    assert label_for("Q1 2027") == "Q1 2027"                                  # pre-announced next quarter
    assert label_for("Q2 2027") is None                                       # two quarters ahead
    assert label_for("Q3 2026") is None                                       # last quarter's page
    assert label_for("Q4 2026", "2026-09-29T00:00:00+00:00") == "Q4 2026"     # late-quarter pre-announcement
    assert label_for("tomorrow") is None


def test_label_without_as_of_is_kept_because_nothing_contradicts_it():
    c = consensus_current({"a": {K: 34.78, "tariff_quarter": "Q3 2026"}, "b": {K: 34.78}})
    assert c["quarter"] == "Q3 2026" and c["ignored_sources"] == {}


def test_consensus_without_any_quote_is_none():
    assert consensus_current({"a": {}, "b": {K: 0}}) is None


# ------------------------------------------------------------------ record_quote
def q(cents=31.16, quarter="Q4 2026", **kw):
    return {"cents_incl_gst": cents, "quarter": quarter, "agreeing_sources": ["pacificlight"],
            "observed_at": "2026-10-02T00:00:00+00:00", "stale": False, **kw}


def test_quarter_key_formats():
    assert quarter_key("Q3 2026") == "2026Q3" and quarter_key("2026Q3") == "2026Q3"
    assert quarter_key("Q5 2026") is None and quarter_key(None) is None


def test_record_quote_new_quarter():
    before = {"2026Q3": {"cents_incl_gst": 34.78, "observed_at": "x", "sources": ["a"]}}
    after = record_quote(before, q())
    assert after["2026Q4"] == {"cents_incl_gst": 31.16, "observed_at": "2026-10-02T00:00:00+00:00",
                               "sources": ["pacificlight"]}
    assert after["2026Q3"] == before["2026Q3"]
    assert "2026Q4" not in before                    # input untouched


def test_record_quote_same_value_keeps_original_observed_at():
    first = record_quote({}, q())
    again = record_quote(first, q(observed_at="2026-10-05T00:00:00+00:00"))
    assert again == first and again["2026Q4"]["observed_at"] == "2026-10-02T00:00:00+00:00"


def test_record_quote_revision_overwrites_and_remembers_old_value():
    first = record_quote({}, q(31.16))
    revised = record_quote(first, q(31.50, observed_at="2026-10-09T00:00:00+00:00"))
    rec = revised["2026Q4"]
    assert rec["cents_incl_gst"] == 31.50 and rec["revised_from"] == 31.16
    assert rec["observed_at"] == "2026-10-09T00:00:00+00:00"


def test_record_quote_ignores_stale_unlabelled_and_empty_quotes():
    assert record_quote({}, q(stale=True)) == {}
    assert record_quote({}, q(quarter=None)) == {}
    assert record_quote({}, q(quarter="soon")) == {}
    assert record_quote({}, {"quarter": "Q4 2026", "stale": False}) == {}
    assert record_quote({}, None) == {}


def test_update_quotes_records_previous_quote_before_the_current_one():
    prev = q(34.78, "Q3 2026", observed_at="2026-09-30T08:00:00+00:00")
    out = update_quotes({}, prev, q(31.16, "Q4 2026"))
    assert list(out) == ["2026Q3", "2026Q4"]
    assert out["2026Q3"]["cents_incl_gst"] == 34.78 and out["2026Q3"]["observed_at"] == "2026-09-30T08:00:00+00:00"
    # a stale previous quote (the fallback copy) is not recorded, and a missing current is fine
    assert update_quotes({}, {**prev, "stale": True}, None) == {}


# ------------------------------------------------------------------ run_plans wiring
def plan(name, rate):
    return make_plan(retailer_id="acme", retailer="Acme Power", name=name, price_type="fixed",
                     rates={"rate": rate}, contract_months=24, source_url="https://acme.example/plans")


class Fresh(Adapter):
    id, name, homepage, plans_url = "acme", "Acme Power", "https://acme.example/", "https://acme.example/plans"

    def scrape(self, session):
        return ScrapeResult([plan("Fresh24", 29.5)],
                            observations={K: 31.16, "tariff_quarter": "Q4 2026"})


class Down(Fresh):
    def scrape(self, session):
        raise ConnectionError("403 challenge page")


def setup(monkeypatch, tmp_path, adapter, clock="2026-10-02T03:00:00+00:00"):
    monkeypatch.setattr(run, "ADAPTERS", [adapter])
    monkeypatch.setattr(run, "SNAP", tmp_path / "snap")
    monkeypatch.setattr(run, "OUT", tmp_path / "out")
    monkeypatch.setattr(run, "PoliteSession", lambda *a, **k: None)
    monkeypatch.setattr(run, "check_retailer_list", lambda s: {"checked": False, "error": "offline test"})
    monkeypatch.setattr(run, "enrich_terms", lambda s, plans, cache: 0)
    monkeypatch.setattr(run, "now", lambda: clock)              # the label check depends on "today"
    monkeypatch.setattr(run, "hours_since", lambda ts: 1.0)     # ...and so does the staleness check


def test_run_plans_backfills_previous_quote_then_records_current(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, Fresh())
    run.save(tmp_path / "out" / "plans.json", {"regulated_tariff": q(34.78, "Q3 2026",
                                                                    observed_at="2026-09-30T08:00:00+00:00")})
    run.run_plans(force=True)
    quotes = json.loads((tmp_path / "snap" / "tariff_quotes.json").read_text(encoding="utf-8"))
    assert list(quotes) == ["2026Q3", "2026Q4"]
    assert quotes["2026Q3"]["cents_incl_gst"] == 34.78 and quotes["2026Q4"]["cents_incl_gst"] == 31.16
    plans = json.loads((tmp_path / "out" / "plans.json").read_text(encoding="utf-8"))
    assert plans["regulated_tariff"]["quarter"] == "Q4 2026" and plans["regulated_tariff"]["stale"] is False


def test_run_plans_does_not_record_the_stale_fallback(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, Down())
    run.save(tmp_path / "out" / "plans.json", {"regulated_tariff": q(34.78, "Q3 2026", stale=True)})
    run.run_plans(force=True)
    assert json.loads((tmp_path / "snap" / "tariff_quotes.json").read_text(encoding="utf-8")) == {}
    plans = json.loads((tmp_path / "out" / "plans.json").read_text(encoding="utf-8"))
    assert plans["regulated_tariff"]["cents_incl_gst"] == 34.78 and plans["regulated_tariff"]["stale"] is True
