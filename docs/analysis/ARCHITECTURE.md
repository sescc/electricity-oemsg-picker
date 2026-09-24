# Analysis — categorical model

> Model-first (FRAMEWORK §2/§4). Intended specification for this component; the
> code realises it (see IMPLEMENTATION.md). Source of record: `analysis/build.py`,
> `analysis/models.py`, `analysis/ols.py`. Decisions M1–M6, S6–S9 in the root `CLAUDE.md`.

## 1. Overview
A pipe-and-filter batch (FRAMEWORK §7.1) that fits every model that does not depend on a
particular household: weather climatology and the bias-anchored seasonal forecast, the
per-dwelling consumption regression, the tariff ARX with its out-of-sample backtest, the
bootstrap simulation of tariff paths, and the K = 5 Markov chain the browser MDP consumes.
Input: `data/snapshots/datasets.json` + `site/data/plans.json`. Output: `site/data/model.json`.

## 2. Why
The whole component is one composable chain in `Alg`; modeling it that way makes the
two honesty rules checkable: **model selection is a deduced morphism of the backtest**
(`chosen = argmin rmse_log`, M4), not a stored choice, and **the Markov chain is deduced
from simulated paths** (M5) — nothing downstream may read the ARX coefficients as if they
drove the simulation when the random walk won.

## 3. Core category
```mermaid
graph LR
    DS["DatasetsSnapshot"]
    RT["RegulatedTariff"]
    W["WeatherMonthly"]
    Clim["Climatology"]
    WF["WeatherForecast"]
    CF["ConsumptionFit"]
    TD["TariffDataset"]
    TF["TariffFit"]
    BT["Backtest"]
    Paths["TariffPaths"]
    MC["MarkovChain"]
    Fan["Fan"]
    MJ["model.json"]
    DS --> W
    W -->|"cdd_climatology"| Clim
    DS -.->|"anchor_seasonal (bias to Clim)"| WF
    Clim --> WF
    DS -->|"fit_consumption"| CF
    DS -->|"build_tariff_dataset"| TD
    RT -.->|"extend? (if newer quarter)"| TD
    TD -->|"fit_tariff"| TF
    TD -->|"backtest"| BT
    BT -.->|"chosen (deduced)"| Paths
    TF --> Paths
    Paths -->|"markov_chain"| MC
    Paths -->|"fan"| Fan
    Clim --> MJ
    WF --> MJ
    CF --> MJ
    TF --> MJ
    BT --> MJ
    MC --> MJ
    Fan --> MJ
    style DS fill:#4f8cf7,color:#fff
    style RT fill:#4f8cf7,color:#fff
    style MJ fill:#4f8cf7,color:#fff
    style BT fill:#9a9a9a,color:#fff
```

## 4. Morphism table
| Morphism | Signature | Partiality | Semantics |
| --- | --- | --- | --- |
| `cdd_climatology` | `WeatherMonthly → (month → ℝ)` | Total | 10-year mean CDD/day per calendar month, base 24 °C (S9) |
| `anchor_seasonal` | `Seasonal × Climatology → WeatherForecast` | Partial | defined only when the seasonal API returned months; keeps shape, level anchored (M2) |
| `fit_consumption` | `kWh series × Weather → ConsumptionFit` | Partial | per dwelling; skipped when < 36 months (M1) |
| `build_tariff_dataset` | `tariff × usep × peak × weather → TariffDataset` | Total | quarterly, ex-GST |
| `extend?` | `RegulatedTariff → TariffDataset` | Partial | appends the current quarter ÷ GST when newer than history |
| `fit_tariff` | `TariffDataset → TariffFit` | Total | ARX + AR-only + F-test on exogenous block (M3) |
| `backtest` | `TariffDataset → Backtest` | Total | rolling one-step RMSE per candidate mode, 80 % coverage |
| `chosen` | `Backtest → Mode` | Deduced | `argmin rmse_log` — never stored as config (M4) |
| `simulate_tariff` | `TariffFit × Mode × start → TariffPaths` | Total | 4-quarter block bootstrap of historical shocks, drift kept (M4, M6) |
| `markov_chain` | `TariffPaths × start → MarkovChain` | Total | K = 5 levels, row-stochastic transition, initial = start bin (M5) |
| `fan` | `TariffPaths → Fan` | Total | P10/P50/P90 per quarter, incl. GST |
| `ols` | `y × X → coefs, se, t, p` | Total | self-contained OLS with Student-t p-values |

## 5. Functors
`build : DatasetsSnapshot × plans.json → model.json` is the composite of §4 — a
pipeline whose last stage multiplies by `GST` so every tariff level in `model.json`
is incl. GST (convention "Rates").

## 6. Composition rules
1. `deduction: simulation_model = argmin(backtest.rmse_log)` (M4).
2. `invariant: Σ_j transition[i][j] = 1 for every row; initial is a distribution` (M5).
3. `invariant: simulation with a fixed seed is reproducible`.
4. `constraint: seasonal forecast level = climatology level (mean bias removed)` (M2).
5. `invariant: model.json tariff levels, fan and chain are GST-inclusive; history carries both`.
6. `constraint: a dwelling type with < 36 months of data is omitted, not extrapolated` ("no invented numbers").

## 7. Atoms owned (FRAMEWORK §4)
**Trn** — every row in §4, all placed in one Python process.
**Loc** — collapsed to one process (CI runner or developer machine): Dat + Alg (§7.1).
**Trm** — none internal. Inputs arrive as files in the checkout; output is committed by
Ingest's `git_commit_data` step in the same workflow job.

## 8. Bridges to other components (ports)
| Boundary morphism | Signature | Stored? | Semantics |
| --- | --- | --- | --- |
| `datasets_snapshot` | `Ingest → Analysis` | Stored | read-only input |
| `regulated_tariff` | `Ingest → Analysis` | Stored (plans.json) | read-only input |
| `merge_history` | Ingest symbol | Deduced | imported directly from `scraper.sources.tariff` (suggestion #1) |
| `model_json` | `Analysis → Site` | Stored (`site/data/model.json`) | weather, consumption, tariff history, fan, Markov chain, diagnostics |

## 9. Coherence notes
Pipe-and-filter law (§7.1) holds: each stage's `t_to` is the next stage's `t_from`.
Law 1 holds as long as Ingest ran first in the same checkout — the workflow orders the
steps; `datasets` is `continue-on-error`, so Analysis always reads the last good snapshot.
