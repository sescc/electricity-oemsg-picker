# tariff-data Specification

## Purpose
The regulated-tariff data published to the browser: the current quarter's tariff in
`plans.json`, the tariff history and forecast in `model.json`, and the model's freshness in
`model_status.json`. This capability covers how quarters are labelled, how the lagging
official series is extended with retailer quotes, and how failures degrade without stopping
the daily refresh.

## Requirements

### Requirement: Tariff history survives the quarter change
The published `model.json` tariff history SHALL include every quarter whose regulated tariff was
quoted by retailers, even after the official statistics series stops covering it, and each
history row SHALL state whether it is `official` or a `retailer_quote`.

#### Scenario: Quote rolls to the next quarter while the official series lags
- **WHEN** the official series ends at 2026Q2, a 2026Q3 quote was recorded earlier, and today's quote is for 2026Q4
- **THEN** the refresh succeeds, `tariff.current_quarter` is `2026Q4`, and `tariff.history` contains 2026Q3 with `source: "retailer_quote"`

#### Scenario: A quarter was never observed
- **WHEN** no quote was ever recorded for 2026Q3 and today's quote is for 2026Q4
- **THEN** the refresh still succeeds, 2026Q3 is absent from `tariff.history` (not interpolated), and `tariff.history_gaps` lists `"2026Q3"`

### Requirement: Current tariff consensus ignores pre-quarter-change leftovers
The current regulated tariff in `plans.json` SHALL be derived only from observations in the
newest calendar quarter observed, and its `quarter` label SHALL come only from a source that
agrees with the chosen value.

#### Scenario: Stale snapshot from the previous quarter
- **WHEN** one retailer's last good snapshot (30 Sep) quotes 34.78 for Q3 and another retailer fetched on 2 Oct quotes 31.16
- **THEN** `regulated_tariff.cents_incl_gst` is 31.16

#### Scenario: Only a disagreeing source carries a label
- **WHEN** the consensus value comes from a source with no quarter label and the only labelled source disagrees
- **THEN** `regulated_tariff.quarter` is null and the quote is not recorded in the quote history

### Requirement: A model failure does not stop the site refreshing
If fitting the models fails, the refresh SHALL keep the previous `model.json`, still publish the
newly scraped plans, and report the model's state in `site/data/model_status.json`.

#### Scenario: Models fit normally
- **WHEN** the model build succeeds
- **THEN** `model_status.json.state` is `ok` and `model_as_of` equals the new `model.json.generated_at`

#### Scenario: Model build raises
- **WHEN** the model build raises an exception
- **THEN** the step exits successfully, `model.json` is unchanged, `model_status.json.state` is `stale` with the error text, and the site shows when the model was last fitted

### Requirement: Published current tariff is consistent
When the retailer-quoted tariff is for a quarter after the official statistics, the current
tariff in `model.json` (`tariff.current_incl_gst`) SHALL equal `plans.json`
`regulated_tariff.cents_incl_gst`, and both SHALL use the same GST factor.

#### Scenario: Quote newer than the official series
- **WHEN** `plans.json` quotes 31.16¢ for Q4 2026 and the official series ends at 2026Q2
- **THEN** `model.json` reports `current_quarter` 2026Q4 and `current_incl_gst` 31.16

#### Scenario: No usable quote
- **WHEN** `plans.json` has no labelled quote (null quarter)
- **THEN** `model.json` falls back to the latest recorded or official quarter, and its value is not claimed to match `plans.json`
