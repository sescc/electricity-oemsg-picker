# Analysis — status

> Reconciles ARCHITECTURE.md (intent) vs IMPLEMENTATION.md (code). Updated whenever
> code changes what is done (§6.5).

## Headline
✅ Built. The quarter-gap bug (`KeyError: '2026Q3'` when the official tariff lagged the retailer
quote) is fixed, and a build failure no longer stops the workflow (`build_or_keep`); 55 Python
tests at the fix, 87 with `common/` and the pipeline-glue tests. Every composition rule (1–8) is now
tested through the pure `analysis/build.py:build_model`. Biggest gap: none known; the live CI
inputs (real `datasets.json`) are only exercised by the daily run.

## Completeness
| Object / morphism | State | Notes |
| --- | --- | --- |
| climatology, seasonal anchor | ✅ built | tested (forecast made too hot is pulled back to climatology) |
| consumption fit | ✅ built | |
| tariff ARX + backtest | ✅ built | |
| simulation, Markov chain, fan | ✅ built | chain row-sum tested |
| model selection (`chosen`) | ✅ built | tested (argmin and each winner simulated) |
| `build_model` (pure) / `main` (I/O) | ✅ built | tested on synthetic inputs |
| history extension (`extend_history`, gaps, `adjacent_dlog`) | ✅ built | tested on synthetic roots |
| `build_or_keep` / `model_status.json` | ✅ built | tested (ok, corrupt input, no previous model) |

## Needs work
None open. (Done: test the pipeline glue on a synthetic `datasets.json`, change test-pipeline-glue.)

## Coherence
All §4.5 laws pass (single Loc, pipe-and-filter). The Law 4 advisory is cleared: Analysis
imports no Ingest code, only `common/tariff.py` (enforced by a test).

## Where to dig
- Model: ARCHITECTURE.md · Code map: IMPLEMENTATION.md
- In flight: none (fix-tariff-quarter-gap, shared-tariff-module, test-pipeline-glue archived 2026-10-08) · Reviews: reviews/ · Notes: general/
