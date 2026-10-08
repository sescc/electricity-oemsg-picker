# Tasks — confirm-tariff-quarter

- [x] 1.1 Senoko `parse`: `tariff_quarter` from "Qn YYYY SP Tariff of Y¢/kWh" when Y equals the prevailing figure
- [x] 1.2 Tests: fixture yields Q3 2026 / 34.78; self-contradicting page → no label; banner only → value + label; consensus with PacificLight absent and Senoko labelled → quarter set
- [x] 2.1 `site/js/ui.js:tariffNotice` + use in `renderFreshness`
- [x] 2.2 Tests: consistent → ''; unlabelled → warning; value mismatch → warning; missing inputs → ''; escaping
- [x] 3.1 IMPLEMENTATION.md rows (Ingest, Site); ARCHITECTURE/STATUS reconciled
- [x] 3.2 Drift check passes
- [x] 3.3 CLAUDE.md decision and edge-case log
