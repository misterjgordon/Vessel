# Run: uv run --extra dev pytest tests/unit/decision_insights/test_scenario_analysis.py -v
"""Scenario analysis tests."""

import pytest

from vessel_valuation.decision_insights.scenario_analysis import (
    DEFAULT_SCENARIO_BUNDLES,
    scenario_returns,
)
from vessel_valuation.dcf import compute_npv_irr
from vessel_valuation.schema import ScenarioBundle, VesselInputs


def test_scenario_returns_three_default_bundles(base_inputs: VesselInputs) -> None:
    """Default scenario run returns Best, Base, and Worst results."""
    results = scenario_returns(base_inputs)
    assert set(results.keys()) == {'Best', 'Base', 'Worst'}


def test_scenario_base_npv_matches_compute_npv_irr(base_inputs: VesselInputs) -> None:
    """Base scenario NPV and IRR match the base-case valuation engine output."""
    base_result = compute_npv_irr(base_inputs)
    scenario_result = scenario_returns(base_inputs)['Base']
    assert scenario_result.npv == pytest.approx(base_result.npv, rel=1e-6)
    assert scenario_result.irr == pytest.approx(base_result.irr, rel=1e-6)  # type: ignore[arg-type]


def test_scenario_best_npv_exceeds_base_npv(base_inputs: VesselInputs) -> None:
    """Best-case scenario NPV exceeds the base-case NPV."""
    results = scenario_returns(base_inputs)
    assert results['Best'].npv > results['Base'].npv


def test_scenario_base_npv_exceeds_worst_npv(base_inputs: VesselInputs) -> None:
    """Base-case scenario NPV exceeds the worst-case NPV."""
    results = scenario_returns(base_inputs)
    assert results['Base'].npv > results['Worst'].npv


def test_scenario_best_irr_exceeds_worst_irr(base_inputs: VesselInputs) -> None:
    """Best-case IRR exceeds worst-case IRR when both are defined."""
    results = scenario_returns(base_inputs)
    assert results['Best'].irr is not None
    assert results['Worst'].irr is not None
    assert results['Best'].irr > results['Worst'].irr


def test_scenario_investment_signal_populated(base_inputs: VesselInputs) -> None:
    """Each default scenario result carries a valid investment signal label."""
    results = scenario_returns(base_inputs)
    for name, res in results.items():
        assert res.investment_signal in {'INVEST', 'MARGINAL', 'DO NOT INVEST'}, (
            f'{name} has unexpected signal: {res.investment_signal}'
        )


def test_scenario_custom_bundles(base_inputs: VesselInputs) -> None:
    """Caller-supplied scenario bundles replace defaults and rank by NPV."""
    custom = [
        ScenarioBundle('LowRate', inflation_rate=0.01, discount_rate=0.05),
        ScenarioBundle('HighRate', inflation_rate=0.07, discount_rate=0.15),
    ]
    results = scenario_returns(base_inputs, bundles=custom)
    assert set(results.keys()) == {'LowRate', 'HighRate'}
    assert results['LowRate'].npv > results['HighRate'].npv


def test_default_scenario_bundles_are_economically_ordered() -> None:
    """Default Best bundle uses lower rates than the Worst bundle."""
    best = next(b for b in DEFAULT_SCENARIO_BUNDLES if b.name == 'Best')
    worst = next(b for b in DEFAULT_SCENARIO_BUNDLES if b.name == 'Worst')
    assert best.discount_rate < worst.discount_rate
    assert best.inflation_rate < worst.inflation_rate
