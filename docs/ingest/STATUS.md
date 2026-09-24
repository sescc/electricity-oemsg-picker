# Ingest — status

> Reconciles ARCHITECTURE.md (intent) vs IMPLEMENTATION.md (code). Updated whenever
> code changes what is done (§6.5).

## Headline
✅ Built. Biggest gap: the refresh workflow has **never run in CI** — live scraping from a
GitHub runner (bot challenges, robots, rate limits) is unverified.

## Completeness
| Object / morphism | State | Notes |
| --- | --- | --- |
| 5 scraping adapters + 2 curated | ✅ built | Keppel/Sembcorp need manual `verified_at` bumps |
| fallback functor | ✅ built | tested |
| `enrich_terms` + cache | ✅ built | once-per-URL rule untested |
| `consensus_current` | ✅ built | tested |
| OEM list check | ✅ built | tested |
| `run_datasets` | ✅ built | weekly limit untested |

## Needs work
1. Watch the first `Refresh plan data` Actions run; record which retailers fail from CI.
2. Add tests for rule 6 (fact-sheet once per URL) and rule 8 (weekly dataset refresh).

## Coherence
All §4.5 laws pass. Advisory: `merge_history` imported by Analysis (suggestion #1).

## Where to dig
- Model: ARCHITECTURE.md · Code map: IMPLEMENTATION.md
- In flight: none · Reviews: reviews/ · Notes: general/
