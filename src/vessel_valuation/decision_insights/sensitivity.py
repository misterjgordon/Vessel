"""IRR sensitivity sweep across a revenue-per-day range."""

import dataclasses

from vessel_valuation.dcf import build_schedule, calculate_irr
from vessel_valuation.schema import SensitivityPoint, VesselInputs

_SENSITIVITY_STEP: int = 1_000
_SENSITIVITY_DEFAULT_BAND: float = 5_000.0


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
