"""common/tariff.py: shared helpers, the package boundary, and agreement of the published tariff copies."""
import ast
import json
from pathlib import Path

import pytest

from analysis import models as M
from analysis.build import main
from common import tariff as C
from fixtures_build import quote, write_root
from scraper import schema
from scraper.sources import tariff as ingest_tariff

REPO = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ helpers
def test_gst_constants():
    assert C.GST_RATE == 0.09 and C.GST_FACTOR == 1.09
    assert schema.with_gst(10.0) == 10.9                       # Ingest converts with the shared factor


def test_merge_history_overrides_and_extends_sorted():
    ses = {"2026-01": 1.0, "2026-02": 2.0}
    assert C.merge_history(ses, {"2026-02": 2.5, "2025-12": 0.5}) == {"2025-12": 0.5, "2026-01": 1.0, "2026-02": 2.5}
    assert list(C.merge_history(ses, {"2025-12": 0.5})) == ["2025-12", "2026-01", "2026-02"]
    assert ses == {"2026-01": 1.0, "2026-02": 2.0}              # input untouched


def test_quarter_key_accepts_both_forms_and_rejects_the_rest():
    assert C.quarter_key("Q3 2026") == "2026Q3" and C.quarter_key(" q3 2026") is None
    assert C.quarter_key("2026Q3") == "2026Q3" and C.quarter_key("2026 Q3") == "2026Q3"
    for bad in ("Q5 2026", "Q0 2026", "2026", "", None, 3, "Q3 26"):
        assert C.quarter_key(bad) is None


def test_shift_quarter_forwards_backwards_and_across_years():
    assert C.shift_quarter("2026Q4", 1) == "2027Q1" and C.shift_quarter("2026Q4") == "2027Q1"
    assert C.shift_quarter("2026Q1", -1) == "2025Q4" and C.shift_quarter("2026Q2", -5) == "2025Q1"
    assert C.shift_quarter("2026Q3", 0) == "2026Q3" and C.shift_quarter("2026Q1", 8) == "2028Q1"


def test_analysis_next_quarter_is_the_shared_implementation():
    assert M.next_quarter is C.shift_quarter


def test_parse_ts_and_quarter_of_ts():
    assert C.parse_ts("2026-10-02T03:00:00+00:00").tzinfo is not None
    assert C.parse_ts("2026-10-02T03:00:00").utcoffset().total_seconds() == 0      # naive -> UTC
    assert C.parse_ts("") is None and C.parse_ts(None) is None and C.parse_ts("garbage") is None
    assert C.quarter_of_ts("2026-09-30T15:59:59+00:00") == "2026Q3"
    assert C.quarter_of_ts("2026-09-30T16:00:00+00:00") == "2026Q4"      # midnight 1 Oct in Singapore
    assert C.quarter_of_ts("2026-12-31T16:00:00+00:00") == "2027Q1"
    assert C.quarter_of_ts("2026-10-01T00:00:00+08:00") == "2026Q4"
    assert C.quarter_of_ts(None) is None


def test_ingest_tariff_module_does_not_redefine_the_shared_helpers():
    for name in ("quarter_key", "shift_quarter", "quarter_of_ts", "parse_ts", "merge_history"):
        fn = getattr(ingest_tariff, name, None)
        assert fn is None or fn is getattr(C, name)


# ------------------------------------------------------------------ package boundary
def imported_modules(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            out.add(("." * node.level) + (node.module or ""))
    return out


def test_analysis_never_imports_scraper():
    files = sorted((REPO / "analysis").glob("*.py"))
    assert files, "analysis/ not found"
    for f in files:
        bad = {m for m in imported_modules(f) if m == "scraper" or m.startswith("scraper.")}
        assert not bad, f"{f.name} imports {bad}: Analysis must couple to Ingest only through files and common/"


def test_common_is_pure_and_imports_neither_component():
    files = sorted((REPO / "common").glob("*.py"))
    assert {f.name for f in files} >= {"__init__.py", "tariff.py"}
    allowed = {"__future__", "datetime", "re"}
    for f in files:
        bad = imported_modules(f) - allowed
        assert not bad, f"{f.name} imports {bad}: common/ must stay pure (no scraper, analysis or I/O)"


# ------------------------------------------------------------------ the two published copies agree
@pytest.mark.parametrize("cents", [31.16, 28.04, 29.13, 34.78])
def test_model_current_tariff_equals_plans_quote_when_quote_is_newer(tmp_path, cents):
    # 28.04 and 29.13 are values where quote / 1.09 * 1.09 rounds to a different cent
    root = write_root(tmp_path, current=quote("Q4 2026", cents))
    main(root)
    plans = json.loads((root / "site" / "data" / "plans.json").read_text(encoding="utf-8"))
    model = json.loads((root / "site" / "data" / "model.json").read_text(encoding="utf-8"))
    assert model["gst_factor"] == C.GST_FACTOR
    assert model["tariff"]["current_quarter"] == "2026Q4"
    assert model["tariff"]["current_incl_gst"] == plans["regulated_tariff"]["cents_incl_gst"] == cents
    # the ex-GST series is the quote divided by the same factor
    last = model["tariff"]["history"][-1]
    assert last["source"] == "retailer_quote" and last["incl_gst"] == cents
    assert last["ex_gst"] == round(cents / C.GST_FACTOR, 2)


def test_recorded_quote_quarters_publish_the_quote_exactly(tmp_path):
    rec = {"cents_incl_gst": 28.04, "observed_at": "2026-09-30T00:00:00+00:00", "sources": ["a"]}
    root = write_root(tmp_path, quotes={"2026Q3": rec}, current=quote("Q4 2026", 29.13))
    main(root)
    rows = {h["quarter"]: h for h in json.loads((root / "site/data/model.json").read_text(encoding="utf-8"))["tariff"]["history"]}
    assert rows["2026Q3"]["incl_gst"] == 28.04 and rows["2026Q4"]["incl_gst"] == 29.13
    assert rows["2026Q2"]["source"] == "official"
    assert rows["2026Q2"]["incl_gst"] == round(rows["2026Q2"]["ex_gst"] * C.GST_FACTOR, 2)


def test_without_a_usable_quote_model_does_not_claim_to_match_plans(tmp_path):
    root = write_root(tmp_path, current=quote(None, 31.16))     # unlabelled quote: cannot be placed in a quarter
    main(root)
    model = json.loads((root / "site" / "data" / "model.json").read_text(encoding="utf-8"))
    assert model["tariff"]["current_quarter"] == "2026Q2"
    assert model["tariff"]["current_incl_gst"] == round(27.27 * C.GST_FACTOR, 2) != 31.16
