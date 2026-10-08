## ADDED Requirements

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
