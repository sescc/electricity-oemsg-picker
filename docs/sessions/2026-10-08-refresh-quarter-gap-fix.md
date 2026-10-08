# 2026-10-08 — refresh quarter-gap fix + backlog #1–#4

## 0. Continuation brief
State: `Refresh plan data` had failed every day since 2026-10-01 (`KeyError: '2026Q3'` in
`analysis/build.py`), so Pages was frozen at 2026-09-30 data. It is fixed locally and verified end to end on a
scratch clone of origin with real data. All four backlog suggestions are done, CI actions are bumped, and three
OpenSpec changes are archived. **Nothing is committed or pushed.** The local checkout is still 6 bot commits
behind origin.
Next step (user): `git pull --ff-only`, then commit (message in the chat reply) and push, then Actions →
"Refresh plan data" → Run workflow. Watch for a green run, a bot commit that adds `data/snapshots/tariff_quotes.json`
with 2026Q3 + 2026Q4, and a Pages deploy.
Resume check: `openspec list --json` (expect no changes) and the Actions runs list:
`Invoke-RestMethod "https://api.github.com/repos/sescc/electricity-oemsg-picker/actions/runs?per_page=5" -Headers @{'User-Agent'='ep'}`.

## 1. Work completed
- Diagnosed from the public Actions API (`Fit models` step failing since the 2026-10-01 run) and reproduced in a scratchpad clone of origin.
- **fix-tariff-quarter-gap:**
  - Quotes are persisted (`record_quote`, `update_quotes` → `data/snapshots/tariff_quotes.json`) with a self-healing back-fill from the previous `plans.json`.
  - The `consensus_current` quarter-boundary rules are rewritten.
  - `extend_history` handles gaps.
  - Volatility uses adjacent quarters only.
  - `build_or_keep` degrades, writing `site/data/model_status.json`.
  - The UI marks quote-sourced points, breaks the chart at gaps, and shows a stale-model badge.
  - CI actions are on the Node-24 majors and runners are pinned to `ubuntu-24.04` (folded into this change).
- **shared-tariff-module:** `common/tariff.py` holds GST, `merge_history` and the quarter helpers. Analysis no longer imports `scraper`. A plans/model tariff-agreement test was added. Quote-sourced figures are published exactly as quoted.
- **test-pipeline-glue:** pure `build_model` and fixture tests for composition rules 1–6. `site/js/ui.js` holds the pure helpers and has node tests.
- Docs reconciled (all component + root docs, architecture map, suggestions). Two §4.5 reviews written. The `tariff-data` spec was created by archiving.

## 2. Decisions
Logged as Q1–Q13 in `CLAUDE.md` ("Refresh failure fix and backlog — 2026-10-08"). Key ones:
| Decision | Verdict | Why |
| --- | --- | --- |
| Operating principle | Site runs unattended; degrade with visible timestamps (user) | The user does not want recurring manual steps |
| Model failure | keep the last good `model.json` + `model_status.json`; supersedes R5 for model failures | 8 days of plans were lost to one model error |
| Quote persistence | real observations only; Q3 back-filled by code, not by hand | No invented numbers |
| Quarter time zone | Singapore time | Tariffs change at 00:00 SGT |
| `model_status` location | its own file | One writer per file (`status.json` belongs to Ingest) |
| `git pull` | the user does it once; Claude never pulls | Git writes are the user's job |
| Discarded | interpolating missing quarters; hand-writing the Q3 seed; a separate OpenSpec change for the CI bumps (folded into A) | — |

## 3. Tests, checks, benchmarks
| Check | Result | What it proved |
| --- | --- | --- |
| `.venv\Scripts\python.exe -m pytest -q` | 87 passed (was 28) | Ingest/Analysis/common behaviour, incl. the 1-Oct regression and the pre-fix input |
| `node --test` | 35 passed (was 20) | UI helpers, escaping, gap/status rendering |
| Old `build.py` on the new fixture | raises `KeyError '2026Q3'` | The regression test reproduces the real bug |
| Scratch clone of origin: `scraper.run plans` → `analysis.build` (no `--force`, within the 20 h limit, so no extra retailer fetches beyond the first reproduction run and one OEM-list check) | quotes {2026Q3: 34.78, 2026Q4: 31.16}; current 2026Q4 31.16; `history_gaps []`; `model_status ok` | The fix works on real data, and the back-fill heals Q3 |
| Browser on the clone's site | no console errors; banner "Q4 2026: 31.16¢"; amber quote markers on Q3/Q4 | The UI renders the new contract on real data |
| Mutation check (Sonnet agent) | removing GST scaling / bias anchoring / the 36-month threshold fails the tests | The rule tests have teeth |
| `drift-check.ps1` on a throwaway git copy | 0 dead / 269 refs | IMPLEMENTATION rows resolve |
| `openspec validate --specs --strict` | 1 passed | The archived spec is valid |

Bugs found along the way: the consensus tie at a quarter boundary picked the stale value; a 0.01 drift in the GST round trip; `simulate_tariff` would have crashed with `ValueError("model")` if ARX ever won the backtest. All three are fixed and tested.

## 4. Live handoff state
| Type | Handle / location | State | Inspect / resume | Stop / cleanup |
| --- | --- | --- | --- | --- |
| repo | working tree | uncommitted changes (see §10); local `main` 6 commits behind origin | `wsl -e bash -c 'cd /mnt/c/FMW/Code/Claude/ElectricityPicker && git status --short'` | the user pulls, commits and pushes |
| CI | GitHub Actions `Refresh plan data` | failing daily until the push | Actions tab or the API command in §0 | the next green run after the push |
| artifact | scratchpad `remote/` (clone of origin plus new code and refreshed data) | disposable | — | delete with the scratchpad |
| artifact | scratchpad `drift2/` | disposable | — | — |
| artifact | `graphify-out/graph.json` | updated (453 nodes, 1093 edges) | `graphify query "…"` | — |

No servers, ports or background jobs left running. The temporary `site-scratch-clone` entry was removed from `.claude/launch.json`.

## 5. In-flight changes (from OpenSpec)
| Change | Tasks | Status | Next ready artifact |
| --- | --- | --- | --- |
| none | — | 3 archived: `2026-10-08-fix-tariff-quarter-gap` (16/16), `2026-10-08-shared-tariff-module` (7/7), `2026-10-08-test-pipeline-glue` (8/8) | — |

## 6. Open items
| Priority | Item | Doc/code reference | Next action | Done when |
| --- | --- | --- | --- | --- |
| P0 | Fix not live | §0 | user: pull, commit, push, Run workflow | green refresh plus Pages deploy |
| P1 | checkout v7 credential handling for the bot `git push` is unverified | `.github/workflows/refresh-data.yml` | check that the first run's "Commit data" step pushes | a bot commit appears |
| P2 | If PacificLight fails while Senoko works, the quote has no quarter label, so it isn't recorded. `model.json` stays on the last recorded quarter while the banner shows the new value with no quarter, and nothing on the page flags the mismatch | `scraper/sources/tariff.py:consensus_current`, `site/js/app.js:renderFreshness` | possible: show a badge when the banner quote is unlabelled or disagrees with `model.json.tariff.current_incl_gst` | low likelihood (PacificLight scraped fine in every CI run) |
| P2 | One harmless 404 in the browser console until `model_status.json` is first published | `site/js/app.js:loadData` | none (goes away after the first run) | — |
| P3 | Curated Keppel/Sembcorp data | `data/curated/*.json` | re-verify by hand periodically | `verified_at` bumped |

## 7. Architecture / model changes
New `Dat`: `TariffQuotes`, `ModelStatus`. New `Trn`: `record_quote`, `update_quotes`, `extend_history`, `adjacent_dlog`,
`quoted_incl_gst`, `build_or_keep`, `build_model`, plus the UI helpers. Shared code root `common/`. The Law 4 advisory is cleared.
All §4.5 laws pass (`docs/analysis/reviews/review-fix-tariff-quarter-gap.md`, `docs/ingest/reviews/review-shared-tariff-module.md`).

## 8. Docs reconciled
| Doc | Change |
| --- | --- |
| `docs/{ingest,analysis,site}/{ARCHITECTURE,IMPLEMENTATION,STATUS}.md` | new morphisms, diagrams, ports, rule → test maps |
| `docs/IMPLEMENTATION.md`, `docs/STATUS.md`, `docs/architecture-map.md` | `common/`, new shared objects/ports, Law 4 cleared |
| `docs/suggestions.md` | #1–#4 done |
| `openspec/specs/tariff-data/spec.md` | created by archive; Purpose written |
| `CLAUDE.md` | Q1–Q13, 14 edge cases, test counts, conventions |
| `README.md` | test counts; unattended-operation and quote-history notes |

## 9. Drift check
`drift-check.ps1` on the throwaway copy `scratchpad/drift2` → 0 dead / 269 refs. The first attempt hung because robocopy kept retrying a locked file. Use `/R:0 /W:0` and copy only the source directories.

## 10. Files changed
Code: `common/` (new), `scraper/{run.py,schema.py,sources/tariff.py,retailers/geneco.py}`, `analysis/{build.py,models.py}`,
`site/js/{app.js,ui.js (new)}`, `site/css/app.css`, `.github/workflows/{refresh-data,pages}.yml`.
Tests (new): `tests/{fixtures_build.py,test_tariff_quotes.py,test_build_resilience.py,test_common.py,test_build_model.py}`, `tests/js/ui.test.mjs`.
Docs: as in §8 plus `docs/sessions/2026-10-08-refresh-quarter-gap-fix.md` and the `openspec/changes/archive/2026-10-08-*` folders.
`site/data/` and `data/snapshots/` were not touched locally: CI creates `tariff_quotes.json` and `model_status.json` on its first run.
