"""Tariff helpers shared by Ingest (`scraper/`) and Analysis (`analysis/`).

Pure functions and constants only: no I/O, and this package must not import `scraper` or
`analysis` (a test enforces it). It is the single home of the GST encoding, of the quarter
arithmetic ("2026Q3" keys, retailer labels like "Q3 2026") and of the tariff-history merge, so the
two components couple through files plus this neutral module, never through each other's code.
"""
from __future__ import annotations

import datetime as dt
import re

GST_RATE = 0.09                      # Singapore GST
GST_FACTOR = 1 + GST_RATE            # multiply an ex-GST value to get the GST-inclusive one

SGT = dt.timezone(dt.timedelta(hours=8))          # tariff quarters change at 00:00 Singapore time


def merge_history(ses: dict[str, float], datagov: dict[str, float]) -> dict[str, float]:
    """SES first, data.gov.sg overrides/extends (it is updated monthly, SES annually)."""
    merged = dict(ses)
    merged.update(datagov)
    return dict(sorted(merged.items()))


def parse_ts(ts) -> dt.datetime | None:
    """ISO timestamp -> aware datetime (naive input is taken as UTC); None if missing or unreadable."""
    if not ts:
        return None
    try:
        t = dt.datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def quarter_of_ts(ts) -> str | None:
    """Calendar quarter ("2026Q4") in which an ISO timestamp falls, in Singapore time."""
    t = parse_ts(ts)
    if t is None:
        return None
    t = t.astimezone(SGT)
    return f"{t.year}Q{(t.month - 1) // 3 + 1}"


def quarter_key(label) -> str | None:
    """"Q3 2026" (retailer wording) or "2026Q3" -> "2026Q3"; None if it is neither."""
    if not isinstance(label, str):
        return None
    m = re.fullmatch(r"\s*Q([1-4])\s*(\d{4})\s*", label)
    if m:
        return f"{m.group(2)}Q{m.group(1)}"
    m = re.fullmatch(r"\s*(\d{4})\s*Q([1-4])\s*", label)
    return f"{m.group(1)}Q{m.group(2)}" if m else None


def shift_quarter(q: str, k: int = 1) -> str:
    """The quarter `k` quarters after `q` (negative k goes back): ("2026Q4", 1) -> "2027Q1"."""
    y, n = map(int, q.split("Q"))
    idx = y * 4 + (n - 1) + k
    return f"{idx // 4}Q{idx % 4 + 1}"
