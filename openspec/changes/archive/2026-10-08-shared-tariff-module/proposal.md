# shared-tariff-module

## Why
Backlog suggestions #1–#3 (`docs/suggestions.md`):
- #1 Analysis imports `merge_history` from Ingest code (`scraper.sources.tariff`) — the Law 4
  advisory. After `fix-tariff-quarter-gap` both components also parse quarter labels
  ("Q3 2026" → "2026Q3"), which would duplicate the rule.
- #2 GST is `0.09` in `scraper/schema.py`, `1.09` in `analysis/build.py` and a `1.09` fallback in
  `scraper/retailers/geneco.py`; a GST change could be applied half-way.
- #3 The current tariff is published twice (`plans.json.regulated_tariff`,
  `model.json.tariff.current_incl_gst`); their agreement is assumed, not checked.

## What changes
- New package `common/` with `common/tariff.py`: `GST_RATE`, `GST_FACTOR`, `merge_history`,
  `quarter_key` (label → "YYYYQn"), `parse_ts`, `quarter_of_ts` (Singapore time), `shift_quarter`. Ingest and Analysis import it;
  Analysis no longer imports `scraper`.
- A test asserts the two published current-tariff copies agree; docs name `model.json` as the
  copy the MDP reads and `plans.json` as the one the freshness banner shows.

## Impact
No change to published JSON values. Code: `common/`, `scraper/schema.py`,
`scraper/sources/tariff.py`, `scraper/retailers/geneco.py`, `analysis/build.py`,
`analysis/models.py`, tests. Docs: root IMPLEMENTATION (new shared code root), Ingest/Analysis
ARCHITECTURE ports, `suggestions.md` #1–#3 closed.
