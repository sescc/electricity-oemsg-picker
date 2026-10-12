# Tasks — test-ingest-rate-rules

- [x] 1.1 Rule 6 tests for `enrich_terms`: once per URL; a successful entry is never re-fetched, however old; an error entry is retried only after 7 days; at most 25 fetches per run; robots-disallowed and exception results are cached as errors and not attached; image URLs skipped
- [x] 1.2 Rule 8 tests for `run_datasets`: skip when < 7 days old; `--force` overrides; refresh when ≥ 7 days or no snapshot; a failed source keeps its previous value and previous `fetched_at`, with `ok: false`
- [x] 2.1 Full suites green (`pytest`, `node --test`)
- [x] 3.1 Reconcile Ingest IMPLEMENTATION.md / STATUS.md, root STATUS.md
- [x] 3.2 Drift check passes
- [x] 3.3 Update the decision and edge-case log in CLAUDE.md
