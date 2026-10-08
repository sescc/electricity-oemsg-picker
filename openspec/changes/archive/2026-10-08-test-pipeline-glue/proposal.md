# test-pipeline-glue

## Why
Backlog suggestion #4: the composition rules realised in `analysis/build.py:main` (model
selection by backtest, seasonal anchoring, GST scaling, omission of dwelling types with < 36
months) and the helpers in `site/js/app.js` (escaping, https-only links, eligibility, contract
labels) have no tests.

## What changes
- `analysis/build.py`: pure `build_model(ds, plans, quotes) -> dict`; `main()` only does I/O.
  Fixture tests on a deterministic synthetic dataset.
- `site/js/ui.js`: pure helpers moved out of `app.js`; `tests/js/ui.test.mjs`.

## Impact
No behaviour change. Code: `analysis/build.py`, `site/js/app.js`, `site/js/ui.js`, tests.
Docs: Analysis and Site IMPLEMENTATION/STATUS; `suggestions.md` #4 closed.
