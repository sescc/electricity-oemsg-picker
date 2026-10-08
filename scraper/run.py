"""Entry point for CI and local runs.

    python -m scraper.run plans     [--force] [--only senoko,tuas]
    python -m scraper.run datasets  [--force]
    python -m analysis.build
    python -m scraper.run all       [--force]

Rate limiting happens at three levels:
  * the workflow runs on a daily schedule (plus manual dispatch by the repo owner);
  * each retailer is re-scraped at most once per MIN_REFRESH_HOURS unless --force;
  * PoliteSession spaces requests per host and caps requests per run.
A failed scrape never removes a retailer: its last-known-good snapshot is served, marked stale.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import traceback
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .http import PoliteSession, RobotsDisallowed
from .retailers import ADAPTERS, OEM_LIST_URL
from .schema import validate_plan
from .sources import ses as ses_src, tariff as tariff_src, weather as weather_src
from .terms import document_text, extract_terms

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "snapshots"
OUT = ROOT / "site" / "data"
MIN_REFRESH_HOURS = 20
DATASET_REFRESH_DAYS = 7
MAX_FACTSHEETS_PER_RUN = 25
STALE_TARIFF_HOURS = 48


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def hours_since(ts: str | None) -> float:
    if not ts:
        return 1e9
    return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(ts)).total_seconds() / 3600


# ------------------------------------------------------------------ plans
def parse_oem_list(html: str) -> list[tuple[str, str]]:
    """(title, url) of retailers on the OEM page.

    The page renders from an inline JS array; former retailers stay in it as `//` comments,
    so commented lines are dropped first. Falls back to rendered <a> links if the array is gone.
    """
    live = "\n".join(line for line in html.splitlines() if not line.lstrip().startswith("//"))
    found = re.findall(r'title:\s*"([^"]+)",\s*logo:\s*"[^"]*",\s*url:\s*"(https?://[^"]+)"', live)
    if not found:
        soup = BeautifulSoup(html, "lxml")
        found = [(a.get_text(strip=True), a["href"]) for a in soup.find_all("a", href=True)
                 if re.search(r"\b(Pte|Ltd)\b", a.get_text()) and a["href"].startswith("http")]
    return list(dict.fromkeys(found))


def check_retailer_list(session) -> dict:
    """Detect retailers added to / removed from the OEM list since the adapters were written."""
    try:
        html = session.get(OEM_LIST_URL).text
    except Exception as e:  # noqa: BLE001
        return {"checked": False, "error": str(e)}
    hosts = {re.sub(r"^www\.", "", urlparse(u).netloc) for _, u in parse_oem_list(html)}
    if not hosts:
        # never report "no changes" when nothing could be read
        return {"checked": False, "checked_at": now(), "error": "no retailer links found on the OEM page (layout changed?)"}
    known = {re.sub(r"^www\.", "", urlparse(a.homepage).netloc) for a in ADAPTERS}
    return {"checked": True, "checked_at": now(), "retailers_found": len(hosts),
            "new_on_oem_list": sorted(hosts - known), "missing_from_oem_list": sorted(known - hosts)}


def enrich_terms(session, plans: list[dict], cache: dict) -> int:
    """Attach fact-sheet terms. Fact sheets are versioned by URL, so each URL is fetched once."""
    fetched = 0
    for p in plans:
        url = p.get("factsheet_url") or ""
        if not url or url.lower().endswith((".jpg", ".png")):
            continue
        cached = cache.get(url)
        if cached is None or ("error" in cached and hours_since(cached.get("fetched_at")) > 24 * 7):
            if fetched >= MAX_FACTSHEETS_PER_RUN:
                continue
            try:
                r = session.get(url)
                terms = extract_terms(document_text(r.content))
                cache[url] = ({**terms, "fetched_at": now()} if terms.get("etf_text") or terms.get("auto_renewal_text")
                              else {"error": "no fact-sheet fields found", "fetched_at": now()})
            except RobotsDisallowed:
                cache[url] = {"error": "robots.txt disallows this fact-sheet host", "fetched_at": now()}
            except Exception as e:  # noqa: BLE001
                cache[url] = {"error": str(e)[:200], "fetched_at": now()}
            fetched += 1
        t = cache[url]
        if "error" not in t:
            p["terms"] = {**t, **p.get("terms", {}), "source_url": url}
            if p.get("standard") is None and "standard" in t:
                p["standard"] = t["standard"]
    return fetched


def run_plans(force: bool = False, only: set[str] | None = None) -> None:
    session = PoliteSession()
    status = load(OUT / "status.json", {}).get("retailers", {})
    terms_cache = load(SNAP / "terms_cache.json", {})
    all_plans, observations = [], {}
    for a in ADAPTERS:
        st = status.get(a.id, {})
        snap_path = SNAP / f"{a.id}.json"
        entry = {"id": a.id, "name": a.name, "homepage": a.homepage, "plans_url": a.plans_url,
                 "method": a.method}
        if a.method == "curated":
            res, doc = a.load()
            entry.update(status="curated", message=a.curated_reason, verified_at=doc["verified_at"],
                         plan_count=len(res.plans), data_as_of=doc["verified_at"])
            plans = res.plans
        elif skip := ("not selected" if only and a.id not in only else
                      "refreshed recently (rate limit)" if not force and hours_since(st.get("last_success_at")) < MIN_REFRESH_HOURS
                      else None):
            snap = load(snap_path, {})
            plans = snap.get("plans", [])
            observations[a.id] = {**snap.get("observations", {}), "as_of": snap.get("fetched_at")}
            entry.update({k: st.get(k) for k in ("status", "message", "last_success_at", "last_attempt_at",
                                                  "plan_count", "data_as_of", "stale")})
            entry["skipped"] = skip
        else:
            entry["last_attempt_at"] = now()
            try:
                res = a.scrape(session)
                bad = {p["name"]: errs for p in res.plans if (errs := validate_plan(p))}
                if bad:
                    raise ValueError(f"validation failed: {bad}")
                if res.status == "ok" and not res.plans:
                    raise ValueError("no plans parsed (page layout probably changed)")
                plans = res.plans
                t = now()
                save(snap_path, {"fetched_at": t, "plans": plans, "observations": res.observations,
                                 "status": res.status, "message": res.message})
                observations[a.id] = {**res.observations, "as_of": t}
                entry.update(status=res.status, message=res.message, last_success_at=t, data_as_of=t,
                             plan_count=len(plans))
            except Exception as e:  # noqa: BLE001
                snap = load(snap_path, {})
                plans = snap.get("plans", [])
                observations[a.id] = {**snap.get("observations", {}), "as_of": snap.get("fetched_at")}
                kind ="blocked_by_robots" if isinstance(e, RobotsDisallowed) else "failed"
                entry.update(status=kind, message=f"{type(e).__name__}: {str(e)[:300]}",
                             last_success_at=st.get("last_success_at") or snap.get("fetched_at"),
                             data_as_of=snap.get("fetched_at"), plan_count=len(plans),
                             stale=bool(plans))
                traceback.print_exc()
        for p in plans:
            p["data_as_of"] = entry.get("data_as_of")
            p["data_method"] = a.method
        all_plans.extend(plans)
        status[a.id] = entry
        print(f"{a.id:13s} {entry.get('status')!s:22s} plans={len(plans)} {entry.get('message', '')[:90]}")

    n = enrich_terms(session, all_plans, terms_cache)
    save(SNAP / "terms_cache.json", terms_cache)
    print(f"fact sheets fetched this run: {n}")

    current = tariff_src.consensus_current(observations)
    prev = load(OUT / "plans.json", {}).get("regulated_tariff")
    if current:
        # when the quote was actually read, not when this run happened (snapshots may be old)
        current["observed_at"] = max(filter(None, (observations[s].get("as_of") for s in current["agreeing_sources"])),
                                     default=None)
        current["stale"] = hours_since(current["observed_at"]) > STALE_TARIFF_HOURS
    # Keep every labelled quote: plans.json only holds the latest one, and the official series lags
    # a quarter or more. `prev` is recorded first so a quote never recorded before is not lost;
    # only a freshly read consensus is recorded as current (the stale fallback below is ignored).
    quotes = tariff_src.update_quotes(load(SNAP / "tariff_quotes.json", {}), prev, current)
    save(SNAP / "tariff_quotes.json", quotes)
    if not current and prev:
        current = {**prev, "stale": True}
    save(OUT / "plans.json", {"generated_at": now(), "regulated_tariff": current, "plans": all_plans})
    save(OUT / "status.json", {"generated_at": now(), "oem_list_url": OEM_LIST_URL,
                               "oem_list_check": check_retailer_list(session), "retailers": status})


# ------------------------------------------------------------------ datasets
def run_datasets(force: bool = False) -> None:
    path = SNAP / "datasets.json"
    cur = load(path, {})
    if not force and hours_since(cur.get("generated_at")) < DATASET_REFRESH_DAYS * 24:
        print("datasets fresh; skipping (use --force)")
        return
    session = PoliteSession(min_interval=2)
    out = {"generated_at": now(), "sources": {}}

    def attempt(key, fn, url):
        try:
            out[key] = fn()
            out["sources"][key] = {"ok": True, "url": url, "fetched_at": now()}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            out[key] = cur.get(key)
            out["sources"][key] = {"ok": False, "url": url, "error": str(e)[:300],
                                   "fetched_at": (cur.get("sources", {}).get(key) or {}).get("fetched_at")}

    attempt("ses", lambda: ses_src.fetch_ses(session), ses_src.SES_URL)
    attempt("tariff_datagov", lambda: tariff_src.fetch_datagov(session), tariff_src.DATAGOV_URL)
    attempt("weather_history", lambda: weather_src.fetch_history(session), weather_src.ARCHIVE)
    attempt("weather_seasonal", lambda: weather_src.fetch_seasonal(session), weather_src.SEASONAL)
    save(path, out)
    print({k: v["ok"] for k, v in out["sources"].items()})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["plans", "datasets", "all"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    only = set(filter(None, a.only.split(","))) or None
    if a.what in ("plans", "all"):
        run_plans(a.force, only)
    if a.what in ("datasets", "all"):
        run_datasets(a.force)
    if a.what == "all":
        from analysis.build import build_or_keep
        build_or_keep()
    return 0


if __name__ == "__main__":
    sys.exit(main())
