# Design — confirm-tariff-quarter

## Model delta
| Morphism | Signature | Partiality | Semantics |
| --- | --- | --- | --- |
| `observe?` (Senoko, changed) | `RetailerPage → TariffObservation` | Partial | value from "prevailing SP tariff of X¢/kWh"; `tariff_quarter` from "Qn YYYY SP Tariff of Y¢/kWh" only when Y = X. If the prevailing figure is absent, Y is the value and the label is kept. Undefined when neither sentence matches |
| `tariffNotice` (Site, new) | `RegulatedTariff? × ModelTariff → Html` | Partial | empty when the quote is labelled and `cents_incl_gst == current_incl_gst`; a warning badge when the quote is unlabelled; a different warning when the two values differ. Empty when either side is missing |

## §3 consolidation
No new object. `TariffObservation` already has an optional `tariff_quarter`. This only makes a second
adapter populate it. `tariffNotice` is deduced from two existing published values, so nothing is stored.

## §4.5 laws
Unchanged. The Site reads only `plans.json` and `model.json` through `fetch_data`.

## Decisions
- Self-consistency check on Senoko's page: the banner and the "prevailing" text are edited separately
  by the retailer, so a mismatch means one of them is out of date. Better no label than a wrong one.
- The UI flag is defence in depth for when both labelled sources fail. It does not try to correct the
  model and does not guess the quarter.
