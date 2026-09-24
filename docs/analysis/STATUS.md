# Analysis — status

> Reconciles ARCHITECTURE.md (intent) vs IMPLEMENTATION.md (code). Updated whenever
> code changes what is done (§6.5).

## Headline
✅ Built. Biggest gap: the pipeline glue in `analysis/build.py:main` (model selection,
seasonal anchoring, GST scaling, < 36-month omission) has no tests.

## Completeness
| Object / morphism | State | Notes |
| --- | --- | --- |
| climatology, seasonal anchor | ✅ built | anchor untested |
| consumption fit | ✅ built | |
| tariff ARX + backtest | ✅ built | |
| simulation, Markov chain, fan | ✅ built | chain row-sum tested |
| model selection (`chosen`) | ✅ built | untested |

## Needs work
1. Test `build.main` end-to-end on a small fixture `datasets.json` (rules 1, 4, 5, 6).

## Coherence
All §4.5 laws pass (single Loc, pipe-and-filter).

## Where to dig
- Model: ARCHITECTURE.md · Code map: IMPLEMENTATION.md
- In flight: none · Reviews: reviews/ · Notes: general/
