# Ingest — status

> Reconciles ARCHITECTURE.md (intent) vs IMPLEMENTATION.md (code). Updated whenever
> code changes what is done (§6.5).

## Headline
✅ Built. The quarter-gap bug (a quote for a quarter the official series lacks, lost when the
quarter turned over) is fixed: quotes are now recorded per quarter in `tariff_quotes.json`
(55 Python tests at the fix, 70 with `common/`). Biggest gap: live scraping from a GitHub
runner (bot challenges, robots, rate limits) is only partly verified — watch the next Actions runs.

## Completeness
| Object / morphism | State | Notes |
| --- | --- | --- |
| 5 scraping adapters + 2 curated | ✅ built | Keppel/Sembcorp need manual `verified_at` bumps |
| fallback functor | ✅ built | tested |
| `enrich_terms` + cache | ✅ built | once-per-URL rule untested |
| `consensus_current` | ✅ built | tested, incl. quarter-change and label rules |
| `TariffQuotes` (`record_quote`, `update_quotes`) | ✅ built | tested, incl. prev back-fill and the stale fallback not being recorded |
| `common/tariff.py` (shared with Analysis) | ✅ built | tested (`tests/test_common.py`) |
| OEM list check | ✅ built | tested |
| `run_datasets` | ✅ built | weekly limit untested |

## Needs work
1. Watch the first `Refresh plan data` Actions run; record which retailers fail from CI.
2. Add tests for rule 6 (fact-sheet once per URL) and rule 8 (weekly dataset refresh).

## Coherence
All §4.5 laws pass. The Law 4 advisory (`merge_history` imported by Analysis) is cleared:
both components now import it from `common/tariff.py`.

## Where to dig
- Model: ARCHITECTURE.md · Code map: IMPLEMENTATION.md
- In flight: none (fix-tariff-quarter-gap, shared-tariff-module archived 2026-10-08) · Reviews: reviews/ · Notes: general/
