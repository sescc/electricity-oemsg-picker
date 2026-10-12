# Ingest — status

> Reconciles ARCHITECTURE.md (intent) vs IMPLEMENTATION.md (code). Updated whenever
> code changes what is done (§6.5).

## Headline
✅ Built. The quarter-gap bug (a quote for a quarter the official series lacks, lost when the
quarter turned over) is fixed: quotes are now recorded per quarter in `tariff_quotes.json`
(55 Python tests at the fix, 70 with `common/`). Senoko now also labels the tariff quarter (only when its banner
and "prevailing" sentence agree), so the quarter is still confirmed and recorded when PacificLight is down
(93 Python tests; 111 with the rule 6 and rule 8 tests). Live scraping from a GitHub runner is verified: in the scheduled runs from 2026-10-09 to 2026-10-12, every scraped retailer (Geneco, PacificLight, Senoko, Tuas) reported `ok` and Flo reported `no_residential_plans`. Senoko's quarter label agreed with PacificLight's in CI. Biggest gap: none known.

## Completeness
| Object / morphism | State | Notes |
| --- | --- | --- |
| 5 scraping adapters + 2 curated | ✅ built | Keppel/Sembcorp re-verified by hand 2026-10-12 (`verified_at`); Senoko and PacificLight both label the tariff quarter (confirmed in CI from 2026-10-09) |
| fallback functor | ✅ built | tested |
| `enrich_terms` + cache | ✅ built | tested (`tests/test_ingest_rate_rules.py`) |
| `consensus_current` | ✅ built | tested, incl. quarter-change and label rules |
| `TariffQuotes` (`record_quote`, `update_quotes`) | ✅ built | tested, incl. prev back-fill and the stale fallback not being recorded |
| `common/tariff.py` (shared with Analysis) | ✅ built | tested (`tests/test_common.py`) |
| OEM list check | ✅ built | tested |
| `run_datasets` | ✅ built | tested (`tests/test_ingest_rate_rules.py`) |

## Needs work
None open. (Done 2026-10-12: CI runs watched, with every scraped retailer `ok`; rule 6 and rule 8 tests added in change test-ingest-rate-rules.)

## Coherence
All §4.5 laws pass. The Law 4 advisory (`merge_history` imported by Analysis) is cleared:
both components now import it from `common/tariff.py`.

## Where to dig
- Model: ARCHITECTURE.md · Code map: IMPLEMENTATION.md
- In flight: none (test-ingest-rate-rules archived 2026-10-12) · Reviews: reviews/ · Notes: general/
