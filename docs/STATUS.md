# System status

> Roll-up of every <component>/STATUS.md. Detail lives in the linked file.

| Component | State | Headline gap | In flight | Detail |
| --- | --- | --- | --- | --- |
| Ingest | ✅ live | Senoko quarter label untested on a live CI run (fixture + live page checked) | — | [ingest/STATUS.md](ingest/STATUS.md) |
| Analysis | ✅ live | `build_or_keep` failure path tested but not yet exercised in CI | — | [analysis/STATUS.md](analysis/STATUS.md) |
| Site | ✅ live | — | — | [site/STATUS.md](site/STATUS.md) |

## Cross-cutting
- `Refresh plan data` failed daily 2026-10-01 → 2026-10-08 (`KeyError: '2026Q3'` in `analysis/build.py`); fixed locally by
  fix-tariff-quarter-gap. **Live since 2026-10-08:** manual run 37731675166 green (incl. the bot `git push` under
  checkout v7), bot commit `67d848b` added `tariff_quotes.json` {2026Q3 34.78, 2026Q4 31.16}, `model_status` ok, Pages
  deploy 37731832736 green and serving the new data.
- A model failure no longer halts the refresh: the last good `model.json` is kept and `model_status.json` says so (user
  requirement: the site runs unattended).
- CI actions on Node-24 majors; runners pinned to `ubuntu-24.04`.
- Keppel and Sembcorp data are curated: bump `verified_at` in `data/curated/*.json` when re-checked.
- Coherence: all §4.5 laws pass, Law 4 included (`common/` replaced the `merge_history` import). Backlog: [suggestions.md](suggestions.md) — all four items done.
