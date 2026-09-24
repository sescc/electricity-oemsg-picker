# Site — status

> Reconciles ARCHITECTURE.md (intent) vs IMPLEMENTATION.md (code). Updated whenever
> code changes what is done (§6.5).

## Headline
✅ Built. Biggest gap: the Pages deploy has never run; `app.js` helpers
(`eligible`, `currentPlan`, `esc`) aren't exported, so they're untested.

## Completeness
| Object / morphism | State | Notes |
| --- | --- | --- |
| billing (all price types) | ✅ built | tested |
| household fit + forecast | ✅ built | tested |
| MDP solve / simulate | ✅ built | tested |
| ranking, recommendation, charts | ✅ built | verified manually in the browser |
| bills persistence | ✅ built | |

## Needs work
1. Watch the first Pages deploy after a successful refresh.
2. Consider extracting pure helpers from `app.js` so rules 7 (escaping) and `eligible` are testable.

## Coherence
All §4.5 laws pass. Advisory: current tariff read from `model.json`, derived from `plans.json` (suggestion #3).

## Where to dig
- Model: ARCHITECTURE.md · Code map: IMPLEMENTATION.md
- In flight: none · Reviews: reviews/ · Notes: general/
