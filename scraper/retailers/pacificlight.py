"""PacificLight: the plans page loads /json/plan.json, which carries the EMA fact-sheet price text.

The headline figure on PacificLight's page is the *lowest tier* of tiered plans, so we never
use it; the full rate structure is parsed from `factsheetPrice`. Plans whose structure cannot
be parsed are dropped (and reported) rather than ranked on a misleading number.
"""
from __future__ import annotations

import html
import json
import re

from ..schema import make_plan, parse_hour
from .base import Adapter, ScrapeResult

C = r"(\d{1,2}\.\d{1,3})\s*¢/kWh"
HR = r"(\d{1,2}(?:am|pm))"


def _clean(s: str) -> str:
    s = html.unescape(s or "").replace("&cent", "¢")
    s = re.sub(r"<br\s*/?>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_price_text(price: str) -> tuple[str, dict, float] | None:
    """Fact-sheet price sentence -> (price_type, rates, daily_charge_cents). None if unknown."""
    p = _clean(price)
    daily = 0.0
    if m := re.search(r"Daily Charge (?:of )?(\$\d+\.\d+|\d+(?:\.\d+)?¢)/day", p):
        v = m.group(1)
        daily = float(v[1:]) * 100 if v.startswith("$") else float(v[:-1])
    if m := re.search(r"Discount off regulated tariff plan: (\d+(?:\.\d+)?)% off(?: and (\d+(?:\.\d+)?)% Prompt Payment Discount)?", p, re.I):
        pct = float(m.group(1)) + (float(m.group(2)) if m.group(2) else 0.0)
        return "dot_pct", {"discount_pct": pct}, daily
    if "Stack" in p:
        blocks = []
        for m in re.finditer(r"(below|\d+ to|above) (\d+)\s*kWh\s*@\s*" + C, p):
            kind, n, rate = m.group(1), int(m.group(2)), float(m.group(3))
            if kind == "below":
                blocks.append({"upto_kwh": n, "rate": rate})
            elif kind == "above":
                blocks.append({"upto_kwh": None, "rate": rate})
            else:
                blocks.append({"upto_kwh": n, "rate": rate})
        return ("block", {"blocks": blocks}, daily) if blocks else None
    tiers = re.findall(C + r"[^¢]*?from " + HR + r" to " + HR, p) or [
        (r, a, b) for (r, a, b) in re.findall(C + r" during (?:off )?peak periods from " + HR + r" to " + HR, p)]
    if len(tiers) == 2:
        # the dearer tier becomes the explicit window, the cheaper one the default
        (r1, a1, b1), (r2, a2, b2) = sorted(tiers, key=lambda t: -float(t[0]))
        return "tou", {"periods": [{"rate": float(r1), "windows": [
            {"days": "all", "start": parse_hour(a1), "end": parse_hour(b1)}]}],
            "default_rate": float(r2)}, daily
    if m := re.search(r"Fixed price plan: " + C, p, re.I) or re.match(C, p):
        return "fixed", {"rate": float(m.group(1))}, daily
    return None


class PacificLight(Adapter):
    id = "pacificlight"
    name = "PacificLight"
    homepage = "https://pacificlight.com.sg/"
    plans_url = "https://pacificlight.com.sg/json/plan.json"
    page_url = "https://pacificlight.com.sg/home/plans-new"

    def fetch(self, session) -> str:
        # page first (for the quoted tariff), then the JSON it loads
        page = session.get(self.page_url).text
        data = session.get(self.plans_url).content.decode("utf-8-sig")
        return json.dumps({"page": page, "plans": json.loads(data)})

    def parse(self, raw: str) -> ScrapeResult:
        blob = json.loads(raw)
        items = blob["plans"] if isinstance(blob, dict) else blob
        obs = {}
        if isinstance(blob, dict) and (m := re.search(r"Regulated Tariff in (Q\d \d{4}) = <span>(\d+\.\d+)</span>", blob.get("page", ""))):
            obs = {"regulated_tariff_cents_incl_gst": float(m.group(2)), "tariff_quarter": m.group(1)}
        plans, skipped = [], []
        for it in items:
            lm = it.get("learnMore") or {}
            parsed = parse_price_text(lm.get("factsheetPrice", ""))
            if not parsed:
                skipped.append(it.get("title"))
                continue
            ptype, rates, daily = parsed
            month = it.get("month", "")
            months = 0 if "no contract" in month.lower() else int(re.search(r"\d+", month).group())
            details = [_clean(d) for d in lm.get("details", [])]
            plan = make_plan(retailer_id=self.id, retailer=self.name, name=it["title"].strip(),
                             price_type=ptype, rates=rates, contract_months=months,
                             source_url=self.page_url, factsheet_url=lm.get("factsheet"),
                             standard=(lm.get("factsheetType", "").lower() == "standard"),
                             daily_charge_cents=daily, plan_code=it.get("plancode"))
            plan["smart_meter_required"] = it.get("smartmeter") == "yes" or ptype == "tou"
            plan["green"] = any("REC" in d for d in details)
            if "Prompt Payment" in lm.get("factsheetPrice", ""):
                plan["conditions"].append("Part of the discount is a prompt-payment discount (GIRO only).")
            terms = {}
            if any("No early termination charge" in d for d in details):
                terms["early_termination_fee_sgd"] = 0.0
                terms["etf_text"] = "No early termination charge (retailer plan data)."
            if lm.get("factsheetRenewal"):
                terms["auto_renewal_text"] = _clean(lm["factsheetRenewal"])[:400]
            if terms:
                terms["source_url"] = self.plans_url
                plan["terms"] = terms
            plan["extras"] = details
            plans.append(plan)
        msg = f"skipped unparseable: {', '.join(skipped)}" if skipped else ""
        return ScrapeResult(plans, message=msg, observations=obs)
