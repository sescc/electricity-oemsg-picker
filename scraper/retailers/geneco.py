"""Geneco: plans and rates are embedded as `var genecoObj = {...}` in the WordPress page."""
from __future__ import annotations

import json
import re

from common.tariff import GST_FACTOR

from ..schema import make_plan
from .base import Adapter, ScrapeResult


def _extract_obj(raw: str) -> dict:
    i = raw.find("var genecoObj")
    if i < 0:
        raise ValueError("genecoObj not found")
    start = raw.index("{", i)
    obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    return obj


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


class Geneco(Adapter):
    id = "geneco"
    name = "Geneco"
    homepage = "https://www.geneco.sg/"
    plans_url = "https://www.geneco.sg/residential/electricity-plans/"

    def parse(self, raw: str) -> ScrapeResult:
        obj = _extract_obj(raw)
        rates = {}
        for r in obj.get("ratesData", {}).get("data", {}).get("Result", []):
            rates.setdefault(r["RateReference"], []).append(r)
        plans = []
        for p in obj.get("planData", []):
            rs = rates.get(p.get("RateReference"))
            if not rs:
                continue
            r = rs[0]
            gst = float(r.get("GSTRate") or GST_FACTOR)
            to_c = lambda x: round(float(x) * 100 * gst, 2)  # SGD/kWh ex-GST -> cents/kWh incl. GST
            common = dict(retailer_id=self.id, retailer=self.name, name=p["Name"],
                          contract_months=int(p.get("ContractDuration") or 0),
                          source_url=self.plans_url, factsheet_url=p.get("FactsheetUrl"),
                          standard=(p.get("PlanType") == "Standard"), plan_code=p.get("RateReference"))
            if r.get("TierKind") == "A" and float(r.get("Rate") or 0) > 0:
                plan = make_plan(price_type="fixed", rates={"rate": to_c(r["Rate"])}, **common)
            elif float(r.get("PRate") or 0) > 0 and float(r.get("OPRate") or 0) > 0:
                # Hours are not in the rate record; Geneco's 2-tier plan is published as
                # 7am-7pm (peak) / 7pm-7am (off-peak). Checked by the fixture test.
                hours = re.search(r"(\d{1,2})\s*To\s*(\d{1,2})", p["Name"], re.I)
                if not hours:
                    continue
                plan = make_plan(price_type="tou", rates={
                    "periods": [{"rate": to_c(r["PRate"]), "windows": [{"days": "all", "start": 7, "end": 19}]}],
                    "default_rate": to_c(r["OPRate"]),
                }, **common)
                plan["smart_meter_required"] = True
            else:
                continue
            promo = _strip_html(p.get("PromotionDeal"))
            nums = [float(x) for x in re.findall(r"\$(\d+) (?:bill )?rebate", promo)]
            if nums:
                plan["rebate_sgd"] = max(nums)
                plan["rebate_note"] = promo[:240]
                if "SP Customers" in promo and len(nums) > 1:
                    plan["rebate_sgd_non_sp"] = min(nums)
                    plan["conditions"].append("Largest rebate only for customers switching from SP Group.")
            plans.append(plan)
        return ScrapeResult(plans)
