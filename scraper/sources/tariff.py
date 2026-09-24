"""Regulated tariff: monthly history (data.gov.sg / SingStat) and the current quarter.

The history series excludes GST. The current quarter's GST-inclusive tariff is quoted on
several retailer pages (scraped as `observations`); we take the consensus and cross-check it
against the history where they overlap.
"""
from __future__ import annotations

import re
from collections import Counter

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


def consensus_current(observations: dict[str, dict]) -> dict | None:
    """observations: {retailer_id: {"regulated_tariff_cents_incl_gst": x, ...}}"""
    vals = {rid: o["regulated_tariff_cents_incl_gst"] for rid, o in observations.items()
            if o.get("regulated_tariff_cents_incl_gst")}
    if not vals:
        return None
    value, n = Counter(vals.values()).most_common(1)[0]
    quarter = next((o.get("tariff_quarter") for o in observations.values() if o.get("tariff_quarter")), None)
    return {"cents_incl_gst": value, "quarter": quarter, "agreeing_sources": sorted(k for k, v in vals.items() if v == value),
            "disagreeing_sources": {k: v for k, v in vals.items() if v != value}, "n_sources": len(vals)}


def merge_history(ses: dict[str, float], datagov: dict[str, float]) -> dict[str, float]:
    """SES first, data.gov.sg overrides/extends (it is updated monthly, SES annually)."""
    merged = dict(ses)
    merged.update(datagov)
    return dict(sorted(merged.items()))
