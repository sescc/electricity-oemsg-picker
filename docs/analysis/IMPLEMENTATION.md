# Analysis — implementation map

> The functor ARCHITECTURE.md → code. Keep in sync WITH the code (§6.3).

## Objects (Dat) → code
| Object | Form / shape | Realised at | State |
| --- | --- | --- | --- |
| `TariffDataset` | `{tariff, usep, peak, cdd_anom}` by quarter | `analysis/models.py:build_tariff_dataset` | built |
| `ConsumptionFit` | `{cdd_coef, r2, n, sigma, coefs, series, last_12m_avg_kwh}` | `analysis/models.py:fit_consumption` | built |
| `TariffFit` | `{full, ar_only, f_test_exog, quarters}` | `analysis/models.py:fit_tariff` | built |
| `Backtest` | `{rmse_log{mode}, coverage_80}` | `analysis/models.py:backtest` | built |
| `MarkovChain` | `{k, levels, edges, transition, initial, start_bin}` | `analysis/models.py:markov_chain` | built |
| `model.json` | see ARCHITECTURE §8 | `analysis/build.py:main` | built |

## Morphisms (Trn / relations) → code
| Morphism | Signature | Realising code | State |
| --- | --- | --- | --- |
| `cdd_climatology` | `Weather → month → ℝ` | `analysis/models.py:cdd_climatology` | built |
| `anchor_seasonal` | `Seasonal × Clim → Forecast` | `analysis/build.py:main` (inline) | built |
| `fit_consumption` | `kWh × Weather → Fit` | `analysis/models.py:fit_consumption` | built |
| `build_tariff_dataset` | `… → TariffDataset` | `analysis/models.py:build_tariff_dataset` | built |
| `extend?` | `RegulatedTariff → TariffDataset` | `analysis/build.py:main` (inline) | built |
| `fit_tariff` | `TariffDataset → TariffFit` | `analysis/models.py:fit_tariff` | built |
| `backtest` | `TariffDataset → Backtest` | `analysis/models.py:backtest` | built |
| `chosen` | `Backtest → Mode` | `analysis/build.py:main` (`min(bt["rmse_log"], …)`) | built |
| `simulate_tariff` | `Fit × Mode → Paths` | `analysis/models.py:simulate_tariff` | built |
| `markov_chain` | `Paths → MarkovChain` | `analysis/models.py:markov_chain` | built |
| `fan` | `Paths → Fan` | `analysis/models.py:fan` | built |
| `ewma_vol` | `ℝ* → ℝ*` | `analysis/models.py:ewma_vol` | built |
| `ols` | `y × X → coefs` | `analysis/ols.py:ols` | built |
| quarter helpers | `𝕊 → 𝕊` | `analysis/models.py:next_quarter`, `analysis/models.py:quarter_of` | built |

## Composition rules → where enforced
| Rule (ARCHITECTURE §6) | Enforced at | Tested at |
| --- | --- | --- |
| 1. chosen = argmin backtest | `analysis/build.py:main` | — (untested) |
| 2. chain rows sum to 1 | `analysis/models.py:markov_chain` | `tests/test_terms_and_models.py:test_markov_chain_rows_sum_to_one_and_simulation_is_reproducible` |
| 3. reproducible simulation | `analysis/models.py:simulate_tariff` | same test |
| 4. seasonal level anchored | `analysis/build.py:main` | — (untested) |
| 5. GST-inclusive outputs | `analysis/build.py:main` | — (untested) |
| 6. < 36 months ⟹ omitted | `analysis/build.py:main` | — (untested) |
| CDD computation | `scraper/sources/weather.py:monthly_from_daily` | `tests/test_terms_and_models.py:test_cdd` |
| quarter arithmetic | `analysis/models.py:next_quarter` | `tests/test_terms_and_models.py:test_quarter_helpers` |

## Notes / divergences
- `analysis/build.py:main` holds the whole pipeline glue inline; rules 1, 4–6 are only
  exercised by running it, not by tests.
