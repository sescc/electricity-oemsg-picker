## ADDED Requirements

### Requirement: Current tariff quarter is confirmed by more than one retailer
The current tariff's quarter label SHALL be available whenever either PacificLight or Senoko quotes a
labelled tariff that agrees with the consensus value.

#### Scenario: PacificLight unavailable, Senoko labels the quarter
- **WHEN** PacificLight's scrape fails and Senoko's page says "Q4 2026 SP Tariff of 31.16¢/kWh" and "prevailing SP tariff of 31.16¢/kWh"
- **THEN** `plans.json.regulated_tariff.quarter` is "Q4 2026" and the quote is recorded for 2026Q4

#### Scenario: Senoko's page contradicts itself
- **WHEN** Senoko's banner says "Q4 2026 SP Tariff of 31.16" but its plan cards say "prevailing SP tariff of 34.78"
- **THEN** Senoko's observation has value 34.78 and no quarter label

### Requirement: An unconfirmed or inconsistent current tariff is flagged on the page
The page SHALL warn when the current tariff in `plans.json` has no quarter label or differs from the
tariff the forecast in `model.json` starts from.

#### Scenario: Labelled and consistent
- **WHEN** `regulated_tariff` is {31.16, "Q4 2026"} and `model.json.tariff.current_incl_gst` is 31.16
- **THEN** no tariff warning is shown

#### Scenario: Unlabelled quote
- **WHEN** `regulated_tariff.quarter` is null
- **THEN** a warning says the quarter could not be confirmed and names the quarter and value the forecast uses
