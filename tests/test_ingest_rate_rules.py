"""Ingest rate-limiting rules that compose across functions in scraper/run.py.

* Fact sheets are fetched once per URL (R4): cached successes are permanent, errors are retried
  after 7 days, and at most MAX_FACTSHEETS_PER_RUN fetches happen per run.
* Datasets are refreshed at most every 7 days (R3); a failing source keeps its previous value.
"""
import datetime as dt
import json

from scraper import run
from scraper.http import RobotsDisallowed

GOOD_TERMS = {"etf_text": "Early termination fee applies", "early_termination_fee_sgd": 100}


def ago(**delta) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(**delta)).replace(microsecond=0).isoformat()


# ------------------------------------------------------------------ fact sheets (enrich_terms)
class Resp:
    content = b"fake pdf bytes"


class FakeSession:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def get(self, url):
        self.calls.append(url)
        if self.fail:
            raise self.fail
        return Resp()


def plan_with(url, **extra):
    return {"name": "P", "factsheet_url": url, **extra}


def stub_extraction(monkeypatch, terms=GOOD_TERMS):
    monkeypatch.setattr(run, "document_text", lambda content: "text")
    monkeypatch.setattr(run, "extract_terms", lambda text: dict(terms))


def test_two_plans_sharing_a_fact_sheet_fetch_it_once(monkeypatch):
    stub_extraction(monkeypatch)
    session, cache = FakeSession(), {}
    plans = [plan_with("https://x.example/a.pdf"), plan_with("https://x.example/a.pdf")]
    assert run.enrich_terms(session, plans, cache) == 1
    assert session.calls == ["https://x.example/a.pdf"]
    assert all(p["terms"]["source_url"] == "https://x.example/a.pdf" for p in plans)


def test_successful_cache_entry_is_never_refetched_however_old(monkeypatch):
    stub_extraction(monkeypatch)
    url = "https://x.example/a.pdf"
    session, cache = FakeSession(), {url: {**GOOD_TERMS, "fetched_at": ago(days=400)}}
    plans = [plan_with(url)]
    assert run.enrich_terms(session, plans, cache) == 0
    assert session.calls == []
    assert plans[0]["terms"]["etf_text"] == GOOD_TERMS["etf_text"]


def test_recent_error_entry_is_not_retried_and_plan_gets_no_terms(monkeypatch):
    stub_extraction(monkeypatch)
    url = "https://x.example/a.pdf"
    session, cache = FakeSession(), {url: {"error": "boom", "fetched_at": ago(days=6)}}
    plans = [plan_with(url)]
    assert run.enrich_terms(session, plans, cache) == 0
    assert session.calls == []
    assert "terms" not in plans[0]


def test_error_entry_older_than_seven_days_is_retried_and_replaced(monkeypatch):
    stub_extraction(monkeypatch)
    url = "https://x.example/a.pdf"
    session, cache = FakeSession(), {url: {"error": "boom", "fetched_at": ago(days=8)}}
    plans = [plan_with(url)]
    assert run.enrich_terms(session, plans, cache) == 1
    assert session.calls == [url]
    assert "error" not in cache[url] and cache[url]["etf_text"] == GOOD_TERMS["etf_text"]
    assert plans[0]["terms"]["source_url"] == url


def test_error_entry_without_timestamp_is_retried(monkeypatch):
    stub_extraction(monkeypatch)
    url = "https://x.example/a.pdf"
    session, cache = FakeSession(), {url: {"error": "boom"}}
    assert run.enrich_terms(session, [plan_with(url)], cache) == 1
    assert session.calls == [url]
    assert "error" not in cache[url]


def test_at_most_25_fact_sheets_are_fetched_per_run(monkeypatch):
    stub_extraction(monkeypatch)
    urls = [f"https://x.example/{i}.pdf" for i in range(30)]
    session, cache = FakeSession(), {}
    plans = [plan_with(u) for u in urls]
    assert run.enrich_terms(session, plans, cache) == run.MAX_FACTSHEETS_PER_RUN == 25
    assert len(session.calls) == 25
    assert set(cache) == set(urls[:25])  # the rest wait for the next run
    assert all("terms" in p for p in plans[:25])
    assert all("terms" not in p for p in plans[25:])


def test_robots_disallowed_is_cached_as_an_error_and_counts_as_a_fetch(monkeypatch):
    stub_extraction(monkeypatch)
    url = "https://x.example/a.pdf"
    session, cache = FakeSession(fail=RobotsDisallowed("no")), {}
    plans = [plan_with(url)]
    assert run.enrich_terms(session, plans, cache) == 1
    assert "robots" in cache[url]["error"] and cache[url]["fetched_at"]
    assert "terms" not in plans[0]


def test_network_failure_is_cached_as_an_error_with_timestamp(monkeypatch):
    stub_extraction(monkeypatch)
    url = "https://x.example/a.pdf"
    session, cache = FakeSession(fail=ConnectionError("reset by peer")), {}
    plans = [plan_with(url)]
    assert run.enrich_terms(session, plans, cache) == 1
    assert "reset by peer" in cache[url]["error"] and cache[url]["fetched_at"]
    assert "terms" not in plans[0]


def test_fact_sheet_without_any_known_field_is_cached_as_an_error(monkeypatch):
    stub_extraction(monkeypatch, terms={"standard": True})
    url = "https://x.example/a.pdf"
    session, cache = FakeSession(), {}
    plans = [plan_with(url)]
    assert run.enrich_terms(session, plans, cache) == 1
    assert cache[url]["error"] == "no fact-sheet fields found"
    assert "terms" not in plans[0]


def test_image_and_missing_urls_are_skipped_without_fetching_or_caching(monkeypatch):
    stub_extraction(monkeypatch)
    session, cache = FakeSession(), {}
    plans = [plan_with("https://x.example/a.jpg"), plan_with("https://x.example/B.PNG"),
             plan_with(""), {"name": "no key at all"}, plan_with(None)]
    assert run.enrich_terms(session, plans, cache) == 0
    assert session.calls == [] and cache == {}
    assert all("terms" not in p for p in plans)


def test_terms_already_on_the_plan_win_over_fact_sheet_terms(monkeypatch):
    stub_extraction(monkeypatch)
    url = "https://x.example/a.pdf"
    plans = [plan_with(url, terms={"early_termination_fee_sgd": 999, "note": "curated"})]
    run.enrich_terms(FakeSession(), plans, {})
    t = plans[0]["terms"]
    assert t["early_termination_fee_sgd"] == 999 and t["note"] == "curated"
    assert t["etf_text"] == GOOD_TERMS["etf_text"] and t["source_url"] == url


def test_standard_status_is_filled_from_the_fact_sheet_only_when_unknown(monkeypatch):
    stub_extraction(monkeypatch, terms={**GOOD_TERMS, "standard": True})
    url = "https://x.example/a.pdf"
    unknown, explicit_false = plan_with(url, standard=None), plan_with(url, standard=False)
    run.enrich_terms(FakeSession(), [unknown, explicit_false], {})
    assert unknown["standard"] is True
    assert explicit_false["standard"] is False


# ------------------------------------------------------------------ datasets (run_datasets)
class DummySession:
    def __init__(self, *a, **k):
        pass


def setup_datasets(monkeypatch, tmp_path, fail=()):
    """Patch paths and the four fetchers; returns the list of fetchers called, in order."""
    monkeypatch.setattr(run, "SNAP", tmp_path)
    monkeypatch.setattr(run, "PoliteSession", DummySession)
    called = []

    def fetcher(key):
        def fn(session):
            called.append(key)
            if key in fail:
                raise RuntimeError(f"{key} is down")
            return {"fresh": key}
        return fn

    monkeypatch.setattr(run.ses_src, "fetch_ses", fetcher("ses"))
    monkeypatch.setattr(run.tariff_src, "fetch_datagov", fetcher("tariff_datagov"))
    monkeypatch.setattr(run.weather_src, "fetch_history", fetcher("weather_history"))
    monkeypatch.setattr(run.weather_src, "fetch_seasonal", fetcher("weather_seasonal"))
    return called


KEYS = ["ses", "tariff_datagov", "weather_history", "weather_seasonal"]


def previous_snapshot(generated_at, fetched_at="2026-01-01T00:00:00+00:00"):
    return {"generated_at": generated_at,
            **{k: {"old": k} for k in KEYS},
            "sources": {k: {"ok": True, "url": f"https://old/{k}", "fetched_at": fetched_at} for k in KEYS}}


def test_datasets_younger_than_seven_days_are_left_alone(monkeypatch, tmp_path):
    called = setup_datasets(monkeypatch, tmp_path)
    path = tmp_path / "datasets.json"
    # 7 days minus 1 hour: still inside the limit
    run.save(path, previous_snapshot(ago(days=6, hours=23)))
    before = path.read_bytes()
    run.run_datasets()
    assert called == []
    assert path.read_bytes() == before


def test_force_refreshes_datasets_even_when_fresh(monkeypatch, tmp_path):
    called = setup_datasets(monkeypatch, tmp_path)
    path = tmp_path / "datasets.json"
    old = ago(days=1)
    run.save(path, previous_snapshot(old))
    run.run_datasets(force=True)
    assert called == KEYS
    out = json.loads(path.read_text(encoding="utf-8"))
    assert out["generated_at"] > old
    assert out["ses"] == {"fresh": "ses"}


def test_datasets_older_than_seven_days_are_refreshed(monkeypatch, tmp_path):
    called = setup_datasets(monkeypatch, tmp_path)
    path = tmp_path / "datasets.json"
    run.save(path, previous_snapshot(ago(days=8)))
    run.run_datasets()
    assert called == KEYS
    assert json.loads(path.read_text(encoding="utf-8"))["ses"] == {"fresh": "ses"}


def test_missing_datasets_file_is_created_with_every_source_ok(monkeypatch, tmp_path):
    called = setup_datasets(monkeypatch, tmp_path)
    run.run_datasets()
    out = json.loads((tmp_path / "datasets.json").read_text(encoding="utf-8"))
    assert called == KEYS
    assert set(out) == {"generated_at", *KEYS, "sources"}
    assert set(out["sources"]) == set(KEYS)
    for k in KEYS:
        src = out["sources"][k]
        assert src["ok"] is True and src["url"] and src["fetched_at"]
        assert out[k] == {"fresh": k}


def test_a_failing_source_keeps_its_previous_value_and_fetch_time(monkeypatch, tmp_path):
    called = setup_datasets(monkeypatch, tmp_path, fail={"weather_seasonal"})
    path = tmp_path / "datasets.json"
    run.save(path, previous_snapshot(ago(days=8), fetched_at="2026-01-01T00:00:00+00:00"))
    run.run_datasets()
    out = json.loads(path.read_text(encoding="utf-8"))
    assert called == KEYS  # the failure does not stop the later sources
    assert out["weather_seasonal"] == {"old": "weather_seasonal"}
    s = out["sources"]["weather_seasonal"]
    assert s["ok"] is False and "weather_seasonal is down" in s["error"]
    assert s["fetched_at"] == "2026-01-01T00:00:00+00:00"
    for k in KEYS[:3]:
        assert out[k] == {"fresh": k}
        assert out["sources"][k]["ok"] is True
        assert out["sources"][k]["fetched_at"] != "2026-01-01T00:00:00+00:00"


def test_a_failing_source_with_no_previous_snapshot_is_recorded_as_missing(monkeypatch, tmp_path):
    setup_datasets(monkeypatch, tmp_path, fail={"ses"})
    run.run_datasets()
    out = json.loads((tmp_path / "datasets.json").read_text(encoding="utf-8"))
    assert out["ses"] is None
    assert out["sources"]["ses"]["ok"] is False
    assert out["sources"]["ses"]["fetched_at"] is None
    assert out["sources"]["tariff_datagov"]["ok"] is True
