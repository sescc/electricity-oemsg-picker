# Ingest — implementation map

> The functor ARCHITECTURE.md → code. Each object/morphism → the file:symbol that
> realises it. Keep in sync WITH the code (§6.3): a new morphism gets a row here in
> the same change that adds its code.

## Objects (Dat) → code
| Object | Form / shape | Realised at | State |
| --- | --- | --- | --- |
| `Plan` | dict built by the factory | `scraper/schema.py:make_plan` | built |
| `ScrapeResult` | `{plans, observations, status, message}` | `scraper/retailers/base.py:ScrapeResult` | built |
| `RetailerSnapshot` | `data/snapshots/<id>.json` | `scraper/run.py:run_plans` (writes) | built |
| `CuratedDoc` | `data/curated/{keppel,sembcorp}.json` | `scraper/retailers/curated.py:CuratedAdapter` | built |
| `Terms` | `{etf_*, auto_renewal_text, standard?}` | `scraper/terms.py:extract_terms` | built |
| `TermsCache` | `data/snapshots/terms_cache.json` | `scraper/run.py:enrich_terms` | built |
| `RegulatedTariff` | `{cents_incl_gst, quarter, agreeing_sources, observed_at, stale}` | `scraper/sources/tariff.py:consensus_current` | built |
| `TariffQuotes` | `data/snapshots/tariff_quotes.json`: `{"2026Q3": {cents_incl_gst, observed_at, sources, revised_from?}}` | `scraper/sources/tariff.py:record_quote` (pure), `scraper/run.py:run_plans` (load/save) | built |
| `RetailerStatus` | `status.json.retailers[id]` | `scraper/run.py:run_plans` | built |
| `OemListCheck` | `status.json.oem_list_check` | `scraper/run.py:check_retailer_list` | built |
| `DatasetsSnapshot` | `data/snapshots/datasets.json` | `scraper/run.py:run_datasets` | built |

## Morphisms (Trn / relations) → code
| Morphism | Signature | Realising code | State |
| --- | --- | --- | --- |
| `scrape` | `Adapter → ScrapeResult` | `scraper/retailers/base.py:Adapter` | built |
| `parse?` (Senoko) | `RetailerPage → Plan*` | `scraper/retailers/senoko.py:Senoko` | built |
| `parse?` (Geneco) | `RetailerPage → Plan*` | `scraper/retailers/geneco.py:Geneco` | built |
| `parse?` (PacificLight) | `RetailerPage → Plan*` | `scraper/retailers/pacificlight.py:PacificLight` | built |
| tier parsing | `𝕊 → (price_type, rates, daily)?` | `scraper/retailers/pacificlight.py:parse_price_text` | built |
| `parse?` (Tuas) | `RetailerPage → Plan*` | `scraper/retailers/tuas.py:Tuas` | built |
| `parse?` (Flo) | `RetailerPage → ∅ ⊕ error` | `scraper/retailers/flo.py:Flo` | built |
| `cur_plans` | `CuratedDoc → Plan*` | `scraper/retailers/curated.py:Keppel`, `scraper/retailers/curated.py:Sembcorp` | built |
| adapter registry | `→ Adapter*` | `scraper/retailers/__init__.py:ADAPTERS` | built |
| `validate_plan` | `Plan → 𝕊*` | `scraper/schema.py:validate_plan` | built |
| `with_gst` | `ℝ → ℝ` | `scraper/schema.py:with_gst` (multiplies by `common/tariff.py:GST_FACTOR`) | built |
| GST constants | `→ ℝ` | `common/tariff.py:GST_RATE`, `common/tariff.py:GST_FACTOR` (Geneco's `GSTRate` fallback: `scraper/retailers/geneco.py:Geneco`) | built |
| resolve / fallback functor | `Retailer → Plan*` | `scraper/run.py:run_plans` | built |
| `enrich_terms` | `Plan* × TermsCache → Plan*` | `scraper/run.py:enrich_terms` | built |
| `extract_terms?` | `FactSheet → Terms` | `scraper/terms.py:extract_terms` | built |
| document text | `bytes → 𝕊` | `scraper/terms.py:document_text` | built |
| `consensus_current` | `Obs* → RegulatedTariff` | `scraper/sources/tariff.py:consensus_current` (drops earlier-quarter reads, recency tie-break, label only from an agreeing plausible source, `ignored_sources`) | built |
| `record_quote` | `TariffQuotes × RegulatedTariff → TariffQuotes` | `scraper/sources/tariff.py:record_quote` | built |
| `update_quotes` | `TariffQuotes × prev × current → TariffQuotes` | `scraper/sources/tariff.py:update_quotes` (records `prev` first, then `current`) | built |
| quotes wiring | `plans.json(prev) × consensus → tariff_quotes.json` | `scraper/run.py:run_plans` (`update_quotes` before the stale fallback; only a fresh consensus is recorded) | built |
| timestamp parse | `𝕊 → datetime?` | `common/tariff.py:parse_ts` | built |
| quarter of timestamp | `𝕊 → "YYYYQn"?` | `common/tariff.py:quarter_of_ts` (Singapore time, `common/tariff.py:SGT`) | built |
| quarter label key | `"Q3 2026" → "2026Q3"?` | `common/tariff.py:quarter_key` | built |
| quarter shift | `"YYYYQn" × ℤ → "YYYYQn"` | `common/tariff.py:shift_quarter` | built |
| `diff_adapters` | `OemPage → OemListCheck` | `scraper/run.py:check_retailer_list`, `scraper/run.py:parse_oem_list` | built |
| `run_datasets` | `Sources → DatasetsSnapshot` | `scraper/run.py:run_datasets` | built |
| SES parse | `xlsx → {tariff, usep, peak, kwh}` | `scraper/sources/ses.py:parse_ses` | built |
| data.gov.sg parse | `Json → ℝ^months` | `scraper/sources/tariff.py:parse_datagov` | built |
| `merge_history` | `ℝ^m × ℝ^m → ℝ^m` | `common/tariff.py:merge_history` (shared; called by Analysis) | built |
| weather monthly | `daily → {cdd, days, mean_temp}` | `scraper/sources/weather.py:monthly_from_daily` | built |
| weather seasonal | `→ ensemble months` | `scraper/sources/weather.py:fetch_seasonal` | built |
| `polite` (nat. transf.) | `Request → Response` | `scraper/http.py:PoliteSession` | built |
| robots refusal | `URL → ⊥` | `scraper/http.py:RobotsDisallowed` | built |
| CLI entry | `argv → run` | `scraper/run.py:main` | built |

## Composition rules → where enforced
| Rule (ARCHITECTURE §6) | Enforced at | Tested at |
| --- | --- | --- |
| 1. every adapter gets a status | `scraper/run.py:run_plans` | `tests/test_run_fallback.py:test_failed_scrape_serves_last_known_plans_marked_stale` |
| 2. invalid ⟹ fallback | `scraper/run.py:run_plans` | `tests/test_run_fallback.py:test_invalid_parse_is_treated_as_failure` |
| 3. GST at parse time | `scraper/schema.py:with_gst` | `tests/test_adapters.py:test_geneco_converts_ex_gst_rates`, `tests/test_common.py:test_gst_constants` |
| 4. tariff consensus + staleness | `scraper/sources/tariff.py:consensus_current` | `tests/test_terms_and_models.py:test_tariff_consensus_flags_disagreement`, `tests/test_run_fallback.py:test_tariff_from_old_snapshot_is_dated_and_marked_stale`, `tests/test_tariff_quotes.py:test_stale_old_quarter_snapshot_does_not_outvote_fresh_read`, `tests/test_tariff_quotes.py:test_old_quarter_sources_are_dropped_even_when_they_are_the_majority`, `tests/test_tariff_quotes.py:test_tie_goes_to_most_recent_read`, `tests/test_tariff_quotes.py:test_quarter_label_comes_only_from_an_agreeing_source`, `tests/test_tariff_quotes.py:test_quarter_label_must_be_plausible_for_when_it_was_read`, `tests/test_tariff_quotes.py:test_quarter_boundary_is_singapore_time` |
| 5. OEM unparseable ≠ "no changes" | `scraper/run.py:check_retailer_list` | `tests/test_run_fallback.py:test_oem_list_ignores_commented_out_retailers` |
| 6. fact sheet once per URL | `scraper/run.py:enrich_terms` | — (untested; see STATUS) |
| 7. no headline rates for tiers | `scraper/retailers/pacificlight.py:parse_price_text` | `tests/test_adapters.py:test_pacificlight_uses_full_tier_structure_not_headline` |
| 8. dataset refresh ≤ weekly | `scraper/run.py:run_datasets` | — (untested) |
| 9. every labelled non-stale quote is kept in `TariffQuotes` | `scraper/sources/tariff.py:record_quote`, `scraper/sources/tariff.py:update_quotes`, `scraper/run.py:run_plans` | `tests/test_tariff_quotes.py:test_record_quote_new_quarter`, `tests/test_tariff_quotes.py:test_record_quote_same_value_keeps_original_observed_at`, `tests/test_tariff_quotes.py:test_record_quote_revision_overwrites_and_remembers_old_value`, `tests/test_tariff_quotes.py:test_record_quote_ignores_stale_unlabelled_and_empty_quotes`, `tests/test_tariff_quotes.py:test_update_quotes_records_previous_quote_before_the_current_one`, `tests/test_tariff_quotes.py:test_run_plans_backfills_previous_quote_then_records_current`, `tests/test_tariff_quotes.py:test_run_plans_does_not_record_the_stale_fallback` |
| 20 h rate limit | `scraper/run.py:run_plans` | `tests/test_run_fallback.py:test_success_replaces_snapshot_and_rate_limit_skips_next_run` |
| per-host spacing | `scraper/http.py:PoliteSession` | `tests/test_terms_and_models.py:test_rate_limiter_spaces_requests` |

## Notes / divergences
- Shared code lives in `common/tariff.py` (GST constants, `merge_history`, quarter and timestamp
  helpers), imported by Ingest and Analysis; it imports neither
  (`tests/test_common.py:test_common_is_pure_and_imports_neither_component`). The former
  cross-component `merge_history` import and the two GST encodings (suggestions #1, #2) are gone.
- Ingest-side tests of the quote record use `scraper/run.py:run_plans` with a monkeypatched clock
  (`tests/test_tariff_quotes.py:setup`), because the quarter-label check depends on "today".
