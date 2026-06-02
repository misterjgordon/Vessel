"""Best / Base / Worst scenario NPV and IRR under alternate macro assumptions."""

import dataclasses

from vessel_valuation.dcf import build_schedule
from vessel_valuation.dcf import calculate_irr
from vessel_valuation.dcf import calculate_npv
from vessel_valuation.dcf import investment_signal
from vessel_valuation.schema import SIGNAL_BAND
from vessel_valuation.schema import ScenarioBundle
from vessel_valuation.schema import ScenarioResult
from vessel_valuation.schema import VesselInputs

# Best/Base/Worst rates are paired so that the real return (discount − inflation)
# stays constant at 2%, preventing economically inconsistent combinations (D-010).
DEFAULT_SCENARIO_BUNDLES: list[ScenarioBundle] = [
    ScenarioBundle(name='Best', inflation_rate=0.01, discount_rate=0.08),
    ScenarioBundle(name='Base', inflation_rate=0.03, discount_rate=0.10),
    ScenarioBundle(name='Worst', inflation_rate=0.05, discount_rate=0.12),
]


def scenario_returns(
    inputs: VesselInputs,
    bundles: list[ScenarioBundle] | None = None,
    signal_band: float = SIGNAL_BAND,
) -> dict[str, ScenarioResult]:
    """NPV, IRR, and investment signal for each Best/Base/Worst scenario bundle.

    Each bundle overrides the inflation and discount rates while all other
    inputs (revenue, OpEx, purchase price, etc.) remain constant. This
    isolates the sensitivity to macro-economic assumptions.

    Parameters
    ----------
    inputs
        Fully validated vessel inputs.
    bundles
        Scenario bundles to evaluate. Defaults to ``DEFAULT_SCENARIO_BUNDLES``
        (Best / Base / Worst as defined in D-010).
    """
    active_bundles = bundles if bundles is not None else DEFAULT_SCENARIO_BUNDLES
    results: dict[str, ScenarioResult] = {}

    for bundle in active_bundles:
        tweaked = dataclasses.replace(
            inputs,
            inflation_rate=bundle.inflation_rate,
            discount_rate=bundle.discount_rate,
        )
        schedule = build_schedule(tweaked)
        npv = calculate_npv(schedule, bundle.discount_rate)
        irr = calculate_irr([row.net_cashflow for row in schedule])
        results[bundle.name] = ScenarioResult(
            npv=npv,
            irr=irr,
            investment_signal=investment_signal(
                irr,
                bundle.discount_rate,
                signal_band=signal_band,
            ),
        )

    return results
