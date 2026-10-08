# Review — fix-tariff-quarter-gap (+ upgrade-ci-actions)

> Ran after building, 2026-10-08. Checks the change against FRAMEWORK §4.5. Not a prose review.
> Spans Ingest (quotes, consensus), Analysis (extend_history, build_or_keep) and Site (display).

## Coherence laws
- [x] 1. Placement honesty — Analysis reads `tariff_quotes.json` from the checkout that Ingest wrote in the previous workflow step; a missing file is `{}` (`load_json`). Site reads `model_status.json` only through `fetch_data` and tolerates its absence.
- [x] 2. Transmission well-typing — the two new files travel over the existing typed `Trm`s (`git_commit_data` already adds `data/snapshots` and `site/data`; `deploy`/`fetch_data` carry `site/data/*`).
- [x] 3. Placement totality — `record_quote`/`update_quotes` are placed in the runner (Ingest), `extend_history`/`adjacent_dlog`/`build_or_keep` in the runner (Analysis), and `historySeries`/`gapNote`/`modelStatusBadge` in the browser plus Node tests.
- [x] 4. Dependency mediation — when this change shipped, `analysis/models.py` imported `quarter_key` from `scraper` (advisory, same Loc). Resolved by shared-tariff-module (`common/tariff.py`).
- [x] 5. Composition soundness — `extend_history`'s output is `fit_tariff`'s input. `_design` already required adjacent lags, so a gap removes rows rather than creating a two-quarter change. `build_or_keep` makes `build` total.
- [x] 6. runsAt is a relation — the pure helpers are placed in two places: runner + pytest, and browser + node.

## Model delta actually shipped
- As designed, plus: `quarter_of_ts` uses **Singapore time** (design said calendar quarter; SGT was chosen because tariffs change at 00:00 SGT). `consensus_current` gains `ignored_sources`. Absorbed in Ingest ARCHITECTURE §4 and IMPLEMENTATION.
- `ModelStatus` lives in its own file `site/data/model_status.json`, not in `status.json` (one writer per file). The spec and design were updated before the code was written.
- `ewma_vol` now takes one-quarter log changes instead of levels. Recorded in Analysis IMPLEMENTATION.
- Quote-sourced quarters publish the GST-inclusive value exactly as quoted (`quoted_incl_gst`), added in shared-tariff-module after a 0.01 round-trip drift was found.

## Modeling smells swept (§3)
- No parallel object: `TariffQuotes` is the persisted past of `RegulatedTariff`, keyed by quarter, not a second tariff type.
- Deduced, not copied: `history_gaps` and `source` are deduced at build time from official ∪ quotes and are not stored by Ingest.
- One source of truth: each quarter's quote is written only by `record_quote`. The model's current tariff equals the plans quote (test in `tests/test_common.py`).

## Verification
- pytest 55 → 70 → (change D) green; node 20 → 35 green.
- End-to-end on a scratch clone of origin with today's real snapshots: Q3 was back-filled from the previous `plans.json` and Q4 recorded; the build exits 0 with `current_quarter 2026Q4`, `history_gaps []` and `model_status ok`.
- Not yet verified: a CI run on GitHub (needs the user's push).
