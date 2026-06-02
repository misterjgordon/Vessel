"""Breakeven revenue search — revenue per day at which NPV equals zero."""

import dataclasses
from typing import TYPE_CHECKING
from typing import cast

from scipy.optimize import brentq

from vessel_valuation.dcf import build_schedule
from vessel_valuation.dcf import calculate_npv

if TYPE_CHECKING:
    from vessel_valuation.schema import VesselInputs

_BREAKEVEN_HI: float = 1_000_000.0


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
        return float(cast('float', brentq(_npv_at_rev, 1.0, _BREAKEVEN_HI)))
    except ValueError:
        return None
