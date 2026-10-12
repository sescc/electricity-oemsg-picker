# test-ingest-rate-rules

## Why
`docs/ingest/STATUS.md` "Needs work" #2: composition rules 6 and 8 of `docs/ingest/ARCHITECTURE.md`
have no tests.
- Rule 6 (R4): each fact-sheet URL is fetched at most once, errors are retried after 7 days, and at most
  25 are fetched per run (`scraper/run.py:enrich_terms`).
- Rule 8 (R3): datasets are refreshed at most every 7 days, and a failed source keeps its previous value
  (`scraper/run.py:run_datasets`).

## What changes
Offline tests only, in `tests/test_ingest_rate_rules.py`, using a fake session and monkeypatched
`SNAP` / source fetchers. No production code changes unless a test exposes a bug. Any bug found is
reported and fixed in the same change, with a CLAUDE.md edge-case row.

## Impact
No behaviour change. Docs: Ingest IMPLEMENTATION/STATUS (rules 6 and 8 marked tested), root STATUS,
CLAUDE.md test count.
