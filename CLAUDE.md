# CLAUDE.md

Guidance for working in this repo. See `README.md` for setup, architecture and deployment.

## Project in one paragraph

This is a coursework project built to production standards. It is a static GitHub Pages app that recommends the best
Singapore Open Electricity Market (OEM) retailer and plan for a household:
- **CI side (Python, GitHub Actions):** scrapes plans and fact sheets, fetches EMA / data.gov.sg / Open-Meteo data, fits models, and commits the resulting JSON to `site/data/`.
- **Browser side (plain ES modules, no build step):** computes bills, the usage forecast and the MDP.

## Commands

```bash
python -m pytest -q          # 28 Python tests, offline (tests/fixtures)
node --test                  # 20 JS tests (tests/js/*.test.mjs)
python -m scraper.run plans [--force] [--only id,id]
python -m scraper.run datasets [--force]
python -m analysis.build
python -m http.server 8765 --directory site   # or the "site" entry in .claude/launch.json
```

## Conventions

- **Rates:** always GST-inclusive ¢/kWh. Convert when a page is parsed, never when it's displayed (`scraper/schema.py`).
- **Adapters:** `parse()` is pure and fixture-tested; `fetch()` does the I/O. Add a fixture and a test for every new adapter.
- **Scraped strings are untrusted:** escape them with `esc()` and put URLs through `safeUrl()` in `app.js`.
- **No invented numbers:** if a value can't be read, mark it as unknown or assumed in the UI.
- **Architecture docs:** `docs/` follows supercharge (see `docs/architecture-map.md`); plan changes with `/opsx:propose`, and update `docs/<component>/IMPLEMENTATION.md` with the code.
- **Python tests:** use `.venv\Scripts\python.exe -m pytest`; WSL's system Python lacks the dependencies.
- **Windows PowerShell 5.1 mangles UTF-8:** `Get-Content`/`Set-Content` corrupted README.md once. Use the Edit/Write tools for text files.

---

# Decision log

Dates are 2026-09-22 unless stated otherwise. "User" means the decision was confirmed by the user; "Claude" means it was made during implementation and flagged at the time.

## Scope and requirements

| # | Decision | By | Rationale |
|---|---|---|---|
| D1 | MDP "long-term wear-n-tear" means **contract switching** (lock-in, exit fees, meter fees vs cheaper rates now, under tariff uncertainty), not appliance wear | User | Appliance wear doesn't depend on which retailer bills you |
| D2 | Split the weather/demand forecasting: **weather → household consumption**; **wholesale (USEP), peak demand and weather → regulated tariff** | User | Residential plans are fixed or discount-off-tariff, not spot-priced, so volatility reaches households only through the quarterly tariff |
| D3 | Retailer data is **hybrid**: automated scraping plus hand-verified snapshots; T&C fields come from fact sheets with source links | User | Full free-text T&C parsing is unreliable |
| D4 | The audience is coursework, but it must run with **production robustness** on **GitHub Pages** | User | — |
| D5 | Refresh via **scheduled GitHub Actions only** (daily cron plus manual "Run workflow"); no on-demand refresh button, no Cloudflare Worker proxy | User | Pages has no server; browsers can't scrape (CORS) or hold a token. A proxy was offered and declined |
| D6 | One stack: Python in CI for scraping and model fitting, browser JS for per-user work (bills, MDP) | Claude | Per-user inputs can't be precomputed; the FastAPI idea was dropped once Pages was chosen |

## Data sources

| # | Decision | Rationale |
|---|---|---|
| S1 | The official OEM Price Comparison Tool (compare.openelectricitymarket.sg) is **not** used | Behind Incapsula + reCAPTCHA; never bypass bot protection |
| S2 | Seven retailers from the OEM list, one adapter each: Senoko (static HTML cards), Geneco (`var genecoObj` JSON in page, rates ex-GST × `GSTRate`), PacificLight (`/json/plan.json` + fact-sheet price text), Tuas (static `div.price_box`), Flo (detect "no residential plans") | Probed live |
| S3 | **Keppel is hand-verified** (`data/curated/keppel.json`) | Its plan page renders from `/api/`, which robots.txt disallows |
| S4 | **Sembcorp is hand-verified** (`data/curated/sembcorp.json`) | Cloudflare managed challenge |
| S5 | The OEM retailer list is re-checked each run by parsing its inline JS array | Flags new or removed retailers |
| S6 | Tariff history comes from EMA SES `T5.2` (2005→) merged with data.gov.sg "Low Tension Supplies - Domestic" (overrides and extends); both **exclude GST** | Cross-checked: 31.91 × 1.09 = 34.78 |
| S7 | The current-quarter tariff (incl. GST) is the consensus of retailer pages quoting it (PacificLight, Senoko) | The historical series lags; disagreements are recorded |
| S8 | EMA SES tidy workbook sheets used: `T5.2` tariff, `T5.4` USEP, `T2.3` peak demand, `T5.3` components, `T3.5` kWh/account by dwelling (Region = Description = "Overall") | One stable URL. The data.gov.sg consumption datasets are 2009/2010 geo snapshots, not time series |
| S9 | Weather: Open-Meteo ERA5 archive (history) and the seasonal ensemble API (~6 months ahead); CDD base 24 °C | Free, no key |
| S10 | Fact sheets: Senoko and Tuas are PDFs; PacificLight's are HTML pages; Geneco's are on Google Drive | Drive's robots.txt disallows `/uc` downloads, so **Geneco's exit fee is "assumed"** |

## Scraping and rate limiting

| # | Decision |
|---|---|
| R1 | Honest user agent, including `GITHUB_REPOSITORY` in CI; robots.txt respected (a missing or bot-challenged robots.txt counts as "no rules") |
| R2 | ≥5 s between requests to the same host; max 20 requests per host per run; retries on 429/5xx with backoff |
| R3 | Each retailer is scraped at most once every **20 h** unless `--force`; datasets are refreshed at most every **7 days** |
| R4 | Each fact sheet is fetched **once per URL** (URLs are versioned) and cached in `data/snapshots/terms_cache.json`; errors are retried after 7 days; at most 25 fetches per run |
| R5 | Workflow `concurrency` prevents overlapping scrapes; Pages deploys only after a *successful* refresh |

## Normalisation (schema)

| # | Decision |
|---|---|
| N1 | Price types: `fixed`, `dot_pct`, `dot_cents`, `tou` (windows may wrap midnight; weekday/weekend/all), `block` (marginal usage tiers) |
| N2 | **Headline rates are never used for tiered plans.** PacificLight shows the lowest tier; the full structure is parsed from `factsheetPrice`. Unparseable plans are dropped and reported, never ranked on a misleading number |
| N3 | Daily charges (e.g. 55¢/day, $1.01/day) are part of every bill and of the effective ¢/kWh |
| N4 | Rebates are one-off, counted only for plans signed now and only if the user ticks the option. Geneco's larger rebate applies only to households switching from SP (`rebate_sgd_non_sp` otherwise) |
| N5 | Validation rejects rates outside 8–70 ¢/kWh (catches SGD/kWh read as cents), odd contract lengths, and malformed windows or blocks. A plan that fails validation fails the whole scrape, which then falls back to the snapshot |
| N6 | Standard vs non-standard status comes from the fact-sheet header or "Type of Price Plan". The **"Standard only" filter excludes unknown status** rather than admitting it |
| N7 | PacificLight Classic 60's "3% off + 5% prompt payment" is modelled as 8% off, with a GIRO condition shown |
| N8 | Exit fees can be flat, a **schedule by contract month** (Senoko: $545 in months 1–12, $327 in months 13–24) or **by dwelling type** (PacificLight). Unknown fees use the user's "assumed exit fee" setting and are badged "assumed" |

## Statistics

| # | Decision | Rationale |
|---|---|---|
| M1 | Consumption model per dwelling type: `ln(kWh/day) = a + b·CDD/day + trend + COVID dummy (2020-04..2021-12)`, fitted from 2012 | b ≈ 0.05–0.067 per CDD/day |
| M2 | The seasonal forecast's level is anchored to 10-year climatology; only its month-to-month shape is kept | Its bias can't be checked without hindcasts |
| M3 | Tariff ARX on quarterly Δln tariff with lagged Δln USEP, Δln demand, CDD anomaly and mean reversion. Reported honestly: exogenous inputs are **significant in sample** (F ≈ 5.1) but a **random walk wins out of sample** (RMSE 0.057 vs 0.066) | — |
| M4 | **Simulation dynamics are chosen by lowest backtest error** (currently random walk), with 4-quarter block-bootstrapped historical shocks (these carry the wholesale, demand and weather effects) | Honest model selection |
| M5 | Markov chain with **K = 5 tariff levels** (coarse on purpose) | ~80 quarterly observations can't support a finer chain |
| M6 | Historical drift is kept in the bootstrap (tariffs rose over 2005–2026) | A stated assumption |

## Decision model (MDP)

| # | Decision |
|---|---|
| P1 | State = (plan, months left, tariff level at signing, current tariff level); actions = keep/renew or switch; backward induction in the browser |
| P2 | **Monthly time steps** (changed from quarterly after the user reported that "1 month left" displayed and was modelled as 3). The tariff level changes only at calendar quarter starts |
| P3 | Future re-contract offers **scale with the tariff** (today's rate/tariff ratio). A robustness re-solve with **frozen offers** warns when the expected-cost winner changes |
| P4 | Switching costs the old plan's exit fee (by months left), a user "hassle" value, and a $43.60 smart-meter fee for peak/off-peak plans if the household has no smart meter |
| P5 | A move-out before the stay ends pays the exit fee on contract time remaining. A stay of "3 years or more" means no move-out inside the horizon; the horizon is capped at **36 months** |
| P6 | Ranking uses a risk-adjusted score = mean + λ·(P90 − mean), with λ from the risk slider; the table shows expected cost, P90 and the score |
| P7 | The user's current plan is plans[0]. Its **months left** set the initial state; its **contract length** (asked separately) is what it renews for; its exit fee is the figure the user enters |
| P8 | When the best move is "keep current", the headline says "Wait until your contract ends (end of MMM YYYY), then switch to X" |
| P9 | Annual discount rate 3% (0.97^(1/12) per month) |

## User's own bills (feature added after first delivery)

| # | Decision |
|---|---|
| B1 | Optional inputs for the past 12 complete calendar months; blank or skipped months are ignored; valid range 10–20,000 kWh |
| B2 | The household fit is `ln(kWh/day) = a + b·CDD/day` against each month's **observed** ERA5 weather (climatology if not yet available, marked `*`). b is shrunk towards the dwelling-type national value with a Gaussian prior (τ = 0.03, household noise s = 0.1). With 1 month, b equals the national value |
| B3 | When bills are entered, the fitted typical month replaces the average-kWh input (which is disabled), and the forecast uses the household's own a and b |
| B4 | Bills are kept only in the browser (localStorage key `electricity-picker.bills.v1`, wrapped in try/catch); nothing leaves the browser |

## Tooling (supercharge) — 2026-09-23

| # | Decision | By | Rationale |
|---|---|---|---|
| T1 | Adopt supercharge: `docs/` (intent), `openspec/` (in-flight work), `graphify-out/` (git-ignored graph), `docs/sessions/` (handoff logs) | User | Requested full setup |
| T2 | Three components: Ingest (`scraper/`), Analysis (`analysis/`), Site (`site/`); billing/household/mdp stay one component | Claude | Code seams; §3 consolidation check in `docs/sessions/2026-09-23-init.md` |
| T3 | OpenSpec specs cover only the external surface (published JSON, CLI, UI); internals live in `docs/*/ARCHITECTURE.md` | Claude | The JSON files are the CI↔browser contract |
| T4 | graphify runs `--code-only` | Claude | No LLM API key available |
| T5 | Drift check runs on a throwaway git copy in the scratchpad | Claude | The folder isn't a git repo, and git add/commit is the user's job |

---

# Edge cases discussed and how they are handled

| Edge case | Handling | Where / test |
|---|---|---|
| A scrape fails (network, bot challenge, 403) | Serve the last-known-good snapshot with its original `data_as_of`, status `failed`, `stale: true`; the UI shows a "last-known data" badge | `run.py`, `test_run_fallback.py` |
| A scrape "succeeds" but the layout changed (garbage values) | Validation failure counts as a scrape failure → snapshot fallback | `test_invalid_parse_is_treated_as_failure` |
| A scrape returns zero plans | Treated as a failure unless the adapter reports `no_residential_plans` | `run.py` |
| Flo lists no residential plans | Shown explicitly as "no residential plans", never silently dropped; raises if the page changes to list plans | `test_flo_*` |
| A retailer is added to or removed from the OEM list | Flagged in `status.json` and the UI | `check_retailer_list` |
| The OEM page can't be parsed | Reported as "could not be checked", **never** as "no changes" (this bug was found and fixed) | `test_oem_list_ignores_commented_out_retailers` |
| Former retailers left as `//` comments in the OEM JS (Sunseap, Diamond Electric) | Commented lines are stripped before parsing | same test |
| The tariff quote comes only from old snapshots | `observed_at` = when it was actually read; `stale` after 48 h; UI warning badge | `test_tariff_from_old_snapshot_is_dated_and_marked_stale` |
| Retailers disagree on the current tariff | Mode is used; disagreeing sources are recorded | `test_tariff_consensus_flags_disagreement` |
| Repeated manual runs hammer retailer sites | 20 h per-retailer limit, per-host spacing and cap | `test_success_replaces_snapshot_and_rate_limit_skips_next_run`, `test_rate_limiter_spaces_requests` |
| robots.txt disallows a path | Not fetched; status `blocked_by_robots` or a curated fallback (Keppel, Google Drive fact sheets) | `http.py` |
| Bot protection (Cloudflare, Incapsula, reCAPTCHA) | Never bypassed. Sembcorp is curated; Tuas may fail in CI → stale fallback | README |
| GST mixing (ex-GST tariff history vs incl-GST retail rates) | Normalised at parse time; Geneco ex-GST × 1.09 | `test_geneco_converts_ex_gst_rates` |
| Tiered plan headline shows only the cheapest tier | Full tiers parsed; unknown formats rejected | `test_pacificlight_uses_full_tier_structure_not_headline` |
| Time-of-use windows that wrap past midnight; weekday-only peaks (Keppel Weekend Saver) | `inWindow` handles wrap-around and day types | `billing.test.mjs` |
| Stacked usage tiers (Stack It Up) | Marginal block costing | `block (stacked) tariff is marginal` |
| Daily charges make a low headline rate expensive | Included in bills and effective ¢/kWh | `discount-off-tariff and daily charges` |
| SP-customers-only plans or rebates (Keppel SureSave, Geneco GENECO200) | Plan hidden / smaller rebate used unless the household is on SP | `eligible()`, `rebate_sgd_non_sp` |
| Peak/off-peak plan without a smart meter | $43.60 installation fee added | `switchCost`/`entryCost` |
| Moving out mid-contract | Exit fee charged at the horizon (can flip the winner) | `moving out before the contract ends…` |
| Exit fee depends on the month you leave | Schedule lookup by elapsed month | `ETF schedule by month and by dwelling` |
| Exit fee depends on dwelling type | Looked up by the chosen home type | same |
| Exit fee not published | User-set assumption, badged "assumed" | `etfFor` default |
| Current contract with 1 month left (reported by the user) | Monthly MDP; contract ends after exactly 1 month; UI says "1 month left", "end of Oct 2026" | `current contract with 1 month left…`, `months left shift…` |
| Current contract already ended (0 months left) | "Contract ended"; switching is free; keeping means renewing for the stated term | `contractLabel` |
| A low exit fee acting as a cheap option to re-contract (why PowerFIX 36 beat LifePower36) | Explained in the recommendation, plus the frozen-offers robustness warning | `renderRecommendation` |
| Ranking table looking self-contradictory (sorted by an unseen score) | Risk-adjusted score column made visible | `renderRanking` |
| "Later switch" share over 100% under monthly steps | Counts paths with at least one later switch, not switches | `simulate` |
| Contracts longer than the 36-month horizon (Classic 60) | Lock-in beyond the horizon isn't valued; documented as an assumption | methods / README |
| Unknown standard status (Sembcorp) under the "Standard only" filter | Excluded | `eligible()` |
| Bills with skipped or blank months, or only one month | Ignored; a single month sets the level with national b | `household.test.mjs` |
| Bill months without observed weather yet | Climatology used, marked `*` | `pastCdd` |
| localStorage unavailable (private mode, blocked) | try/catch; the app works without persistence | `initBills` |
| Page opened from disk (`file://`) | Error message asks to serve over HTTP | `main()` |
| `requestAnimationFrame` doesn't fire in hidden tabs | Recompute is scheduled with `setTimeout` only | `initForm` |
| Narrow/mobile layout overflowing horizontally | `minmax(0,1fr)` + `min-width: 0` on grid children | `app.css` |
| XSS via scraped text or URLs | `esc()` on every interpolation; only `https://` links rendered | `app.js` |

# Known limits / open items

- Git wasn't installed on the dev machine, so the GitHub workflows have **never run**. Watch the first Actions run.
- Keppel and Sembcorp need manual updates in `data/curated/*.json` (bump `verified_at`).
- Load profiles are typical shapes (adjustable night share), not metered data.
- Discount-off-tariff plans are assumed to discount the whole per-kWh tariff.
- Months are counted from the start of the analysis (the next quarter start), not from today's date.
