"""Polite HTTP client: honest user agent, robots.txt, per-domain spacing, retries."""
from __future__ import annotations

import os
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

_REPO = os.environ.get("GITHUB_REPOSITORY")  # set automatically inside GitHub Actions
USER_AGENT = (
    "Mozilla/5.0 (compatible; ElectricityPicker/1.0"
    + (f"; +https://github.com/{_REPO}" if _REPO else "")
    + "; household plan comparison, runs at most daily)"
)
MIN_INTERVAL_S = 5.0      # minimum gap between two requests to the same host
MAX_REQUESTS_PER_HOST = 20  # hard cap per run, protects retailer sites from runaway loops


class RobotsDisallowed(Exception):
    pass


class RequestBudgetExceeded(Exception):
    pass


class PoliteSession:
    def __init__(self, min_interval: float = MIN_INTERVAL_S, max_per_host: int = MAX_REQUESTS_PER_HOST,
                 timeout: float = 30.0, sleep=time.sleep, clock=time.monotonic):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-SG,en;q=0.9"})
        self.min_interval = min_interval
        self.max_per_host = max_per_host
        self.timeout = timeout
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._count: dict[str, int] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _robots_for(self, url: str):
        p = urlparse(url)
        root = f"{p.scheme}://{p.netloc}"
        if root not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(root + "/robots.txt", timeout=self.timeout)
                if r.status_code == 200 and "text/html" not in r.headers.get("content-type", ""):
                    rp.parse(r.text.splitlines())
                else:
                    # 404 or a bot-challenge page instead of robots.txt: no rules published
                    rp = None
            except requests.RequestException:
                rp = None
            self._robots[root] = rp
        return self._robots[root]

    def allowed(self, url: str) -> bool:
        rp = self._robots_for(url)
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def _throttle(self, host: str):
        n = self._count.get(host, 0)
        if n >= self.max_per_host:
            raise RequestBudgetExceeded(f"{host}: more than {self.max_per_host} requests in one run")
        last = self._last.get(host)
        if last is not None:
            wait = self.min_interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._count[host] = n + 1
        self._last[host] = self._clock()

    def get(self, url: str, retries: int = 2, check_robots: bool = True, **kw) -> requests.Response:
        if check_robots and not self.allowed(url):
            raise RobotsDisallowed(url)
        host = urlparse(url).netloc
        err: Exception | None = None
        for attempt in range(retries + 1):
            self._throttle(host)
            try:
                r = self.session.get(url, timeout=self.timeout, **kw)
                if r.status_code in (429, 502, 503, 504) and attempt < retries:
                    self._sleep(min(60, 10 * (attempt + 1)))
                    continue
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                err = e
                if attempt < retries:
                    self._sleep(5 * (attempt + 1))
        raise err  # type: ignore[misc]
