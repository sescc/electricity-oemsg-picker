# fix-tariff-quarter-gap

## Why
`Refresh plan data` has failed daily since 2026-10-01 at "Fit models" with
`KeyError: '2026Q3'` (`analysis/build.py:77`), so Pages has not deployed since 2026-09-30.
The official tariff history (EMA SES + data.gov.sg) lags and ends at 2026Q2; Q3 2026 only ever
existed as the live retailer quote in `plans.json.regulated_tariff`. When the quote rolled to
Q4 2026 the Q3 value was lost and the history had a hole. Quotes were never persisted, so this
recurs every quarter. Separately, one bad model input halts the whole refresh, which conflicts
with the user's requirement that the site run unattended and degrade visibly.

## What changes
- Ingest records every labelled, fresh tariff quote per quarter in `data/snapshots/tariff_quotes.json`
  and back-fills the previous run's quote before overwriting `plans.json` (self-healing seed).
- The current-tariff consensus ignores observations from an earlier calendar quarter than the
  newest one, breaks ties by recency, and takes the quarter label only from an agreeing source
  whose label is in the quarter of its observation or the next one.
- Analysis extends the official history with recorded quotes, tolerates gaps (reported, never
  interpolated), and computes volatility from adjacent-quarter changes only.
- `model.json` gains `tariff.history[].source` and `tariff.history_gaps`; the UI marks
  quote-sourced points and warns about gaps.
- A model-fitting failure keeps the last good `model.json`, records its state in
  `site/data/model_status.json`, and lets the refresh commit and deploy (supersedes decision R5 for model failures).

- CI (folded in): GitHub Actions bumped to Node-24 majors and runners pinned to `ubuntu-24.04`
  (Node 20 deprecation warnings; `ubuntu-latest` becomes Ubuntu 26 on 2026-10-19).

## Impact
- Code: `scraper/sources/tariff.py`, `scraper/run.py`, `analysis/build.py`, `site/js/app.js`, tests.
- Published JSON: `model.json` (additive fields), `status.json` (`model_status`), new snapshot file.
- Docs: Ingest, Analysis, Site ARCHITECTURE/IMPLEMENTATION/STATUS; CLAUDE.md log.
