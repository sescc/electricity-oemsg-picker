# Suggestions (category-theory derived)

> Deduced from the component ARCHITECTURE.md files by FRAMEWORK rules. Not applied —
> a backlog. Each becomes an OpenSpec change if taken up. Component-level detail is
> small enough to live here only; per-component `suggestions.md` files will be split
> out if the list grows.

| # | Rule (§) | Smell found | Proposed change | Payoff |
| --- | --- | --- | --- | --- |
| 1 | §5 Ports / one source of truth | `analysis/build.py` imports `merge_history` from `scraper.sources.tariff` | Have Ingest write the merged tariff history into `datasets.json` (or move `merge_history` to a shared module) | Analysis depends only on files, not on Ingest code |
| 2 | §5 One source of truth | GST is `0.09` in `scraper/schema.py` and `1.09` in `analysis/build.py` | One constant, imported by both | A GST change can't be applied half-way |
| 3 | §5 Deduce, don't store | Current tariff exists as `plans.json.regulated_tariff` and `model.json.tariff.current_incl_gst` | Keep it, since Analysis may extend history with it; document `model.json` as the one the browser reads and assert they agree in a test | Makes the two copies' agreement checked, not assumed |
| 4 | §6.5 Status / testability | Pipeline glue in `analysis/build.py:main` and helpers in `site/js/app.js` are untested | Fixture test for `build.main`; export pure helpers from `app.js` | Covers 7 currently-untested composition rules |

No §3 consolidation smells found: `Plan` is already one object across curated, scraped,
current and SP-tariff cases (`data_method` / `id` discriminate).
