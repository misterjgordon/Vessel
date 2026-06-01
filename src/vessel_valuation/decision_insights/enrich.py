"""Full valuation enrichment — core DCF plus all decision-insight layers."""

from vessel_valuation.decision_insights.breakeven import breakeven_revenue
from vessel_valuation.decision_insights.scenario_analysis import scenario_returns
from vessel_valuation.decision_insights.sensitivity import sensitivity_analysis
from vessel_valuation.dcf import compute_npv_irr
from vessel_valuation.schema import ScenarioBundle, ValuationResult, VesselInputs


def enrich(
    inputs: VesselInputs,
    bundles: list[ScenarioBundle] | None = None,
    rev_min: float | None = None,
    rev_max: float | None = None,
) -> ValuationResult:
    """Compute a fully enriched valuation result for one vessel.

    Combines the core DCF result with breakeven revenue, sensitivity
    analysis, and scenario analysis in a single call. This is the
    primary entry point for the application layer.

    Parameters
    ----------
    inputs
        Fully validated vessel inputs.
    bundles
        Scenario bundles for scenario analysis. Defaults to
        ``DEFAULT_SCENARIO_BUNDLES`` (Best / Base / Worst).
    rev_min
        Lower bound for the sensitivity revenue sweep.
    rev_max
        Upper bound for the sensitivity revenue sweep.

    Returns
    -------
    ValuationResult
        All fields populated, including ``breakeven_rate``, ``sensitivity``,
        and ``scenarios``.
    """
    base = compute_npv_irr(inputs)
    return ValuationResult(
        npv=base.npv,
        irr=base.irr,
        schedule=base.schedule,
        payback_year=base.payback_year,
        investment_signal=base.investment_signal,
        breakeven_rate=breakeven_revenue(inputs),
        sensitivity=sensitivity_analysis(inputs, rev_min, rev_max),
        scenarios=scenario_returns(inputs, bundles),
    )
