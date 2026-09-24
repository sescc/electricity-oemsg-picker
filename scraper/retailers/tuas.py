"""Tuas Power: server-rendered `div.price_box` cards (site sits behind Incapsula; may fail in CI)."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..schema import make_plan
from .base import Adapter, ScrapeResult


class Tuas(Adapter):
    id = "tuas"
    name = "Tuas Power"
    homepage = "https://www.savewithtuas.com/"
    plans_url = "https://www.savewithtuas.com/our-electricity-plans/"

    def parse(self, raw: str) -> ScrapeResult:
        soup = BeautifulSoup(raw, "lxml")
        plans = []
        for box in soup.select("div.price_box"):
            text = box.get_text(" | ", strip=True)
            head = re.match(r"([^|]+?) \| (?:Green Plan \| )?(\d+) Months \|", text)
            if not head:
                continue
            name, months = head.group(1).strip(), int(head.group(2))
            links = {a.get_text(strip=True): urljoin(self.plans_url, a["href"])
                     for a in box.find_all("a", href=True) if a["href"]}
            common = dict(retailer_id=self.id, retailer=self.name, name=name, contract_months=months,
                          source_url=self.plans_url, factsheet_url=links.get("Factsheet"),
                          terms_url=links.get("Terms & Conditions"))
            fixed = re.search(r"Fixed Rate \(with GST\) \| \$(0\.\d{3,4}) \| /kWh", text)
            dot = re.search(r"% Discount off Tariff \| (\d{1,2}(?:\.\d+)?)%", text)
            if fixed:
                plan = make_plan(price_type="fixed", rates={"rate": round(float(fixed.group(1)) * 100, 2)}, **common)
            elif dot:
                plan = make_plan(price_type="dot_pct", rates={"discount_pct": float(dot.group(1))}, **common)
            else:
                continue
            reb = re.search(r"Bill Rebate \| \$(\d+)", text)
            if reb:
                plan["rebate_sgd"] = float(reb.group(1))
                code = re.search(r"Promo Code \| (\w+)", text)
                plan["rebate_note"] = "One-time bill rebate" + (f" with promo code {code.group(1)}" if code else "")
            plan["green"] = "Green Plan" in text or "G+" in name
            if terms := common.get("terms_url"):
                plan["standard"] = "non-standard" not in terms.lower()
            plans.append(plan)
        return ScrapeResult(plans)
