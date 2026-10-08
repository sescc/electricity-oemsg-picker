# System status

> Roll-up of every <component>/STATUS.md. Detail lives in the linked file.

| Component | State | Headline gap | In flight | Detail |
| --- | --- | --- | --- | --- |
| Ingest | ✅ built | quarter-gap fix not yet run in CI | — | [ingest/STATUS.md](ingest/STATUS.md) |
| Analysis | ✅ built | `build_or_keep` degrade path not yet run in CI | — | [analysis/STATUS.md](analysis/STATUS.md) |
| Site | ✅ built | Pages deploy frozen at 2026-09-30 data until the fix is pushed | — | [site/STATUS.md](site/STATUS.md) |

## Cross-cutting
- `Refresh plan data` failed daily 2026-10-01 → 2026-10-08 (`KeyError: '2026Q3'` in `analysis/build.py`); fixed locally by
  fix-tariff-quarter-gap and verified end-to-end on a scratch clone of origin. Live once pushed and the next run is green.
- A model failure no longer halts the refresh: the last good `model.json` is kept and `model_status.json` says so (user
  requirement: the site runs unattended).
- CI actions on Node-24 majors; runners pinned to `ubuntu-24.04`.
- Keppel and Sembcorp data are curated: bump `verified_at` in `data/curated/*.json` when re-checked.
- Coherence: all §4.5 laws pass, Law 4 included (`common/` replaced the `merge_history` import). Backlog: [suggestions.md](suggestions.md) — all four items done.
