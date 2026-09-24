"""Retailers whose data is maintained by hand in data/curated/<id>.json."""
from __future__ import annotations

import json
from pathlib import Path

from ..schema import make_plan
from .base import Adapter, ScrapeResult

CURATED_DIR = Path(__file__).resolve().parents[2] / "data" / "curated"


class CuratedAdapter(Adapter):
    method = "curated"

    def load(self) -> tuple[ScrapeResult, dict]:
        doc = json.loads((CURATED_DIR / f"{self.id}.json").read_text(encoding="utf-8"))
        plans = []
        for p in doc["plans"]:
            p = dict(p)
            plan = make_plan(retailer_id=self.id, retailer=self.name, name=p.pop("name"),
                             price_type=p.pop("price_type"), rates=p.pop("rates"),
                             contract_months=p.pop("contract_months"),
                             source_url=doc["verified_from"], **p)
            plans.append(plan)
        return ScrapeResult(plans, message=doc["note"]), doc

    def scrape(self, session) -> ScrapeResult:  # pragma: no cover - never scraped
        raise RuntimeError(f"{self.id} is curated-only: {self.curated_reason}")


class Keppel(CuratedAdapter):
    id = "keppel"
    name = "Keppel Electric"
    homepage = "https://www.keppelelectric.com/"
    plans_url = "https://www.keppelelectric.com/residential-price-plan"
    curated_reason = "robots.txt disallows the /api/ endpoints the plan page is rendered from"


class Sembcorp(CuratedAdapter):
    id = "sembcorp"
    name = "Sembcorp Power"
    homepage = "https://www.sembcorppower.com/"
    plans_url = "https://www.sembcorppower.com/"
    curated_reason = "site is behind a Cloudflare bot challenge; we do not bypass bot protection"
