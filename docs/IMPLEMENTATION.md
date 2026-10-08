# System implementation map

> Whole-system functor architecture-map.md → code, deduced from the component
> IMPLEMENTATION.md files. System-level rows only.

## Components → code root
| Component | Code root | Model | Code map |
| --- | --- | --- | --- |
| Ingest | `scraper/` | [ingest/ARCHITECTURE.md](ingest/ARCHITECTURE.md) | [ingest/IMPLEMENTATION.md](ingest/IMPLEMENTATION.md) |
| Analysis | `analysis/` | [analysis/ARCHITECTURE.md](analysis/ARCHITECTURE.md) | [analysis/IMPLEMENTATION.md](analysis/IMPLEMENTATION.md) |
| Site | `site/` | [site/ARCHITECTURE.md](site/ARCHITECTURE.md) | [site/IMPLEMENTATION.md](site/IMPLEMENTATION.md) |

**Shared code** (not a component, no `Loc` of its own): `common/` — `common/tariff.py` holds the GST
constants, `merge_history` and the quarter/timestamp helpers. Ingest and Analysis import it; it imports
neither and does no I/O.

## Shared objects (one Dat, DataLocs in ≥2 components)
| Object | Authoritative at | Also read by | Realised at |
| --- | --- | --- | --- |
| `Plan` | `scraper/schema.py:make_plan` | Site | `site/data/plans.json` |
| `RegulatedTariff` | `scraper/sources/tariff.py:consensus_current` | Analysis, Site (via model.json) | `site/data/plans.json` |
| `DatasetsSnapshot` | `scraper/run.py:run_datasets` | Analysis | `data/snapshots/datasets.json` |
| `Model` | `analysis/build.py:main` | Site | `site/data/model.json` |
| `RetailerStatus` | `scraper/run.py:run_plans` | Site | `site/data/status.json` |
| `TariffQuotes` | `scraper/sources/tariff.py:record_quote` | Analysis | `data/snapshots/tariff_quotes.json` |
| `ModelStatus` | `analysis/build.py:build_or_keep` | Site | `site/data/model_status.json` |

## Inter-component transmissions / ports (Trm)
| Port | carries | c_from → c_to | Realising code |
| --- | --- | --- | --- |
| `datasets_snapshot` | `DatasetsSnapshot` | Ingest → Analysis | `scraper/run.py:run_datasets` → `analysis/build.py:main` |
| `plans_json` | `Plan*`, `RegulatedTariff` | Ingest → Analysis, Site | `scraper/run.py:run_plans` → `site/js/app.js:loadData` |
| `status_json` | `RetailerStatus*` | Ingest → Site | `scraper/run.py:run_plans` → `site/js/app.js:renderStatus` |
| `model_json` | `Model` | Analysis → Site | `analysis/build.py:main` → `site/js/app.js:loadData` |
| `tariff_quotes` | `TariffQuotes` | Ingest → Analysis | `scraper/run.py:run_plans` → `analysis/build.py:main` (`data/snapshots/tariff_quotes.json`) |
| `model_status_json` | `ModelStatus` | Analysis → Site | `analysis/build.py:build_or_keep` → `site/js/app.js:loadData` |
| `common/tariff.py` (shared module, imported by Ingest and Analysis) | functions, constants | Ingest, Analysis → `common/` | `common/tariff.py:merge_history`, `common/tariff.py:GST_FACTOR`, `common/tariff.py:quarter_key` |
| `git_commit_data`, `deploy` | files | runner → repo → Pages | `.github/workflows/refresh-data.yml`, `.github/workflows/pages.yml` |

## System entry points
| Entry | Trn triggered | Code |
| --- | --- | --- |
| cron `17 22 * * *` / manual dispatch | test → plans → datasets → build → commit | `.github/workflows/refresh-data.yml` |
| push to `site/**` or successful refresh | `node --test` → deploy | `.github/workflows/pages.yml` |
| CLI `python -m scraper.run plans\|datasets\|all` | `run_plans` / `run_datasets` / `build` | `scraper/run.py:main` |
| CLI `python -m analysis.build` | `build` (never fails the pipeline) | `analysis/build.py:build_or_keep` |
| page load / form input | `compute` → render | `site/js/app.js:run` |

## Divergences (system-level)
None recorded.
