"""Per-year cashflow schedules for Inputs and Best / Base / Worst scenarios."""

import dataclasses
from typing import TYPE_CHECKING

from vessel_valuation.dcf import build_schedule
from vessel_valuation.dcf import compute_npv_irr
from vessel_valuation.decision_insights.scenario_analysis import DEFAULT_SCENARIO_BUNDLES

if TYPE_CHECKING:
    from vessel_valuation.schema import CashflowYear
    from vessel_valuation.schema import ScenarioBundle
    from vessel_valuation.schema import VesselInputs

INPUTS_SCENARIO_NAME = 'Inputs'


def scenario_schedules(
    inputs: VesselInputs,
    bundles: list[ScenarioBundle] | None = None,
) -> dict[str, list[CashflowYear]]:
    """Build annual cashflow schedules for the form inputs and each scenario bundle.

    ``Inputs`` uses the vessel's entered inflation and discount rates. Each
    named bundle overrides those rates (same logic as ``scenario_returns``).

    Parameters
    ----------
    inputs
        Fully validated vessel inputs.
    bundles
        Scenario bundles to evaluate. Defaults to ``DEFAULT_SCENARIO_BUNDLES``.

    Returns
    -------
    dict[str, list[CashflowYear]]
        Keys are ``Inputs`` plus each bundle name (e.g. Best, Base, Worst).
    """
    active_bundles = bundles if bundles is not None else DEFAULT_SCENARIO_BUNDLES
    schedules: dict[str, list[CashflowYear]] = {
        INPUTS_SCENARIO_NAME: compute_npv_irr(inputs).schedule,
    }

    for bundle in active_bundles:
        tweaked = dataclasses.replace(
            inputs,
            inflation_rate=bundle.inflation_rate,
            discount_rate=bundle.discount_rate,
        )
        schedules[bundle.name] = build_schedule(tweaked)

    return schedules
