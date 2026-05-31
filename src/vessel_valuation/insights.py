"""Decision-support insights layer — breakeven, sensitivity, and scenario analysis.

All functions are pure engine functions: they take ``VesselInputs``, call
model primitives, and return typed result objects. No UI or DB concerns.

Typical call chain:
    result = compute_npv_irr(inputs)          # model.py — core NPV/IRR
    result = enrich(inputs)                   # insights.py — full report

``enrich`` is the single entry point for the application layer; it
combines the base valuation with all three insight layers in one call.
"""

import dataclasses

from scipy.optimize import brentq

from vessel_valuation.model import (
    build_schedule,
    calculate_irr,
    calculate_npv,
    compute_npv_irr,
    investment_signal,
)
from vessel_valuation.schema import (
    ScenarioBundle,
    ScenarioResult,
    SensitivityPoint,
    ValuationResult,
    VesselInputs,
)

# ---------------------------------------------------------------------------
# Default scenario bundles (D-010)
# Best/Base/Worst rates are paired so that the real return (discount − inflation)
# stays constant at 2%, preventing economically inconsistent combinations.
# ---------------------------------------------------------------------------

DEFAULT_SCENARIO_BUNDLES: list[ScenarioBundle] = [
    ScenarioBundle(name='Best', inflation_rate=0.01, discount_rate=0.08),
    ScenarioBundle(name='Base', inflation_rate=0.03, discount_rate=0.10),
    ScenarioBundle(name='Worst', inflation_rate=0.05, discount_rate=0.12),
]

_BREAKEVEN_HI: float = 1_000_000.0
_SENSITIVITY_STEP: int = 1_000
_SENSITIVITY_DEFAULT_BAND: float = 5_000.0


# ---------------------------------------------------------------------------
# Breakeven revenue
# ---------------------------------------------------------------------------


def breakeven_revenue(inputs: VesselInputs) -> float | None:
    """Revenue per day (gross, pre-offhire) at which NPV = 0.

    Uses Brent's method on the range [1, 1,000,000]. Returns ``None``
    when no sign change is found — i.e. the vessel never breaks even
    or is profitable even with negligible revenue.

    Parameters
    ----------
    inputs
        Fully validated vessel inputs.
    """

    def _npv_at_rev(rev: float) -> float:
        tweaked = dataclasses.replace(inputs, revenue_per_day=rev)
        schedule = build_schedule(tweaked)
        return calculate_npv(schedule, inputs.discount_rate)

    try:
        root = brentq(_npv_at_rev, 1.0, _BREAKEVEN_HI)
        return float(root)  # type: ignore[arg-type]
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------


def sensitivity_analysis(
    inputs: VesselInputs,
    rev_min: float | None = None,
    rev_max: float | None = None,
) -> list[SensitivityPoint]:
    """IRR at each $1,000 revenue-per-day step across the given range.

    Default range is ±$5,000 from the vessel's entered revenue per day.
    Both bounds are clamped to a minimum of $1 to avoid non-positive revenue.
    The endpoint ``rev_max`` is included when it falls on a $1,000 step.

    Parameters
    ----------
    inputs
        Fully validated vessel inputs.
    rev_min
        Lower bound of the revenue range (per day, USD). Defaults to
        ``inputs.revenue_per_day - 5,000``.
    rev_max
        Upper bound of the revenue range (per day, USD). Defaults to
        ``inputs.revenue_per_day + 5,000``.
    """
    default_lo = inputs.revenue_per_day - _SENSITIVITY_DEFAULT_BAND
    default_hi = inputs.revenue_per_day + _SENSITIVITY_DEFAULT_BAND
    lo = max(1, int(round(rev_min if rev_min is not None else default_lo)))
    hi = int(round(rev_max if rev_max is not None else default_hi))

    if lo > hi:
        lo, hi = hi, lo

    points: list[SensitivityPoint] = []
    for rev in range(lo, hi + 1, _SENSITIVITY_STEP):
        tweaked = dataclasses.replace(inputs, revenue_per_day=float(rev))
        schedule = build_schedule(tweaked)
        irr = calculate_irr([row.net_cashflow for row in schedule])
        points.append(SensitivityPoint(revenue_per_day=float(rev), irr=irr))

    return points


# ---------------------------------------------------------------------------
# Scenario analysis
# ---------------------------------------------------------------------------


def scenario_returns(
    inputs: VesselInputs,
    bundles: list[ScenarioBundle] | None = None,
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
            investment_signal=investment_signal(irr, bundle.discount_rate),
        )

    return results


# ---------------------------------------------------------------------------
# Full enrichment entry point
# ---------------------------------------------------------------------------


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
    return dataclasses.replace(
        base,
        breakeven_rate=breakeven_revenue(inputs),
        sensitivity=sensitivity_analysis(inputs, rev_min, rev_max),
        scenarios=scenario_returns(inputs, bundles),
    )
