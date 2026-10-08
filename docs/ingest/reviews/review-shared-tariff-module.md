# Review — shared-tariff-module

> Ran after building, 2026-10-08. Checks the change against FRAMEWORK §4.5. Not a prose review.

## Coherence laws
- [x] 1. Placement honesty — `common/` holds pure functions and constants and does no I/O. Every importer is in the runner or pytest.
- [x] 2. Transmission well-typing — no new `Trm`; one code-level reach (`merge_history` import) removed.
- [x] 3. Placement totality — `common/` has no `Loc` of its own; it is placed wherever it is imported (runner, pytest).
- [x] 4. Dependency mediation — `analysis/` imports nothing from `scraper` (`test_analysis_never_imports_scraper`), and `common/` imports neither component (`test_common_is_pure_and_imports_neither_component`). The Law 4 advisory is cleared.
- [x] 5. Composition soundness — `models.next_quarter is common.shift_quarter` (`test_analysis_next_quarter_is_the_shared_implementation`), so there is one quarter arithmetic.
- [x] 6. runsAt is a relation — n/a (no new placements beyond the importers).

## Model delta actually shipped
- The helper is named `quarter_of_ts` (Singapore time), not `quarter_of_iso` (UTC) as first drafted. The proposal, design and tasks have been corrected.
- Added `analysis/models.py:quoted_incl_gst`: quote-sourced quarters publish the exact quoted GST-inclusive figure. Recorded in Analysis ARCHITECTURE §4 and IMPLEMENTATION.

## Modeling smells swept (§3)
- GST is now encoded once (`common/tariff.py:GST_FACTOR`; Geneco still prefers the retailer's own `GSTRate`).
- The two current-tariff copies are kept on purpose (banner vs MDP) and checked to agree (`test_model_current_tariff_equals_plans_quote_when_quote_is_newer`).
