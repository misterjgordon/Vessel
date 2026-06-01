# Run: uv run --extra dev pytest tests/unit/decision_insights/test_breakeven.py -v
"""Breakeven revenue search tests."""

import dataclasses

import pytest

from vessel_valuation.decision_insights.breakeven import breakeven_revenue
from vessel_valuation.model import build_schedule, calculate_npv
from vessel_valuation.schema import VesselInputs


def test_breakeven_returns_float_for_viable_vessel(base_inputs: VesselInputs) -> None:
    """Viable vessel breakeven search returns a numeric daily revenue rate."""
    result = breakeven_revenue(base_inputs)
    assert result is not None
    assert isinstance(result, float)


def test_breakeven_is_less_than_current_revenue_when_npv_positive(
    base_inputs: VesselInputs,
) -> None:
    """Positive-NPV base case breakeven lies below the current revenue per day."""
    result = breakeven_revenue(base_inputs)
    assert result is not None
    assert result < base_inputs.revenue_per_day


def test_breakeven_npv_is_zero_at_result(base_inputs: VesselInputs) -> None:
    """NPV at the breakeven revenue rate is approximately zero."""
    be = breakeven_revenue(base_inputs)
    assert be is not None
    tweaked = dataclasses.replace(base_inputs, revenue_per_day=be)
    schedule = build_schedule(tweaked)
    npv_at_breakeven = calculate_npv(schedule, base_inputs.discount_rate)
    assert npv_at_breakeven == pytest.approx(0.0, abs=1.0)


def test_breakeven_returns_none_for_unviable_vessel(base_inputs: VesselInputs) -> None:
    """Unviable purchase price yields no breakeven revenue within the search band."""
    doomed = dataclasses.replace(base_inputs, purchase_price=100_000_000_000.0)
    result = breakeven_revenue(doomed)
    assert result is None
