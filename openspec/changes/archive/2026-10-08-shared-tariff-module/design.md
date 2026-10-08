# Design — shared-tariff-module

## Model delta
New shared code root `common/` (no `Loc` of its own — placed in whichever process imports it).
| Morphism / constant | Signature | Partiality | Semantics |
| --- | --- | --- | --- |
| `GST_RATE`, `GST_FACTOR` | constants | — | 0.09 and 1 + GST_RATE; the only GST encoding in Python |
| `merge_history` | `ℝ^months × ℝ^months → ℝ^months` | Total | moved unchanged from `scraper/sources/tariff.py` |
| `quarter_key` | `"Qn YYYY" → "YYYYQn"` | Partial | undefined (returns None) for anything else |
| `parse_ts` | `ISO timestamp → datetime` | Partial | None when missing or unreadable; naive input taken as UTC |
| `quarter_of_ts` | `ISO timestamp → "YYYYQn"` | Partial | calendar quarter in Singapore time (tariffs change at 00:00 SGT) |
| `shift_quarter` | `"YYYYQn" × ℤ → "YYYYQn"` | Total | `analysis/models.py:next_quarter` is this function |

Geneco keeps reading the retailer's own `GSTRate` field; only its fallback uses `GST_FACTOR`.

## §3 consolidation
No new object. `common/` is the shared home of morphisms already used by two components,
which removes a code-level port (`merge_history` import) instead of adding one.

## §4.5 laws
Law 4 advisory cleared: Ingest ↔ Analysis now couple only through files plus a neutral shared
module that imports neither. Rule: `common/` must not import `scraper`, `analysis` or I/O.
