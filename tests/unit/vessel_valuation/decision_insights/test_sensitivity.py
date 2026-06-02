"""
Sensitivity analysis tests.
uv run --extra dev pytest tests/unit/vessel_valuation/decision_insights/test_sensitivity.py -v
"""

from typing import TYPE_CHECKING

import pytest

from vessel_valuation.decision_insights.sensitivity import sensitivity_analysis

if TYPE_CHECKING:
    from vessel_valuation.schema import VesselInputs


def test_sensitivity_default_range_produces_11_points(base_inputs: VesselInputs) -> None:
    """Default ±$5k sweep at $1k steps yields eleven sensitivity points."""
    points = sensitivity_analysis(base_inputs)
    assert len(points) == 11


def test_sensitivity_first_and_last_points(base_inputs: VesselInputs) -> None:
    """Default sensitivity sweep endpoints match $45k and $55k per day."""
    points = sensitivity_analysis(base_inputs)
    assert points[0].revenue_per_day == pytest.approx(45_000.0)
    assert points[-1].revenue_per_day == pytest.approx(55_000.0)


def test_sensitivity_custom_range(base_inputs: VesselInputs) -> None:
    """Custom rev_min and rev_max control sweep bounds and point count."""
    points = sensitivity_analysis(base_inputs, rev_min=40_000, rev_max=60_000)
    assert len(points) == 21
    assert points[0].revenue_per_day == pytest.approx(40_000.0)
    assert points[-1].revenue_per_day == pytest.approx(60_000.0)


def test_sensitivity_irr_increases_monotonically_with_revenue(base_inputs: VesselInputs) -> None:
    """IRR rises monotonically as revenue per day increases across the sweep."""
    points = sensitivity_analysis(base_inputs)
    irrs = [p.irr for p in points if p.irr is not None]
    assert irrs == sorted(irrs), 'IRR should increase as revenue per day increases'


def test_sensitivity_all_points_have_irr_for_viable_vessel(base_inputs: VesselInputs) -> None:
    """Every sensitivity point on a viable vessel has a defined IRR."""
    points = sensitivity_analysis(base_inputs)
    assert all(p.irr is not None for p in points)


def test_sensitivity_clamps_low_bound_to_one(base_inputs: VesselInputs) -> None:
    """Negative rev_min is clamped so no sensitivity point falls below $1/day."""
    points = sensitivity_analysis(base_inputs, rev_min=-10_000, rev_max=5_000)
    assert all(p.revenue_per_day >= 1 for p in points)
