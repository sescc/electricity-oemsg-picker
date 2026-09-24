from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScrapeResult:
    plans: list[dict]
    # ok | no_residential_plans
    status: str = "ok"
    message: str = ""
    # extra facts the adapter noticed, e.g. the regulated tariff quoted on the page
    observations: dict = field(default_factory=dict)


class Adapter:
    """One per retailer. `fetch` does I/O, `parse` is pure so it can be tested on fixtures."""
    id: str = ""
    name: str = ""
    homepage: str = ""
    plans_url: str = ""
    # "scrape" = automated; "curated" = hand-verified snapshot only (reason in curated_reason)
    method: str = "scrape"
    curated_reason: str = ""

    def fetch(self, session) -> str:
        return session.get(self.plans_url).text

    def parse(self, raw: str) -> ScrapeResult:
        raise NotImplementedError

    def scrape(self, session) -> ScrapeResult:
        return self.parse(self.fetch(session))
