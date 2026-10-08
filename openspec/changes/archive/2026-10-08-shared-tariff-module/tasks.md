# Tasks — shared-tariff-module

- [x] 1.1 `common/__init__.py`, `common/tariff.py` (GST_RATE, GST_FACTOR, merge_history, quarter_key, parse_ts, quarter_of_ts, shift_quarter)
- [x] 1.2 Switch `scraper/schema.py`, `scraper/sources/tariff.py`, `scraper/retailers/geneco.py` fallback, `analysis/build.py`, `analysis/models.py` to it; no `scraper` import left in `analysis/`
- [x] 1.3 Tests: common helpers; published current-tariff agreement (#3); grep-style test that `analysis/` does not import `scraper`
- [x] 2.1 IMPLEMENTATION.md rows (root shared code root; Ingest, Analysis)
- [x] 2.2 Reconcile ARCHITECTURE.md, IMPLEMENTATION.md and STATUS.md; close suggestions #1–#3
- [x] 2.3 Drift check passes
- [x] 2.4 Update the decision and edge-case log in CLAUDE.md
