"""
Contract tests for bundled case-study PP÷TEU benchmarks.
uv run --extra dev pytest tests/unit/vessel_valuation/test_case_study_benchmarks.py -v
"""

from vessel_valuation.case_study_benchmarks import load_case_study_pp_teu_benchmarks
from vessel_valuation.excel_reference import build_pp_teu_benchmarks_from_workbook


def test_bundled_pp_teu_benchmarks_match_case_study_workbook(case_study_xlsx) -> None:
    """Bundled PP÷TEU JSON matches medians computed from the case-study sample sheet."""
    from_workbook = build_pp_teu_benchmarks_from_workbook(case_study_xlsx)
    bundled = load_case_study_pp_teu_benchmarks()
    assert bundled == from_workbook
