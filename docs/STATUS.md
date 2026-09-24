# System status

> Roll-up of every <component>/STATUS.md. Detail lives in the linked file.

| Component | State | Headline gap | In flight | Detail |
| --- | --- | --- | --- | --- |
| Ingest | ✅ built | CI refresh has never run | — | [ingest/STATUS.md](ingest/STATUS.md) |
| Analysis | ✅ built | `build.main` glue untested | — | [analysis/STATUS.md](analysis/STATUS.md) |
| Site | ✅ built | Pages deploy has never run; `app.js` helpers untested | — | [site/STATUS.md](site/STATUS.md) |

## Cross-cutting
- The repo has no git history on Windows (git runs only in WSL); both workflows are unverified until the first push.
- Keppel and Sembcorp data are curated: bump `verified_at` in `data/curated/*.json` when re-checked.
- Coherence: all §4.5 laws pass; Law 4 advisory (`merge_history` import). Backlog: [suggestions.md](suggestions.md).
