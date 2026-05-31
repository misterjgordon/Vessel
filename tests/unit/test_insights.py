"""Insights layer tests — breakeven, sensitivity, scenario analysis, and enrich."""

import dataclasses
from datetime import date

import pytest

from vessel_valuation.insights import (
    DEFAULT_SCENARIO_BUNDLES,
    breakeven_revenue,
    enrich,
    scenario_returns,
    sensitivity_analysis,
)
from vessel_valuation.model import build_schedule, calculate_npv, compute_npv_irr
from vessel_valuation.schema import ScenarioBundle, ValuationResult, VesselInputs

BASE_INPUTS = VesselInputs(
    vessel_name='Base Case',
    purchase_price=100_000_000.0,
    vessel_life=25,
    residual_value=5_000_000.0,
    lw_tonnage=12_500.0,
    revenue_per_day=50_000.0,
    offhire_rate=0.02,
    opex_per_day=10_000.0,
    drydock_capex=5_000_000.0,
    drydock_frequency=5,
    upgrades_capex=500_000.0,
    inflation_rate=0.03,
    discount_rate=0.10,
    days_of_year=365,
    teu_size=10_000,
    purchase_date=date(2025, 12, 31),
)


def test_breakeven_returns_float_for_viable_vessel() -> None:
    """Viable vessel breakeven search returns a numeric daily revenue rate."""
    result = breakeven_revenue(BASE_INPUTS)
    assert result is not None
    assert isinstance(result, float)


def test_breakeven_is_less_than_current_revenue_when_npv_positive() -> None:
    """Positive-NPV base case breakeven lies below the current revenue per day."""
    result = breakeven_revenue(BASE_INPUTS)
    assert result is not None
    assert result < BASE_INPUTS.revenue_per_day


def test_breakeven_npv_is_zero_at_result() -> None:
    """NPV at the breakeven revenue rate is approximately zero."""
    be = breakeven_revenue(BASE_INPUTS)
    assert be is not None
    tweaked = dataclasses.replace(BASE_INPUTS, revenue_per_day=be)
    schedule = build_schedule(tweaked)
    npv_at_breakeven = calculate_npv(schedule, BASE_INPUTS.discount_rate)
    assert npv_at_breakeven == pytest.approx(0.0, abs=1.0)


def test_breakeven_returns_none_for_unviable_vessel() -> None:
    """Unviable purchase price yields no breakeven revenue within the search band."""
    doomed = dataclasses.replace(BASE_INPUTS, purchase_price=100_000_000_000.0)
    result = breakeven_revenue(doomed)
    assert result is None


def test_sensitivity_default_range_produces_11_points() -> None:
    """Default ±$5k sweep at $1k steps yields eleven sensitivity points."""
    points = sensitivity_analysis(BASE_INPUTS)
    assert len(points) == 11


def test_sensitivity_first_and_last_points() -> None:
    """Default sensitivity sweep endpoints match $45k and $55k per day."""
    points = sensitivity_analysis(BASE_INPUTS)
    assert points[0].revenue_per_day == pytest.approx(45_000.0)
    assert points[-1].revenue_per_day == pytest.approx(55_000.0)


def test_sensitivity_custom_range() -> None:
    """Custom rev_min and rev_max control sweep bounds and point count."""
    points = sensitivity_analysis(BASE_INPUTS, rev_min=40_000, rev_max=60_000)
    assert len(points) == 21
    assert points[0].revenue_per_day == pytest.approx(40_000.0)
    assert points[-1].revenue_per_day == pytest.approx(60_000.0)


def test_sensitivity_irr_increases_monotonically_with_revenue() -> None:
    """IRR rises monotonically as revenue per day increases across the sweep."""
    points = sensitivity_analysis(BASE_INPUTS)
    irrs = [p.irr for p in points if p.irr is not None]
    assert irrs == sorted(irrs), 'IRR should increase as revenue per day increases'


def test_sensitivity_all_points_have_irr_for_viable_vessel() -> None:
    """Every sensitivity point on a viable vessel has a defined IRR."""
    points = sensitivity_analysis(BASE_INPUTS)
    assert all(p.irr is not None for p in points)


def test_sensitivity_clamps_low_bound_to_one() -> None:
    """Negative rev_min is clamped so no sensitivity point falls below $1/day."""
    points = sensitivity_analysis(BASE_INPUTS, rev_min=-10_000, rev_max=5_000)
    assert all(p.revenue_per_day >= 1 for p in points)


def test_scenario_returns_three_default_bundles() -> None:
    """Default scenario run returns Best, Base, and Worst results."""
    results = scenario_returns(BASE_INPUTS)
    assert set(results.keys()) == {'Best', 'Base', 'Worst'}


def test_scenario_base_npv_matches_compute_npv_irr() -> None:
    """Base scenario NPV and IRR match the base-case valuation engine output."""
    base_result = compute_npv_irr(BASE_INPUTS)
    scenario_result = scenario_returns(BASE_INPUTS)['Base']
    assert scenario_result.npv == pytest.approx(base_result.npv, rel=1e-6)
    assert scenario_result.irr == pytest.approx(base_result.irr, rel=1e-6)  # type: ignore[arg-type]


def test_scenario_best_npv_exceeds_base_npv() -> None:
    """Best-case scenario NPV exceeds the base-case NPV."""
    results = scenario_returns(BASE_INPUTS)
    assert results['Best'].npv > results['Base'].npv


def test_scenario_base_npv_exceeds_worst_npv() -> None:
    """Base-case scenario NPV exceeds the worst-case NPV."""
    results = scenario_returns(BASE_INPUTS)
    assert results['Base'].npv > results['Worst'].npv


def test_scenario_best_irr_exceeds_worst_irr() -> None:
    """Best-case IRR exceeds worst-case IRR when both are defined."""
    results = scenario_returns(BASE_INPUTS)
    assert results['Best'].irr is not None
    assert results['Worst'].irr is not None
    assert results['Best'].irr > results['Worst'].irr


def test_scenario_investment_signal_populated() -> None:
    """Each default scenario result carries a valid investment signal label."""
    results = scenario_returns(BASE_INPUTS)
    for name, res in results.items():
        assert res.investment_signal in {'INVEST', 'MARGINAL', 'DO NOT INVEST'}, (
            f'{name} has unexpected signal: {res.investment_signal}'
        )


def test_scenario_custom_bundles() -> None:
    """Caller-supplied scenario bundles replace defaults and rank by NPV."""
    custom = [
        ScenarioBundle('LowRate', inflation_rate=0.01, discount_rate=0.05),
        ScenarioBundle('HighRate', inflation_rate=0.07, discount_rate=0.15),
    ]
    results = scenario_returns(BASE_INPUTS, bundles=custom)
    assert set(results.keys()) == {'LowRate', 'HighRate'}
    assert results['LowRate'].npv > results['HighRate'].npv


def test_default_scenario_bundles_are_economically_ordered() -> None:
    """Default Best bundle uses lower rates than the Worst bundle."""
    best = next(b for b in DEFAULT_SCENARIO_BUNDLES if b.name == 'Best')
    worst = next(b for b in DEFAULT_SCENARIO_BUNDLES if b.name == 'Worst')
    assert best.discount_rate < worst.discount_rate
    assert best.inflation_rate < worst.inflation_rate


def test_enrich_returns_valuation_result() -> None:
    """Enrich returns a ValuationResult domain object."""
    result = enrich(BASE_INPUTS)
    assert isinstance(result, ValuationResult)


def test_enrich_breakeven_is_populated() -> None:
    """Enrich attaches a breakeven revenue rate to the result."""
    result = enrich(BASE_INPUTS)
    assert result.breakeven_rate is not None


def test_enrich_sensitivity_is_populated() -> None:
    """Enrich attaches the default eleven-point sensitivity sweep."""
    result = enrich(BASE_INPUTS)
    assert len(result.sensitivity) == 11


def test_enrich_scenarios_are_populated() -> None:
    """Enrich attaches Best, Base, and Worst scenario results."""
    result = enrich(BASE_INPUTS)
    assert set(result.scenarios.keys()) == {'Best', 'Base', 'Worst'}


def test_enrich_custom_revenue_range_passes_through() -> None:
    """Enrich rev_min and rev_max override the default sensitivity sweep bounds."""
    result = enrich(BASE_INPUTS, rev_min=40_000, rev_max=50_000)
    assert len(result.sensitivity) == 11
    assert result.sensitivity[0].revenue_per_day == pytest.approx(40_000.0)


def test_enrich_payback_and_signal_from_base_valuation() -> None:
    """Enrich copies payback year and investment signal from the base valuation."""
    result = enrich(BASE_INPUTS)
    assert result.payback_year is not None
    assert result.investment_signal in {'INVEST', 'MARGINAL', 'DO NOT INVEST'}
