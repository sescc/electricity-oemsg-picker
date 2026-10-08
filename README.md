# Electricity Plan Picker (Singapore OEM)

A static web app that answers: **which Open Electricity Market retailer and plan best fits this household?**
It combines each retailer's published plans and fact sheets, a weather-driven consumption forecast,
a regulated-tariff forecast, and a Markov Decision Process that plans contract choices over the
household's stay.

```
GitHub Actions (daily)                                    GitHub Pages (static)
┌──────────────────────────────────────────────┐          ┌──────────────────────────────┐
│ scraper/  7 retailer adapters + fact sheets   │─ JSON ─▶ │ site/  questions → billing    │
│           EMA SES, data.gov.sg, Open-Meteo    │          │        → MDP (backward        │
│ analysis/ consumption + tariff models, Monte  │          │        induction) → ranking,  │
│           Carlo paths → Markov chain          │          │        charts, data freshness │
└──────────────────────────────────────────────┘          └──────────────────────────────┘
```

## How the original requirements were interpreted

| Requirement | What was built | Why |
|---|---|---|
| Scrape every retailer on the [OEM list](https://www.openelectricitymarket.sg/residential/list-of-retailers) | One adapter per retailer; the OEM list is re-checked each run and new retailers are flagged | The official comparison tool is behind reCAPTCHA/Incapsula, so it isn't used |
| Scrape on demand / on a button | **Scheduled** daily GitHub Action (+ manual "Run workflow" by the repo owner) | GitHub Pages has no server; a browser can't scrape other sites (CORS) and can't hold a token. Chosen with the user |
| Rate limiting | Daily schedule, per-retailer 20 h minimum, ≥5 s between requests to a host, max 20 requests/host/run, fact sheets fetched once per URL, honest user agent, robots.txt respected | |
| Read all T&Cs | Fields that change the decision are extracted from each plan's **EMA-mandated Fact Sheet** (early-termination charge, including month- or dwelling-dependent schedules; deposit; auto-renewal; late payment; standard/non-standard), with source links | Free-text T&C summaries are unreliable. Fact sheets share an EMA template |
| Weather/demand → price volatility | Split in two: **weather → consumption** (cooling degree days), and **wholesale price + peak demand + weather → regulated tariff** (quarterly ARX model) | Residential plans are fixed or discount-off-tariff, so volatility reaches households only through the tariff |
| MDP: short-term savings vs long-term wear-and-tear | Interpreted (with the user) as **contract switching**: lock-in, early-termination charges and meter fees vs cheaper rates now, under tariff uncertainty | Appliance wear doesn't depend on the retailer |

## Retailers (as of 2026-09-22)

| Retailer | Method | Notes |
|---|---|---|
| Senoko Energy | scraped (HTML) | PDF fact sheets, ETF schedule by contract month |
| Geneco | scraped (JSON embedded in page) | rates published ex-GST and converted; fact sheets on Google Drive (robots-disallowed), so ETF is assumed |
| PacificLight | scraped (`/json/plan.json`) | full tiered/TOU/daily-charge structures; HTML fact sheets with ETF by dwelling type |
| Tuas Power | scraped (HTML) | behind Incapsula, may fail in CI → last-known data is shown, marked stale |
| Keppel Electric | **hand-verified** `data/curated/keppel.json` | robots.txt disallows the `/api/` the page renders from |
| Sembcorp Power | **hand-verified** `data/curated/sembcorp.json` | Cloudflare challenge; bot protection is not bypassed |
| Flo Energy | detected "no residential plans" | register-interest page only |

Update the two curated files by hand when those retailers change their plans (bump `verified_at`).

## Statistics

* **Consumption:** `ln(kWh/day) = a + b·CDD/day + trend + COVID dummy`, per dwelling type, fitted on EMA SES monthly kWh per account (2012→) with ERA5 temperatures. The next ~6 months use the Open-Meteo seasonal ensemble (level anchored to 10-year climatology), then climatology.
* **Tariff:** `Δln T_t = c + φ·Δln T_{t-1} + g·(ln T_{t-1} − mean) + β₁·Δln USEP_{t-1} + β₂·Δln demand_{t-1} + β₃·CDD-anomaly_{t-1}`.
  In sample the external inputs are significant (F-test). In an expanding-window backtest the random walk
  forecasts best one quarter ahead, so **simulation dynamics are chosen by out-of-sample error**. The page reports both.
* **Paths:** 4,000 Monte-Carlo paths with 4-quarter block bootstrap → fan chart, and a 5-level Markov chain (kept coarse: about 80 quarterly observations).
* **Your own bills (optional):** enter any of the past 12 months' kWh. The app fits `ln(kWh/day) = a + b·CDD/day` against each month's observed weather, with `b` shrunk towards the national value for the home type (Gaussian prior, sd 0.03). A few months set the usage level; a full year also estimates the household's own weather sensitivity. Bills are stored only in the browser (localStorage).
* **MDP:** monthly time steps, so contract ends, contract lengths and move-out dates are exact; the tariff level moves only at calendar quarter starts. State: (plan, months left, sign-time tariff level, current tariff level). Actions: keep/renew or switch. Solved by backward induction in the browser. Plans are ranked by expected cost plus a user-chosen weight on the 90th-percentile cost from 800 simulated paths per plan, with a robustness re-ranking under frozen future offers.

## Run locally

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows path; use .venv/bin on macOS/Linux
python -m scraper.run plans --force      # scrape retailers (polite: takes a few minutes)
python -m scraper.run datasets --force   # EMA SES, data.gov.sg tariff, Open-Meteo
python -m analysis.build                 # fit models -> site/data/model.json
python -m http.server 8765 --directory site
python -m pytest -q && node --test       # 87 Python + 35 JS tests, offline (saved fixtures)
```

## Deploy to GitHub Pages

1. Push this folder to a GitHub repository (branch `main`).
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Actions → General → Workflow permissions: **Read and write** (the data job commits JSON).
4. `refresh-data.yml` runs daily. `pages.yml` deploys after each successful refresh and on changes to `site/`.

The site is meant to run unattended. A retailer that can't be scraped falls back to its last-known plans, marked
"stale". If the models can't be refitted, the last good `model.json` is kept and the page says when it was last
fitted (`site/data/model_status.json`). Neither case stops the refresh or the deploy. The page always shows when the
data was last updated. If it looks old, open Actions → "Refresh plan data" → **Run workflow**.

The official tariff statistics lag by a quarter or more, so the tariff quoted by retailers is recorded every quarter
(`data/snapshots/tariff_quotes.json`) and fills the recent quarters. Those quarters are marked as retailer-quoted on
the chart. A quarter that was never observed is shown as a gap, never interpolated.

## Known limits

* Rebates and promo codes change often and have conditions; they're counted only if the user ticks the option.
* Hourly load profiles are typical shapes (adjustable night share), not metered data.
* Discount-off-tariff plans are assumed to apply to the whole per-kWh tariff.
* Future re-contract offers are assumed to move with the tariff. Because of this, a plan with a low exit fee is worth
  more (you can leave and re-sign if the tariff falls). The app re-ranks with frozen future offers and warns when the winner changes.
* The horizon is capped at 12 quarters; lock-in beyond 3 years is not valued for households staying longer.
* Standard vs non-standard status comes from fact sheets; plans with unknown status (e.g. Sembcorp) are excluded by the "Standard only" filter.
