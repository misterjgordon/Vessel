"""
Per-year scenario schedule tests.
uv run --extra dev pytest tests/unit/vessel_valuation/decision_insights -k scenario_schedules -q
"""

from typing import TYPE_CHECKING

from vessel_valuation.dcf import compute_npv_irr
from vessel_valuation.decision_insights.scenario_analysis import DEFAULT_SCENARIO_BUNDLES
from vessel_valuation.decision_insights.scenario_schedules import INPUTS_SCENARIO_NAME
from vessel_valuation.decision_insights.scenario_schedules import scenario_schedules

if TYPE_CHECKING:
    from vessel_valuation.schema import VesselInputs


def test_scenario_schedules_includes_inputs_and_three_bundles(
    base_inputs: VesselInputs,
) -> None:
    """Schedules are returned for Inputs plus Best, Base, and Worst."""
    schedules = scenario_schedules(base_inputs)
    assert set(schedules.keys()) == {INPUTS_SCENARIO_NAME, 'Best', 'Base', 'Worst'}


def test_inputs_schedule_matches_compute_npv_irr(base_inputs: VesselInputs) -> None:
    """Inputs scenario schedule matches the base valuation engine schedule."""
    base_schedule = compute_npv_irr(base_inputs).schedule
    assert scenario_schedules(base_inputs)[INPUTS_SCENARIO_NAME] == base_schedule


def test_base_bundle_schedule_length_matches_inputs(base_inputs: VesselInputs) -> None:
    """Each scenario schedule has the same number of years as the Inputs schedule."""
    schedules = scenario_schedules(base_inputs)
    expected_len = len(schedules[INPUTS_SCENARIO_NAME])
    for name in ('Best', 'Base', 'Worst'):
        assert len(schedules[name]) == expected_len


def test_base_bundle_revenue_matches_inputs_first_operating_year(
    base_inputs: VesselInputs,
) -> None:
    """Macro rate overrides do not change year-1 revenue from operating assumptions."""
    schedules = scenario_schedules(base_inputs)
    assert schedules['Base'][1].revenue == schedules[INPUTS_SCENARIO_NAME][1].revenue


def test_default_bundle_count_matches_constants() -> None:
    """Default bundle list contains exactly three named scenarios."""
    assert len(DEFAULT_SCENARIO_BUNDLES) == 3
