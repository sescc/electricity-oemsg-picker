"""Flo Energy: is on the OEM retailer list but currently only offers business plans.

The adapter detects the "register your interest" state explicitly, so the app can say
"no residential plans" instead of silently dropping the retailer.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import Adapter, ScrapeResult


class Flo(Adapter):
    id = "flo"
    name = "Flo Energy"
    homepage = "https://floenergy.sg/"
    plans_url = "https://floenergy.sg/residential"

    def parse(self, raw: str) -> ScrapeResult:
        text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
        if re.search(r"register your interest|coming soon|homes across Singapore soon", text, re.I) \
                and not re.search(r"¢\s*/\s*kWh|cents/kWh", text):
            return ScrapeResult([], status="no_residential_plans",
                                message="Residential plans announced as 'coming soon' (register-interest page).")
        raise ValueError("Flo residential page changed: plans may now be listed; adapter needs updating")
