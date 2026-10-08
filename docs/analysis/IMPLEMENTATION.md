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
| `TariffQuotes` (input) | `data/snapshots/tariff_quotes.json`, read as a file (optional) | `analysis/build.py:load_json` (called in `analysis/build.py:main`) | built |
| `model.json` | see ARCHITECTURE §8; `tariff.history[].source`, `tariff.history_gaps` | `analysis/build.py:main` (writes; returns the model dict) | built |
| `ModelStatus` | `site/data/model_status.json`: `{state: "ok" or "stale", model_as_of, checked_at, error?}` | `analysis/build.py:build_or_keep` | built |

## Morphisms (Trn / relations) → code
| Morphism | Signature | Realising code | State |
| --- | --- | --- | --- |
| `cdd_climatology` | `Weather → month → ℝ` | `analysis/models.py:cdd_climatology` | built |
| `anchor_seasonal` | `Seasonal × Clim → Forecast` | `analysis/build.py:main` (inline) | built |
| `fit_consumption` | `kWh × Weather → Fit` | `analysis/models.py:fit_consumption` | built |
| `build_tariff_dataset` | `… → TariffDataset` | `analysis/models.py:build_tariff_dataset` | built |
| `extend_history` | `TariffDataset × TariffQuotes × RegulatedTariff → TariffDataset × Gaps` | `analysis/models.py:extend_history` (called in `analysis/build.py:main`) | built |
| exact quoted values | `… → {quarter: ¢ incl GST}` | `analysis/models.py:quoted_incl_gst` (published GST-inclusive figures for quote-sourced quarters are the quote itself, not quote ÷ GST × GST) | built |
| `adjacent_dlog` | `TariffDataset → (quarter, Δln)*` | `analysis/models.py:adjacent_dlog` | built |
| `build_or_keep` | `Inputs × model.json(prev) → model.json × ModelStatus` | `analysis/build.py:build_or_keep` (CLI entry `python -m analysis.build`; also `scraper/run.py:main` for `all`) | built |
| JSON read | `path → Json?` | `analysis/build.py:load_json` | built |
| GST scaling / merge | constants and merge | `common/tariff.py:GST_FACTOR`, `common/tariff.py:merge_history` (shared with Ingest; Analysis imports no Ingest code) | built |
| `fit_tariff` | `TariffDataset → TariffFit` | `analysis/models.py:fit_tariff` | built |
| `backtest` | `TariffDataset → Backtest` | `analysis/models.py:backtest` | built |
| `chosen` | `Backtest → Mode` | `analysis/build.py:main` (`min(bt["rmse_log"], …)`) | built |
| `simulate_tariff` | `Fit × Mode → Paths` | `analysis/models.py:simulate_tariff` | built |
| `markov_chain` | `Paths → MarkovChain` | `analysis/models.py:markov_chain` | built |
| `fan` | `Paths → Fan` | `analysis/models.py:fan` | built |
| `ewma_vol` | `Δln* → ℝ*` (takes one-quarter log changes; `[]` for none) | `analysis/models.py:ewma_vol` | built |
| `ols` | `y × X → coefs` | `analysis/ols.py:ols` | built |
| quarter helpers | `𝕊 → 𝕊` | `analysis/models.py:next_quarter` (the same function as `common/tariff.py:shift_quarter`), `analysis/models.py:quarter_of` | built |
| `build_model` | `DatasetsSnapshot × plans × TariffQuotes → Model` | `analysis/build.py:build_model` (pure, no file I/O; `generated_at` can be passed in) | built |
| `main(root)` | `root → model.json` | `analysis/build.py:main` (loads the three inputs, calls `build_model`, serialises with `allow_nan=False`, writes, prints) | built |
| synthetic inputs | `params → datasets.json × plans.json` | `tests/fixtures_build.py:make_datasets`, `tests/fixtures_build.py:write_root` | built |

## Composition rules → where enforced
| Rule (ARCHITECTURE §6) | Enforced at | Tested at |
| --- | --- | --- |
| 1. chosen = argmin backtest | `analysis/build.py:build_model` | `tests/test_build_model.py:test_simulation_model_is_the_argmin_of_the_backtest`, `tests/test_build_model.py:test_each_backtest_winner_is_the_mode_actually_simulated` (stubbed backtest forces each winner) |
| 2. chain rows sum to 1 | `analysis/models.py:markov_chain` | `tests/test_terms_and_models.py:test_markov_chain_rows_sum_to_one_and_simulation_is_reproducible`, `tests/test_build_model.py:test_markov_rows_and_initial_distribution_sum_to_one` (through `build_model`, after rounding) |
| 3. reproducible simulation | `analysis/models.py:simulate_tariff`, `analysis/build.py:build_model` | `tests/test_terms_and_models.py:test_markov_chain_rows_sum_to_one_and_simulation_is_reproducible`, `tests/test_build_model.py:test_same_inputs_give_an_identical_model_apart_from_generated_at`, `tests/test_build_model.py:test_different_inputs_do_change_the_model` |
| 4. seasonal level anchored | `analysis/build.py:build_model` | `tests/test_build_model.py:test_seasonal_forecast_is_anchored_to_climatology_and_keeps_its_shape` (forecast made 1 CDD/day too hot), `tests/test_build_model.py:test_no_seasonal_forecast_gives_an_empty_forecast_not_an_error` |
| 5. GST-inclusive outputs | `analysis/build.py:build_model` | `tests/test_build_model.py:test_fan_and_markov_levels_are_ex_gst_paths_times_gst_factor` (stubbed paths), `tests/test_build_model.py:test_history_and_current_tariff_are_gst_inclusive`, `tests/test_common.py:test_model_current_tariff_equals_plans_quote_when_quote_is_newer`, `tests/test_common.py:test_recorded_quote_quarters_publish_the_quote_exactly` |
| 6. < 36 months ⟹ omitted | `analysis/build.py:build_model` | `tests/test_build_model.py:test_dwelling_with_fewer_than_36_months_is_omitted_and_36_is_kept` |
| `build_model` is pure | `analysis/build.py:build_model` | `tests/test_build_model.py:test_build_model_does_no_file_io_and_leaves_its_inputs_alone`, `tests/test_build_model.py:test_main_writes_exactly_what_build_model_returns`, `tests/test_build_model.py:test_main_refuses_nan_and_leaves_no_model_file` |
| 7. no log change spans a missing quarter | `analysis/models.py:adjacent_dlog`, `analysis/models.py:extend_history` | `tests/test_build_resilience.py:test_missing_quarter_is_a_reported_gap_not_an_interpolation`, `tests/test_build_resilience.py:test_adjacent_dlog_skips_changes_across_a_gap_and_ewma_survives_it`, `tests/test_build_resilience.py:test_extend_history_precedence_sources_and_gaps` |
| 7. (regression) a quote newer than the official series builds | `analysis/build.py:main` | `tests/test_build_resilience.py:test_first_of_october_regression_recorded_q3_quote_bridges_the_gap`, `tests/test_build_resilience.py:test_exact_pre_fix_failure_input_no_longer_raises`, `tests/test_build_resilience.py:test_live_quote_overrides_a_recorded_one_for_the_same_quarter` |
| 8. a model failure never removes `model.json` | `analysis/build.py:build_or_keep` | `tests/test_build_resilience.py:test_build_or_keep_keeps_previous_model_when_inputs_are_corrupt`, `tests/test_build_resilience.py:test_build_or_keep_with_no_previous_model_still_exits_zero`, `tests/test_build_resilience.py:test_build_or_keep_keeps_previous_model_when_a_model_step_fails`, `tests/test_build_resilience.py:test_build_or_keep_success_writes_ok_status` |
| Analysis imports no Ingest code (Law 4) | `analysis/build.py`, `analysis/models.py` | `tests/test_common.py:test_analysis_never_imports_scraper` |
| CDD computation | `scraper/sources/weather.py:monthly_from_daily` | `tests/test_terms_and_models.py:test_cdd` |
| quarter arithmetic | `analysis/models.py:next_quarter` | `tests/test_terms_and_models.py:test_quarter_helpers` |

## Notes / divergences
- The pipeline glue is `analysis/build.py:build_model` (pure); `analysis/build.py:main` only does I/O.
  Whole-pipeline tests build synthetic inputs with `tests/fixtures_build.py:make_datasets`
  (change test-pipeline-glue), so every composition rule 1–8 is now tested.
- Found while testing rule 1: if the ARX model won the backtest, `analysis/models.py:simulate_tariff`
  raised `ValueError("model")` (the backtest calls that candidate `model`, the simulator `full`); fixed
  by accepting both. The published `simulation_model` string is unchanged.
- Shared with Ingest through `common/tariff.py` (`merge_history`, `GST_FACTOR`, quarter keys);
  there is no `scraper` import in `analysis/`.
