"""
Editable scenario bundle parsing and warnings.
uv run --extra dev pytest tests/unit/vessel_valuation/decision_insights -k scenario_bundles -q
"""

import pytest

from vessel_valuation.decision_insights.scenario_analysis import DEFAULT_SCENARIO_BUNDLES
from vessel_valuation.decision_insights.scenario_bundles import resolve_scenario_bundles
from vessel_valuation.decision_insights.scenario_bundles import scenario_bundle_warnings
from vessel_valuation.decision_insights.scenario_bundles import scenario_bundles_from_table_rows
from vessel_valuation.schema import ScenarioBundle


def test_scenario_bundles_from_table_rows_empty_uses_defaults() -> None:
    """Missing table data falls back to default Best / Base / Worst bundles."""
    bundles, errors = scenario_bundles_from_table_rows(None)
    assert errors == []
    assert bundles is not None
    assert len(bundles) == len(DEFAULT_SCENARIO_BUNDLES)


def test_scenario_bundles_from_table_rows_parses_decimals() -> None:
    """Table rows coerce inflation and discount rates as decimals."""
    rows = [
        {
            'scenario': 'Best',
            'inflation_rate': 0.02,
            'discount_rate': 0.09,
        },
        {
            'scenario': 'Base',
            'inflation_rate': 0.03,
            'discount_rate': 0.10,
        },
        {
            'scenario': 'Worst',
            'inflation_rate': 0.04,
            'discount_rate': 0.11,
        },
    ]
    bundles, errors = scenario_bundles_from_table_rows(rows)  # ty: ignore[invalid-argument-type]
    assert errors == []
    assert bundles is not None
    assert bundles[0] == ScenarioBundle('Best', 0.02, 0.09)


def test_scenario_bundles_from_table_rows_rejects_invalid_rate() -> None:
    """Rates at or above 1.0 return parse errors."""
    rows = [{'scenario': 'Base', 'inflation_rate': 1.5, 'discount_rate': 0.10}]
    bundles, errors = scenario_bundles_from_table_rows(rows)  # ty: ignore[invalid-argument-type]
    assert bundles is None
    assert any('inflation' in err.lower() for err in errors)


def test_scenario_bundle_warnings_when_spread_differs() -> None:
    """Unequal real spreads across scenarios produce a Tier 2 warning."""
    bundles = [
        ScenarioBundle('Best', inflation_rate=0.01, discount_rate=0.08),
        ScenarioBundle('Base', inflation_rate=0.03, discount_rate=0.10),
        ScenarioBundle('Worst', inflation_rate=0.05, discount_rate=0.20),
    ]
    warnings = scenario_bundle_warnings(bundles)
    assert any('differs across scenarios' in w for w in warnings)


def test_resolve_scenario_bundles_raises_on_invalid_rows() -> None:
    """resolve_scenario_bundles surfaces parse failures as ValueError."""
    with pytest.raises(ValueError, match='discount rate'):
        resolve_scenario_bundles(
            [{'scenario': 'Base', 'inflation_rate': 0.03, 'discount_rate': 0}],
        )
