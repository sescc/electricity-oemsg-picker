"""Senoko Energy: server-rendered plan cards on /households/price-plans."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..schema import make_plan, parse_hour
from .base import Adapter, ScrapeResult

CENTS = r"(\d{1,2}\.\d{1,2})\s*¢/kWh"


class Senoko(Adapter):
    id = "senoko"
    name = "Senoko Energy"
    homepage = "https://www.senokoenergy.com/"
    plans_url = "https://www.senokoenergy.com/households/price-plans"

    def parse(self, raw: str) -> ScrapeResult:
        soup = BeautifulSoup(raw, "lxml")
        plans, obs = [], {}
        page_text = soup.get_text(" ", strip=True)
        m = re.search(r"prevailing SP tariff of\s*" + CENTS, page_text)
        banner = re.search(r"(Q[1-4])\s*(\d{4})\s*SP Tariff of\s*" + CENTS, page_text, re.I)
        prevailing = float(m.group(1)) if m else None
        quoted = float(banner.group(3)) if banner else None
        if prevailing is not None:
            obs["regulated_tariff_cents_incl_gst"] = prevailing
        elif quoted is not None:
            obs["regulated_tariff_cents_incl_gst"] = quoted
        # The label is trusted only when the banner and the "prevailing" sentence agree (or the banner is all
        # there is): they are edited separately, so a mismatch means one is out of date. No label beats a wrong one.
        if banner and (prevailing is None or prevailing == quoted):
            obs["tariff_quarter"] = f"{banner.group(1).upper()} {banner.group(2)}"
        for card in soup.select("div.promotions-card"):
            fs = card.find("a", href=re.compile(r"FS\?plancode=HH-"))
            if not fs:
                continue  # promotion cards (bank/GIRO gifts) are not price plans
            text = card.get_text(" | ", strip=True)
            mm = re.match(r"(\d+)-month plan \| ([^|]+) \|", text)
            if not mm:
                continue
            months, name = int(mm.group(1)), mm.group(2).strip()
            factsheet = urljoin(self.plans_url, fs["href"])
            code = re.search(r"plancode=([^&]+)", fs["href"]).group(1)
            common = dict(retailer_id=self.id, retailer=self.name, name=name,
                          contract_months=months, source_url=self.plans_url,
                          factsheet_url=factsheet, plan_code=code)
            reb = re.search(r"up to \| \$(\d+) rebate", text)
            if "Peak" in text and "Off-Peak" in text:
                pk = re.search(r"Peak \| (\d{1,2}(?:am|pm)) to (\d{1,2}(?:am|pm)) every day \| " + CENTS, text)
                op = re.search(r"Off-Peak \| (\d{1,2}(?:am|pm)) to (\d{1,2}(?:am|pm)) every day \| " + CENTS, text)
                if not (pk and op):
                    continue
                plan = make_plan(price_type="tou", rates={
                    "periods": [{"rate": float(pk.group(3)), "windows": [
                        {"days": "all", "start": parse_hour(pk.group(1)), "end": parse_hour(pk.group(2))}]}],
                    "default_rate": float(op.group(3)),
                }, **common)
            elif "Discount" in text:
                d = re.search(r"(\d{1,2}\.\d{1,2})¢/kWh Discount", text)
                if not d:
                    continue
                plan = make_plan(price_type="dot_cents", rates={"discount_cents": float(d.group(1))}, **common)
            else:
                r = re.search(r"fixed rate \| " + CENTS, text)
                if not r:
                    continue
                plan = make_plan(price_type="fixed", rates={"rate": float(r.group(1))}, **common)
            if reb:
                plan["rebate_sgd"] = float(reb.group(1))
                plan["rebate_note"] = "Up to amount; mostly conditional on credit-card/GIRO recurring payment or promo code."
            plan["green"] = "green" in name.lower()
            plans.append(plan)
        return ScrapeResult(plans, observations=obs)
