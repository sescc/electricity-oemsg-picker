# Tasks — fix-tariff-quarter-gap

## 1. Ingest
- [x] 1.1 `consensus_current`: drop earlier-quarter observations, recency tie-break, label from agreeing source within [q(as_of), q(as_of)+1]
- [x] 1.2 `record_quote` (pure) in `scraper/sources/tariff.py`
- [x] 1.3 `run_plans`: load/save `data/snapshots/tariff_quotes.json`; record `prev` (labelled, not stale, unrecorded) then the fresh consensus
- [x] 1.4 Tests: boundary tie, label rules, `record_quote` new/same/revised/stale, prev back-fill

## 2. Analysis
- [x] 2.1 `extend_history`: official + quotes after official end; `history_gaps`; `prev_ex` = latest quarter before `last_q`
- [x] 2.2 Volatility (`hist_sd`, EWMA) from adjacent-quarter changes only
- [x] 2.3 `history[].source`, `tariff.history_gaps` in `model.json`
- [x] 2.4 `build_or_keep`: on exception keep previous `model.json`, write `site/data/model_status.json`, exit 0
- [x] 2.5 Tests: 1-Oct regression, gap case, failure fallback

## 3. Site
- [x] 3.1 Tariff chart marks quote-sourced points; gap warning line
- [x] 3.2 "Model last fitted <date>" badge when `model_status.state == "stale"`

## 4. CI (folded in: upgrade-ci-actions, ships in the same push)
- [x] 4.0 Node-24 action majors (checkout/setup-python/setup-node v7, configure-pages v6, upload-pages-artifact v5, deploy-pages v5); `runs-on: ubuntu-24.04`; breaking changes reviewed — none apply

## 5. Reconcile
- [x] 4.1 IMPLEMENTATION.md rows (Ingest, Analysis, Site) with file:symbol
- [x] 4.2 Reconcile ARCHITECTURE.md, IMPLEMENTATION.md and STATUS.md
- [x] 4.3 Drift check passes
- [x] 4.4 CLAUDE.md decision and edge-case log
