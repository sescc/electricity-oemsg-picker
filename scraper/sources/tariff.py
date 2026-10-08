"""Regulated tariff: monthly history (data.gov.sg / SingStat) and the current quarter.

(Quarter labels, timestamps and the history merge live in `common/tariff.py`.)
The history series excludes GST. The current quarter's GST-inclusive tariff is quoted on
several retailer pages (scraped as `observations`); we take the consensus and cross-check it
against the history where they overlap.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter

from common.tariff import parse_ts, quarter_key, quarter_of_ts, shift_quarter

DATAGOV_URL = ("https://data.gov.sg/api/action/datastore_search?"
               "resource_id=d_61eac3cdb086814af485dcc682b75ae9&limit=5")
SERIES = "Low Tension Supplies - Domestic"
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                                      "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_datagov(payload: dict) -> dict[str, float]:
    recs = payload["result"]["records"]
    rec = next(r for r in recs if r.get("DataSeries") == SERIES)
    out = {}
    for k, v in rec.items():
        m = re.fullmatch(r"(\d{4})([A-Z][a-z]{2})", k)
        if m and v not in (None, "", "na"):
            out[f"{m.group(1)}-{MONTHS[m.group(2)]:02d}"] = float(v)
    return dict(sorted(out.items()))


def fetch_datagov(session) -> dict[str, float]:
    return parse_datagov(session.get(DATAGOV_URL, check_robots=False).json())


_OLDEST = dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def consensus_current(observations: dict[str, dict]) -> dict | None:
    """observations: {retailer_id: {"regulated_tariff_cents_incl_gst": x, "as_of": iso, ...}}

    Quotes read in an earlier calendar quarter than the newest quote are dropped first (a stale
    snapshot from before the quarterly change must not outvote a fresh read after it). Of the
    rest, the most common value wins; ties go to the most recently read. The quarter label is
    taken only from a source that agrees with the chosen value and whose label is plausible for
    when it was read (that quarter or the next, because pages announce the next tariff early).
    """
    vals = {rid: o["regulated_tariff_cents_incl_gst"] for rid, o in observations.items()
            if o.get("regulated_tariff_cents_incl_gst")}
    if not vals:
        return None
    when = {rid: parse_ts(observations[rid].get("as_of")) or _OLDEST for rid in vals}
    qtr = {rid: quarter_of_ts(observations[rid].get("as_of")) or "" for rid in vals}   # "" = oldest
    newest = max(qtr.values())
    kept = {rid: v for rid, v in vals.items() if qtr[rid] == newest}
    ignored = {rid: v for rid, v in vals.items() if rid not in kept}
    counts = Counter(kept.values())
    value = max(counts, key=lambda v: (counts[v], max(when[r] for r, x in kept.items() if x == v)))
    agreeing = sorted((r for r, x in kept.items() if x == value), key=lambda r: (when[r], r), reverse=True)
    quarter = None
    for rid in agreeing:
        label = observations[rid].get("tariff_quarter")
        key = quarter_key(label)
        if not key:
            continue
        q = qtr[rid]
        if q and not (q <= key <= shift_quarter(q, 1)):      # no as_of: nothing to check it against
            continue
        quarter = label
        break
    return {"cents_incl_gst": value, "quarter": quarter, "agreeing_sources": sorted(agreeing),
            "disagreeing_sources": {k: v for k, v in kept.items() if v != value}, "n_sources": len(kept),
            "ignored_sources": ignored}


def record_quote(quotes: dict, quote: dict | None) -> dict:
    """Return `quotes` plus this quarter-labelled consensus quote ({"2026Q3": {...}}); never mutates.

    Retailer quotes are the only source of the tariff for the quarter(s) that the official
    series (SES / data.gov.sg) has not published yet, and a quote disappears from plans.json
    when the quarter turns over, so each one is kept here. Stale or unlabelled quotes are ignored.
    """
    out = {q: dict(rec) for q, rec in quotes.items()}
    if not quote or quote.get("stale") or quote.get("cents_incl_gst") is None:
        return out
    key = quarter_key(quote.get("quarter"))
    if not key:
        return out
    value, old = quote["cents_incl_gst"], out.get(key)
    if old is not None and old.get("cents_incl_gst") == value:
        return out                                            # keep the original observed_at
    rec = {"cents_incl_gst": value, "observed_at": quote.get("observed_at"),
           "sources": list(quote.get("agreeing_sources") or [])}
    if old is not None:
        rec["revised_from"] = old.get("cents_incl_gst")
    out[key] = rec
    return dict(sorted(out.items()))


def update_quotes(quotes: dict, prev: dict | None, current: dict | None) -> dict:
    """Record the previously published quote first (self-healing back-fill of a quarter that was
    never recorded), then the freshly read consensus, so a later quote overrides an earlier one."""
    return dict(sorted(record_quote(record_quote(quotes, prev), current).items()))
