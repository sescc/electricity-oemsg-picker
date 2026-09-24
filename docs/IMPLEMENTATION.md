# System implementation map

> Whole-system functor architecture-map.md → code, deduced from the component
> IMPLEMENTATION.md files. System-level rows only.

## Components → code root
| Component | Code root | Model | Code map |
| --- | --- | --- | --- |
| Ingest | `scraper/` | [ingest/ARCHITECTURE.md](ingest/ARCHITECTURE.md) | [ingest/IMPLEMENTATION.md](ingest/IMPLEMENTATION.md) |
| Analysis | `analysis/` | [analysis/ARCHITECTURE.md](analysis/ARCHITECTURE.md) | [analysis/IMPLEMENTATION.md](analysis/IMPLEMENTATION.md) |
| Site | `site/` | [site/ARCHITECTURE.md](site/ARCHITECTURE.md) | [site/IMPLEMENTATION.md](site/IMPLEMENTATION.md) |

## Shared objects (one Dat, DataLocs in ≥2 components)
| Object | Authoritative at | Also read by | Realised at |
| --- | --- | --- | --- |
| `Plan` | `scraper/schema.py:make_plan` | Site | `site/data/plans.json` |
| `RegulatedTariff` | `scraper/sources/tariff.py:consensus_current` | Analysis, Site (via model.json) | `site/data/plans.json` |
| `DatasetsSnapshot` | `scraper/run.py:run_datasets` | Analysis | `data/snapshots/datasets.json` |
| `Model` | `analysis/build.py:main` | Site | `site/data/model.json` |
| `RetailerStatus` | `scraper/run.py:run_plans` | Site | `site/data/status.json` |

## Inter-component transmissions / ports (Trm)
| Port | carries | c_from → c_to | Realising code |
| --- | --- | --- | --- |
| `datasets_snapshot` | `DatasetsSnapshot` | Ingest → Analysis | `scraper/run.py:run_datasets` → `analysis/build.py:main` |
| `plans_json` | `Plan*`, `RegulatedTariff` | Ingest → Analysis, Site | `scraper/run.py:run_plans` → `site/js/app.js:loadData` |
| `status_json` | `RetailerStatus*` | Ingest → Site | `scraper/run.py:run_plans` → `site/js/app.js:renderStatus` |
| `model_json` | `Model` | Analysis → Site | `analysis/build.py:main` → `site/js/app.js:loadData` |
| `merge_history` (code import) | function | Ingest → Analysis | `scraper/sources/tariff.py:merge_history` |
| `git_commit_data`, `deploy` | files | runner → repo → Pages | `.github/workflows/refresh-data.yml`, `.github/workflows/pages.yml` |

## System entry points
| Entry | Trn triggered | Code |
| --- | --- | --- |
| cron `17 22 * * *` / manual dispatch | test → plans → datasets → build → commit | `.github/workflows/refresh-data.yml` |
| push to `site/**` or successful refresh | `node --test` → deploy | `.github/workflows/pages.yml` |
| CLI `python -m scraper.run plans\|datasets\|all` | `run_plans` / `run_datasets` / `build` | `scraper/run.py:main` |
| CLI `python -m analysis.build` | `build` | `analysis/build.py:main` |
| page load / form input | `compute` → render | `site/js/app.js:run` |

## Divergences (system-level)
- GST encoded as `0.09` (`scraper/schema.py:GST`) and `1.09` (`analysis/build.py:GST`) — suggestion #2.
