# Design — fix-tariff-quarter-gap

## Model delta (objects and morphisms)
New `Dat`
- `TariffQuotes` = `Quarter ⇀ {cents_incl_gst, observed_at, sources, revised_from?}`, stored at
  `data/snapshots/tariff_quotes.json`. Owner: Ingest. Reader: Analysis.
- `ModelStatus` = `{state ∈ {ok, stale}, model_as_of, checked_at, error?}` at
  `site/data/model_status.json` — its own file so `status.json` keeps one writer (Ingest).

New / changed `Trn`
| Morphism | Signature | Partiality | Semantics |
| --- | --- | --- | --- |
| `consensus_current` (changed) | `TariffObservation* × now → RegulatedTariff` | Partial | observations whose `as_of` is in an earlier calendar quarter than the newest `as_of` are dropped; mode of the rest, ties → most recent `as_of`; `quarter` only from an agreeing source with label ∈ [quarter(as_of), quarter(as_of)+1], else `None` |
| `record_quote` | `TariffQuotes × RegulatedTariff → TariffQuotes` | Total | identity unless the quote is labelled and not stale; same value → unchanged; different value → overwrite, keep `revised_from` |
| `extend_history` (replaces `extend?`) | `TariffDataset × TariffQuotes × RegulatedTariff → TariffDataset × Gaps` | Total | appends quote quarters strictly after the official end; `Gaps` = missing quarters between official end and the last quarter; never interpolates |
| `adjacent_dlog` | `TariffDataset → ℝ*` | Total | log changes only between consecutive quarters (feeds hist SD and EWMA) |
| `build_or_keep` | `Inputs × model.json(prev) → model.json × ModelStatus` | Total | `build` on success; on any exception keeps the previous file and reports `stale` |

## §3 consolidation check
`TariffQuotes` is not a new kind of tariff: it is the persisted history of the existing
`RegulatedTariff` object (one value per quarter). The current `regulated_tariff` in
`plans.json` stays the single "now" value; `TariffQuotes` is its past. No parallel type.

## §4.5 coherence laws kept
- Law 1 (inputs delivered): Analysis reads `tariff_quotes.json` from the same checkout that
  Ingest wrote in the previous workflow step; a missing file is the empty map.
- Law 2 (typed cross-Loc flows): `tariff_quotes.json` travels via the existing `git_commit_data`.
- Law 4: still advisory until change `shared-tariff-module` removes the `scraper` import.
- Pipe-and-filter: `extend_history` output is `fit_tariff`'s input; `_design` already requires
  adjacent lags, so a gap removes rows rather than creating a fake two-quarter change.

## Decisions
- Quotes are recorded from real observations only; the Q3 2026 value is back-filled by code
  from the previous `plans.json`, not hand-entered ("no invented numbers").
- Label may be one quarter ahead of the observation date: retailers pre-announce the next
  quarter's tariff in the last days of a quarter.
- Model failure degrades (user requirement 2026-10-08: the site runs unattended); pytest
  failure still halts the job, because that means the code itself is broken.
