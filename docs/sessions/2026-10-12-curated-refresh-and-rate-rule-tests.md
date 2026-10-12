# 2026-10-12 — curated refresh and rate-rule tests

## 0. Continuation brief
Current state: every outstanding item from the 2026-10-08 handoff is closed. The changes are **uncommitted** in the working tree; the user commits. The local `main` is **4 bot data commits behind** `origin/main`. Those commits touch only `data/snapshots/` and `site/data/`, so `git pull --ff-only` applies cleanly over these edits.
- P1 (first scheduled runs, and Senoko's quarter label in CI) is verified. The scheduled refreshes from 2026-10-09 to 2026-10-12 and every Pages deploy after them were green. The live `plans.json` has Q4 2026 at 31.16¢ with `agreeing_sources` [pacificlight, senoko], and `model_status` is `ok`.
- P3: Keppel and Sembcorp were re-verified by hand and their prices updated (CLAUDE.md C1–C3).
- Ingest "Needs work" #2: rules 6 and 8 are tested (change `test-ingest-rate-rules`, archived; 18 tests; 111 Python tests in total).

Next step: the user pulls, commits and pushes. The curated prices reach the live site on the next refresh, or sooner with a manual "Run workflow".

Resume command/check (after the push and the next refresh):
```
Invoke-RestMethod https://sescc.github.io/electricity-oemsg-picker/data/status.json | % { $_.retailers.keppel, $_.retailers.sembcorp } | select id,verified_at,plan_count
```
Expect `verified_at` 2026-10-12, keppel with 5 plans and sembcorp with 2.

## 1. Work completed
- `data/curated/keppel.json`:
  - FIXED24 changed from 29.80 to 29.00; FIXED36 from 29.40 to 28.90; FIXED12 from 34.77 to 31.15.
  - SURESAVE DOT removed (no longer listed on the plan page), with a dated note.
  - `verified_at` set to 2026-10-12.
- `data/curated/sembcorp.json`: the 24M plan changed from 29.80 to 29.00; `verified_at` set to 2026-10-12.
- `tests/test_ingest_rate_rules.py` (new, written by the Sonnet agent and reviewed): 12 rule-6 tests for `scraper/run.py:enrich_terms` and 6 rule-8 tests for `scraper/run.py:run_datasets`. No production code changed.
- OpenSpec `test-ingest-rate-rules` was proposed, implemented and archived as `2026-10-12-test-ingest-rate-rules` (`skip_specs`: tests only).
- Docs reconciled (see §8).

## 2. Decisions
CLAUDE.md C1–C4 holds the durable record. Choices made in this session:

| Decision | Verdict | Why |
| --- | --- | --- |
| Re-verify the curated plans in the in-app browser | kept | A page view the user directed, matching how they were first hand-copied; no scraper code reads these pages |
| Remove SureSave | kept | It is absent from `verified_from`. The promotions page rendered no cards at all, so it is not evidence either way. The wording is "no longer listed", not "withdrawn" |
| Change S4 because Sembcorp loaded without a challenge | discarded | A real browser clears managed challenges silently; probing with `requests` would be testing bot protection |
| Run `scraper.run plans` locally to check the curated output | discarded | It hits retailer sites and writes bot-owned `site/data/` from a checkout that is behind. The adapter's `load()` and `validate_plan` were run offline instead |
| Fix the "fact sheet with only `standard`" gap found by the tests | deferred (recorded as an edge case) | A behaviour change outside this test-only change; rare in practice |
| A `reviews/review-test-ingest-rate-rules.md` | not written | Test-only change with no model delta, same as test-pipeline-glue |

## 3. Tests, checks, benchmarks
| Check | Result | What it proved |
| --- | --- | --- |
| `CuratedAdapter.load()` + `validate_plan` on both curated files | 7 plans, 0 errors | The edited curated data won't fail the scrape (N5) |
| `.venv\Scripts\python.exe -m pytest -q` | 111 passed | 93 existing tests plus 18 new |
| `node --test` | 41 passed | JS unaffected |
| `drift-check.ps1` on the repo | 18 dead | Only the untracked new test file, as expected |
| `drift-check.ps1` on a fully tracked scratch copy | 0 dead / 298 refs | All rows resolve once the file is tracked |
| Actions API + live `plans.json`, `status.json`, `model_status.json` | all green; every scraped retailer `ok` (Flo `no_residential_plans`) | P1 closed |

## 4. Live handoff state
| Type | Handle / location | State | Inspect / resume | Stop / cleanup |
| --- | --- | --- | --- | --- |
| branch | `main` | 4 behind `origin/main`; uncommitted edits (§10) | `wsl -e bash -c 'cd /mnt/c/FMW/Code/Claude/ElectricityPicker && git fetch -q && git status -sb'` | user: `git pull --ff-only`, then commit |
| deployment | https://sescc.github.io/electricity-oemsg-picker/ | serving the 2026-10-12T01:21Z data; curated prices still those of 2026-09-22 | §0 command | none |
| artifact | `graphify-out/` | updated (`--update` + `cluster-only`, 18 communities) | `graphify query "…"` | git-ignored |
| artifact | scratchpad `drift/` | throwaway git copy | — | delete with the scratchpad |
| browser | in-app browser tab (sembcorppower.com) | open, idle | — | close any time |

No processes, servers or ports are running.

## 5. In-flight changes (from OpenSpec)
| Change | Tasks | Status | Next ready artifact |
| --- | --- | --- | --- |
| none | — | archived today: test-ingest-rate-rules (6/6) | — |

## 6. Open items
| Priority | Item | Doc/code reference | Next action | Done when |
| --- | --- | --- | --- | --- |
| P2 | Commit this session's work and the untracked `2026-10-08-end-handoff.md` | §10 | user: pull, commit, push | pushed |
| P3 | Curated Keppel and Sembcorp plans | `data/curated/*.json` | re-verify by hand periodically | `verified_at` bumped |
| P3 | `build_or_keep` failure path not yet exercised in CI | `docs/analysis/STATUS.md` | none; it is covered by tests and will show if it happens | a real model failure degrades as designed |
| P4 | A fact sheet giving only `standard` is cached as an error | `scraper/run.py:enrich_terms`, CLAUDE.md edge cases | optional: keep `standard`-only results | if wanted |

## 7. Architecture / model changes
None. Rules 6 and 8 of `docs/ingest/ARCHITECTURE.md` are unchanged; they are now tested.

## 8. Docs reconciled
| Doc | Change |
| --- | --- |
| `docs/ingest/IMPLEMENTATION.md` | rule 6 and rule 8 rows list their tests |
| `docs/ingest/STATUS.md` | headline (CI verified, 111 tests), completeness notes, "Needs work" closed |
| `docs/STATUS.md` | Ingest headline gap; CI-verified bullet; curated re-verify date |
| `CLAUDE.md` | 111 tests; decisions C1–C4; SureSave edge-case row; 6 new edge cases; known-limits date |

## 9. Drift check
0 dead / 298 refs on a fully tracked copy. On the repo itself the only dead refs are the untracked `tests/test_ingest_rate_rules.py`, which clears once it is committed.

## 10. Files changed
- Modified: `CLAUDE.md`, `README.md` (test count), `data/curated/keppel.json`, `data/curated/sembcorp.json`, `docs/STATUS.md`, `docs/ingest/IMPLEMENTATION.md`, `docs/ingest/STATUS.md`.
- New: `tests/test_ingest_rate_rules.py`, `openspec/changes/archive/2026-10-12-test-ingest-rate-rules/`, this log.
- Still untracked from last session: `docs/sessions/2026-10-08-end-handoff.md`.
