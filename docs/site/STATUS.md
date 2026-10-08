# Site — status

> Reconciles ARCHITECTURE.md (intent) vs IMPLEMENTATION.md (code). Updated whenever
> code changes what is done (§6.5).

## Headline
✅ Built and live. Pure helpers in `site/js/ui.js` (41 JS tests), including `tariffNotice`, which flags an unlabelled or inconsistent current tariff. Pages deploys after a green refresh, verified
2026-10-08 (run 37731832736).

## Completeness
| Object / morphism | State | Notes |
| --- | --- | --- |
| billing (all price types) | ✅ built | tested |
| household fit + forecast | ✅ built | tested |
| MDP solve / simulate | ✅ built | tested |
| ranking, recommendation, charts | ✅ built | verified manually in the browser |
| bills persistence | ✅ built | |
| pure UI helpers (`ui.js`) | ✅ built | tested (`tests/js/ui.test.mjs`) |
| tariff quarter / value warning (`tariffNotice`) | ✅ built | tested; wired into `renderFreshness` |
| tariff source/gap display, `model_status.json` badge | ✅ built | written against the new data contract; verified in the browser with patched data and on real data; published by CI since 2026-10-08 |

## Needs work
None open. (The former item, flagging an unlabelled or disagreeing banner quote, is closed by `site/js/ui.js:tariffNotice`.)

## Coherence
All §4.5 laws pass. The two current-tariff copies (`plans.json` for the freshness banner, `model.json` for the MDP) are checked to agree by `tests/test_common.py` (shared-tariff-module).

## Where to dig
- Model: ARCHITECTURE.md · Code map: IMPLEMENTATION.md
- In flight: none (`fix-tariff-quarter-gap`, `test-pipeline-glue` archived 2026-10-08) · Reviews: reviews/ · Notes: general/
