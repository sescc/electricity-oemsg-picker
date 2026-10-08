# Site — implementation map

> The functor ARCHITECTURE.md → code. Keep in sync WITH the code (§6.3).

## Objects (Dat) → code
| Object | Form / shape | Realised at | State |
| --- | --- | --- | --- |
| `Inputs` | form state object | `site/js/app.js:readForm` | built |
| `Bill*` | `[{month, kwh}]` | `site/js/app.js:readBills` | built |
| `LoadProfile` | 24 hourly weights | `site/js/billing.js:PROFILES` | built |
| `Plan` (SP tariff) | constructor | `site/js/billing.js:SP_TARIFF_PLAN` | built |
| `Plan` (current) | constructor | `site/js/app.js:currentPlan` | built |
| `HouseholdFit` | `{a, b, n, dataWeight, typicalMonthlyKwh}` | `site/js/household.js:fitHousehold` | built |
| `UsagePath` | kWh per month | `site/js/household.js:consumptionForecast` | built |
| `Solution` | `{V, firstQ, policy}` | `site/js/mdp.js:solve` | built |
| `RankedRow` | `{p, sim, score, effRate, etf}` | `site/js/app.js:compute` | built |
| dwelling list | keys + labels | `site/js/household.js:DWELLINGS` | built |

## Morphisms (Trn / relations) → code
| Morphism | Signature | Realising code | State |
| --- | --- | --- | --- |
| `fetch_data` | CDN → Browser | `site/js/app.js:loadData` | built |
| `model_status_json` read | optional fetch; 404 or bad JSON → `null` | `site/js/app.js:loadData` (the `optional` wrapper for `model_status.json`) | built |
| `eligible` | `Plan × Inputs → 𝔹` | `site/js/ui.js:eligible` | built |
| `currentPlan` | `Inputs → Plan` | `site/js/app.js:currentPlan` | built |
| `fitHousehold?` | `Bill* → HouseholdFit` | `site/js/household.js:fitHousehold` | built |
| past CDD | `Weather × month → cdd` | `site/js/household.js:pastCdd` | built |
| `consumptionForecast` | `… → UsagePath` | `site/js/household.js:consumptionForecast` | built |
| `withNightShare` | `Profile × ℝ → Profile` | `site/js/billing.js:withNightShare` | built |
| `inWindow` | `Window × day × h → 𝔹` | `site/js/billing.js:inWindow` | built |
| `blockCost` | `Blocks × kWh → ℝ` | `site/js/billing.js:blockCost` | built |
| `energyCents` | `Plan × … → ℝ` | `site/js/billing.js:energyCents` | built |
| `monthlyBill` | `Plan × … → ℝ` | `site/js/billing.js:monthlyBill` | built |
| `effectiveRate` | `Plan × … → ℝ` | `site/js/billing.js:effectiveRate` | built |
| `scalePlan` | `Plan × ℝ → Plan` | `site/js/billing.js:scalePlan` | built |
| `etfFor` | `Plan × r × Ctx → ℝ` | `site/js/mdp.js:etfFor` | built |
| `switchCost` | `… → ℝ` | `site/js/mdp.js:switchCost` | built |
| `solve` | `… → Solution` | `site/js/mdp.js:solve` | built |
| `simulate` | `Solution × q → SimStats` | `site/js/mdp.js:simulate` | built |
| seeded RNG | `seed → () → [0,1)` | `site/js/mdp.js:mulberry32` | built |
| `policyAt` | `Solution × state → action` | `site/js/mdp.js:policyAt` | built |
| `score`, `frozen_check` | deduced | `site/js/app.js:compute` | built |
| `best` / headline | `RankedRow* → Rec` | `site/js/app.js:renderRecommendation` | built |
| ranking table | `RankedRow* → DOM` | `site/js/app.js:renderRanking` | built |
| freshness badges | `status.json × model_status? → DOM` | `site/js/app.js:renderFreshness`, `site/js/app.js:renderStatus` | built |
| `modelStatusBadge` | `ModelStatus? → HTML` (empty unless `state = stale`) | `site/js/ui.js:modelStatusBadge` | built |
| `tariffNotice` | `RegulatedTariff? × ModelTariff? → HTML` (empty when labelled and equal, or either side missing; warns on an unlabelled quote or a value mismatch) | `site/js/ui.js:tariffNotice`, used in `site/js/app.js:renderFreshness` | built |
| `historySeries` | `History × Gaps → Row*` (gap rows are null) | `site/js/ui.js:historySeries` | built |
| `gapNote` | `Gaps → HTML` (empty if none) | `site/js/ui.js:gapNote` | built |
| retailer-quote marker | legend/tooltip label | `site/js/ui.js:QUOTE_LABEL` | built |
| tariff chart | `TariffHistory × fan → chart` | `site/js/app.js:renderTariffChart` | built |
| label helpers | `Plan × Inputs → 𝕊` | `site/js/ui.js:contractLabel`, `site/js/ui.js:planLabel`, `site/js/ui.js:typeLabel`, `site/js/ui.js:hasPublishedEtf` | built |
| format helpers | `ℝ / date → 𝕊` | `site/js/ui.js:sgd`, `site/js/ui.js:cents`, `site/js/ui.js:plural`, `site/js/ui.js:fmtDate`, `site/js/ui.js:monthName`, `site/js/ui.js:daysAgo` | built |
| `bills_store` | RAM ↔ localStorage | `site/js/app.js:initBills` | built |
| `esc` / `safeUrl` | `𝕊 → 𝕊` | `site/js/ui.js:esc`, `site/js/ui.js:safeUrl` | built |
| recompute scheduling | input → `run` | `site/js/app.js:initForm` | built |

## Composition rules → where enforced
| Rule (ARCHITECTURE §6) | Enforced at | Tested at |
| --- | --- | --- |
| 1. simulation ≈ Bellman | `site/js/mdp.js:simulate` | `tests/js/mdp.test.mjs` ("simulation mean agrees with the Bellman value") |
| 2. tariff moves at quarter starts | `site/js/mdp.js:solve` | `tests/js/mdp.test.mjs` ("tariff only moves at quarter starts") |
| 3. r months left ⟹ r steps | `site/js/mdp.js:solve` | `tests/js/mdp.test.mjs` ("current contract with 1 month left…") |
| 4. rebates one-off | `site/js/mdp.js:solve` | `tests/js/mdp.test.mjs` ("rebates are one-off…") |
| 5. move-out pays ETF | `site/js/mdp.js:solve` | `tests/js/mdp.test.mjs` ("moving out before the contract ends…") |
| 6. one `rows` for all views | `site/js/app.js:compute` | — (structural) |
| 7. escaping | `site/js/ui.js:esc` | `tests/js/ui.test.mjs` ("esc escapes…", "safeUrl accepts only https") |
| 8. bills local only | `site/js/app.js:initBills` | — (untested) |
| 9. gaps are breaks, not interpolated | `site/js/ui.js:historySeries` | `tests/js/ui.test.mjs` ("historySeries: a gap inside the range becomes a null row…") |
| `eligible` rules (N6) | `site/js/ui.js:eligible` | `tests/js/ui.test.mjs` ("eligible: …") |
| labels, `gapNote`, `modelStatusBadge` | `site/js/ui.js:contractLabel` | `tests/js/ui.test.mjs` ("contractLabel…", "gapNote…", "modelStatusBadge…") |
| unconfirmed or inconsistent current tariff is flagged | `site/js/ui.js:tariffNotice` | `tests/js/ui.test.mjs` ("tariffNotice: a labelled quote that matches…", "tariffNotice: an unlabelled quote warns…", "tariffNotice: a labelled quote that differs…", "tariffNotice: differences up to 0.005…", "tariffNotice: missing inputs…", "tariffNotice: the forecast quarter is escaped") |
| TOU windows / blocks / dot | `site/js/billing.js:energyCents` | `tests/js/billing.test.mjs` |
| household shrinkage | `site/js/household.js:fitHousehold` | `tests/js/household.test.mjs` |
| ETF schedules | `site/js/mdp.js:etfFor` | `tests/js/mdp.test.mjs` ("ETF schedule by month and by dwelling") |

## Notes / divergences
- `site/js/app.js` still mixes compute (`compute`) with rendering. The pure, DOM-free helpers
  now live in `site/js/ui.js` and are unit-tested (`tests/js/ui.test.mjs`); `currentPlan`, `billsFit`
  and `badges` stay in `app.js` because they read form or module state (`DATA`).
- `model_status.json` may be absent (older deployments): the browser treats that as "no information".
  The 404 shows once in the console; it is not an error.
