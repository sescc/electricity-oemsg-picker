"""A failed scrape must never drop a retailer: its last-known-good plans are served, marked stale."""
import json

from scraper import run
from scraper.retailers.base import Adapter, ScrapeResult
from scraper.schema import make_plan


def plan(name, rate):
    return make_plan(retailer_id="acme", retailer="Acme Power", name=name, price_type="fixed",
                     rates={"rate": rate}, contract_months=24, source_url="https://acme.example/plans")


class Broken(Adapter):
    id, name, homepage, plans_url = "acme", "Acme Power", "https://acme.example/", "https://acme.example/plans"

    def scrape(self, session):
        raise ConnectionError("403 challenge page")


class Working(Broken):
    def scrape(self, session):
        return ScrapeResult([plan("Fresh24", 29.5)], observations={"regulated_tariff_cents_incl_gst": 34.78})


class Garbage(Broken):
    def scrape(self, session):  # layout change: a SGD/kWh figure read as cents
        return ScrapeResult([plan("Weird", 0.298)])


def setup(monkeypatch, tmp_path, adapter):
    monkeypatch.setattr(run, "ADAPTERS", [adapter])
    monkeypatch.setattr(run, "SNAP", tmp_path / "snap")
    monkeypatch.setattr(run, "OUT", tmp_path / "out")
    monkeypatch.setattr(run, "PoliteSession", lambda *a, **k: None)
    monkeypatch.setattr(run, "check_retailer_list", lambda s: {"checked": False, "error": "offline test"})
    monkeypatch.setattr(run, "enrich_terms", lambda s, plans, cache: 0)


def read(tmp_path, name):
    return json.loads((tmp_path / "out" / name).read_text(encoding="utf-8"))


def test_failed_scrape_serves_last_known_plans_marked_stale(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, Broken())
    run.save(tmp_path / "snap" / "acme.json", {"fetched_at": "2026-09-01T00:00:00+00:00",
                                               "plans": [plan("Old24", 30.1)], "observations": {}})
    run.run_plans(force=True)
    plans, status = read(tmp_path, "plans.json"), read(tmp_path, "status.json")
    assert [p["name"] for p in plans["plans"]] == ["Old24"]
    assert plans["plans"][0]["data_as_of"] == "2026-09-01T00:00:00+00:00"
    st = status["retailers"]["acme"]
    assert st["status"] == "failed" and st["stale"] is True and "403" in st["message"]


def test_invalid_parse_is_treated_as_failure(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, Garbage())
    run.save(tmp_path / "snap" / "acme.json", {"fetched_at": "2026-09-01T00:00:00+00:00",
                                               "plans": [plan("Old24", 30.1)], "observations": {}})
    run.run_plans(force=True)
    assert [p["name"] for p in read(tmp_path, "plans.json")["plans"]] == ["Old24"]
    assert "validation failed" in read(tmp_path, "status.json")["retailers"]["acme"]["message"]


def test_success_replaces_snapshot_and_rate_limit_skips_next_run(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, Working())
    run.run_plans(force=True)
    assert read(tmp_path, "plans.json")["regulated_tariff"]["cents_incl_gst"] == 34.78
    # a second run within MIN_REFRESH_HOURS must not hit the site again
    monkeypatch.setattr(run, "ADAPTERS", [Broken()])
    run.run_plans(force=False)
    st = read(tmp_path, "status.json")["retailers"]["acme"]
    assert st["skipped"].startswith("refreshed recently") and st["status"] == "ok"
    assert [p["name"] for p in read(tmp_path, "plans.json")["plans"]] == ["Fresh24"]


def test_oem_list_ignores_commented_out_retailers():
    from pathlib import Path
    html = (Path(__file__).parent / "fixtures" / "oem_list.html").read_text(encoding="utf-8")
    titles = [t for t, _ in run.parse_oem_list(html)]
    assert len(titles) == 7
    assert not any("Sunseap" in t or "Diamond" in t for t in titles)  # former retailers, commented out


def test_tariff_from_old_snapshot_is_dated_and_marked_stale(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, Broken())
    run.save(tmp_path / "snap" / "acme.json", {
        "fetched_at": "2026-08-01T00:00:00+00:00", "plans": [plan("Old24", 30.1)],
        "observations": {"regulated_tariff_cents_incl_gst": 29.11, "tariff_quarter": "Q2 2026"}})
    run.run_plans(force=True)
    rt = read(tmp_path, "plans.json")["regulated_tariff"]
    assert rt["cents_incl_gst"] == 29.11
    assert rt["observed_at"] == "2026-08-01T00:00:00+00:00" and rt["stale"] is True


def test_fresh_tariff_not_stale(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path, Working())
    run.run_plans(force=True)
    rt = read(tmp_path, "plans.json")["regulated_tariff"]
    assert rt["stale"] is False and rt["agreeing_sources"] == ["acme"]
