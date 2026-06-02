"""
Enrichment entry-point tests.
uv run --extra dev pytest tests/unit/vessel_valuation/decision_insights/test_enrich.py -v
"""

import pytest

from vessel_valuation.decision_insights.enrich import enrich
from vessel_valuation.schema import DcfResult
from vessel_valuation.schema import ValuationResult
from vessel_valuation.schema import VesselInputs


def test_enrich_returns_valuation_result(base_inputs: VesselInputs) -> None:
    """Enrich returns a ValuationResult that extends the core DcfResult fields."""
    result = enrich(base_inputs)
    assert isinstance(result, ValuationResult)
    assert isinstance(result, DcfResult)


def test_enrich_breakeven_is_populated(base_inputs: VesselInputs) -> None:
    """Enrich attaches a breakeven revenue rate to the result."""
    result = enrich(base_inputs)
    assert result.breakeven_rate is not None


def test_enrich_sensitivity_is_populated(base_inputs: VesselInputs) -> None:
    """Enrich attaches the default eleven-point sensitivity sweep."""
    result = enrich(base_inputs)
    assert len(result.sensitivity) == 11


def test_enrich_scenarios_are_populated(base_inputs: VesselInputs) -> None:
    """Enrich attaches Best, Base, and Worst scenario results."""
    result = enrich(base_inputs)
    assert set(result.scenarios.keys()) == {'Best', 'Base', 'Worst'}


def test_enrich_custom_revenue_range_passes_through(base_inputs: VesselInputs) -> None:
    """Enrich rev_min and rev_max override the default sensitivity sweep bounds."""
    result = enrich(base_inputs, rev_min=40_000, rev_max=50_000)
    assert len(result.sensitivity) == 11
    assert result.sensitivity[0].revenue_per_day == pytest.approx(40_000.0)


def test_enrich_payback_and_signal_from_base_valuation(base_inputs: VesselInputs) -> None:
    """Enrich copies payback year and investment signal from the base valuation."""
    result = enrich(base_inputs)
    assert result.payback_year is not None
    assert result.investment_signal in {'INVEST', 'MARGINAL', 'DO NOT INVEST'}
