"""Normalised price-plan schema shared by every retailer adapter.

All money values are GST-inclusive. Rates are cents/kWh, daily charges cents/day,
rebates and fees in SGD. Parsers convert at parse time (never at display time) so
plans from different retailers are directly comparable.

price_type:
  fixed      {"rate": c}
  dot_pct    {"discount_pct": d}          % off the prevailing regulated tariff
  dot_cents  {"discount_cents": d}        cents/kWh off the prevailing regulated tariff
  tou        {"periods": [{"rate": c, "windows": [{"days": "all|weekday|weekend",
                                                   "start": h, "end": h}]}],
              "default_rate": c}           hours not covered by any window use default_rate
  block      {"blocks": [{"upto_kwh": n|None, "rate": c}, ...]}  marginal blocks per bill
"""
from __future__ import annotations

import re

GST = 0.09
PRICE_TYPES = {"fixed", "dot_pct", "dot_cents", "tou", "block"}
SANE_RATE = (8.0, 70.0)         # cents/kWh incl. GST; anything outside is a parse error
SANE_CONTRACT = {0, 6, 12, 18, 24, 25, 36, 48, 60}


def with_gst(cents_ex: float) -> float:
    return round(cents_ex * (1 + GST), 3)


def slug(*parts: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", " ".join(parts).lower()).strip("-")


def make_plan(*, retailer_id: str, retailer: str, name: str, price_type: str, rates: dict,
              contract_months: int, source_url: str, **extra) -> dict:
    plan = {
        "id": slug(retailer_id, name, str(contract_months)),
        "retailer_id": retailer_id,
        "retailer": retailer,
        "name": name.strip(),
        "price_type": price_type,
        "rates": rates,
        "contract_months": int(contract_months),
        "daily_charge_cents": 0.0,
        "rebate_sgd": 0.0,
        "rebate_note": None,
        "standard": None,          # EMA "Standard" vs "Non-Standard" price plan
        "green": False,
        "smart_meter_required": price_type == "tou",
        "eligibility": None,       # e.g. "sp_customers_only"
        "conditions": [],          # plain-language caveats shown to the user
        "factsheet_url": None,
        "source_url": source_url,
        "terms": {},
    }
    plan.update(extra)
    return plan


def validate_plan(p: dict) -> list[str]:
    """Return a list of problems; empty means the plan is usable."""
    errs = []
    if p.get("price_type") not in PRICE_TYPES:
        errs.append(f"unknown price_type {p.get('price_type')!r}")
        return errs
    if p.get("contract_months") not in SANE_CONTRACT:
        errs.append(f"odd contract length {p.get('contract_months')}")
    r = p.get("rates") or {}
    lo, hi = SANE_RATE

    def chk(v, what):
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            errs.append(f"{what}={v!r} outside {lo}-{hi} c/kWh")

    t = p["price_type"]
    if t == "fixed":
        chk(r.get("rate"), "rate")
    elif t == "dot_pct":
        d = r.get("discount_pct")
        if not isinstance(d, (int, float)) or not 0 < d < 40:
            errs.append(f"discount_pct={d!r}")
    elif t == "dot_cents":
        d = r.get("discount_cents")
        if not isinstance(d, (int, float)) or not 0 < d < 15:
            errs.append(f"discount_cents={d!r}")
    elif t == "tou":
        periods = r.get("periods") or []
        if not periods:
            errs.append("tou without periods")
        for per in periods:
            chk(per.get("rate"), "tou rate")
            for w in per.get("windows", []):
                if w.get("days") not in ("all", "weekday", "weekend") or not (
                        0 <= w.get("start", -1) <= 24 and 0 <= w.get("end", -1) <= 24):
                    errs.append(f"bad window {w}")
        chk(r.get("default_rate"), "default_rate")
    elif t == "block":
        blocks = r.get("blocks") or []
        if not blocks or blocks[-1].get("upto_kwh") is not None:
            errs.append("block plan must end with an open-ended block")
        for b in blocks:
            chk(b.get("rate"), "block rate")
    if not 0 <= p.get("daily_charge_cents", 0) <= 300:
        errs.append(f"daily_charge_cents={p.get('daily_charge_cents')}")
    if not 0 <= p.get("rebate_sgd", 0) <= 1000:
        errs.append(f"rebate_sgd={p.get('rebate_sgd')}")
    return errs


def parse_hour(s: str) -> int:
    """'7am' -> 7, '11pm' -> 23, '12am' -> 0, '12pm' -> 12, '7' -> 7."""
    m = re.fullmatch(r"\s*(\d{1,2})(?:[.:]00)?\s*(am|pm)?\s*", s.lower())
    if not m:
        raise ValueError(s)
    h, ap = int(m.group(1)), m.group(2)
    if ap == "am":
        h = 0 if h == 12 else h
    elif ap == "pm":
        h = 12 if h == 12 else h + 12
    return h


def money(s: str) -> float:
    return float(re.sub(r"[^\d.]", "", s))
