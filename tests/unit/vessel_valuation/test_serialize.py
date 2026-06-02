"""Unit tests for valuation result JSON serialization."""

from datetime import date

import pytest

from vessel_valuation.schema import (
    CashflowYear,
    ScenarioResult,
    SensitivityPoint,
    ValuationResult,
)
from vessel_valuation.serialize import (
    cashflow_year_from_json,
    cashflow_year_to_json,
    scenario_result_to_json,
    scenarios_from_json,
    scenarios_to_json,
    sensitivity_point_to_json,
    sensitivity_points_from_json,
    sensitivity_points_to_json,
    valuation_summary_to_json,
)


def test_sensitivity_points_round_trip() -> None:
    """Sensitivity list JSON preserves revenue and optional IRR."""
    points = [
        SensitivityPoint(revenue_per_day=45_000.0, irr=0.08),
        SensitivityPoint(revenue_per_day=50_000.0, irr=None),
    ]
    restored = sensitivity_points_from_json(sensitivity_points_to_json(points))
    assert restored == points


def test_scenarios_round_trip() -> None:
    """Scenario dict JSON preserves NPV, IRR, and investment signal per name."""
    scenarios = {
        'Best': ScenarioResult(npv=1.0, irr=0.12, investment_signal='Buy'),
        'Worst': ScenarioResult(npv=-1.0, irr=None, investment_signal='Hold'),
    }
    restored = scenarios_from_json(scenarios_to_json(scenarios))
    assert restored == scenarios


def test_cashflow_year_round_trip() -> None:
    """Cashflow year JSON uses ISO period_end and numeric columns."""
    row = CashflowYear(
        year=1,
        period_end=date(2026, 12, 31),
        revenue=1.0,
        opex=2.0,
        drydock_capex=3.0,
        upgrades_capex=4.0,
        free_cashflow=5.0,
        net_cashflow=6.0,
        discounted_cashflow=7.0,
        cumulative_cashflow=8.0,
    )
    restored = cashflow_year_from_json(cashflow_year_to_json(row))
    assert restored == row


def test_valuation_summary_matches_nested_serializers() -> None:
    """Summary dict nests the same sensitivity and scenario wire shapes."""
    result = ValuationResult(
        npv=10.0,
        irr=0.09,
        schedule=[],
        payback_year=5,
        investment_signal='Buy',
        breakeven_rate=42_000.0,
        sensitivity=[SensitivityPoint(revenue_per_day=50_000.0, irr=0.09)],
        scenarios={
            'Base': ScenarioResult(npv=10.0, irr=0.09, investment_signal='Buy'),
        },
    )
    payload = valuation_summary_to_json(result)
    assert payload['sensitivity'] == [sensitivity_point_to_json(result.sensitivity[0])]
    assert payload['scenarios'] == {'Base': scenario_result_to_json(result.scenarios['Base'])}


def test_cashflow_year_from_json_rejects_non_iso_period_end() -> None:
    """Non-string period_end raises TypeError on deserialize."""
    data = cashflow_year_to_json(
        CashflowYear(
            year=0,
            period_end=date(2025, 12, 31),
            revenue=0.0,
            opex=0.0,
            drydock_capex=0.0,
            upgrades_capex=0.0,
            free_cashflow=0.0,
            net_cashflow=0.0,
            discounted_cashflow=0.0,
            cumulative_cashflow=0.0,
        )
    )
    data['period_end'] = 20251231
    with pytest.raises(TypeError, match='period_end'):
        cashflow_year_from_json(data)
