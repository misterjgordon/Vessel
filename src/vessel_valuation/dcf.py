"""DCF valuation engine for single-vessel investment analysis."""

from datetime import date
from typing import cast

from scipy.optimize import brentq

from vessel_valuation.schema import SIGNAL_BAND
from vessel_valuation.schema import CashflowYear
from vessel_valuation.schema import DcfResult
from vessel_valuation.schema import VesselInputs


def _year_end(base_year: int, t: int) -> date:
    """Dec 31 of the year that is ``t`` years after ``base_year``."""
    return date(base_year + t, 12, 31)


def build_schedule(inputs: VesselInputs) -> list[CashflowYear]:
    """Build the annual cashflow schedule from vessel inputs.

    Year 0 is the purchase outflow only. Years 1–T are operating years.
    Inflation applies to OpEx and CapEx from year 1; revenue is fixed
    under a time-charter contract. Drydock occurs at every multiple of
    ``drydock_frequency`` except the final operating year. Residual value
    is added to the net cashflow of the final year only.

    Parameters
    ----------
    inputs
        Validated vessel inputs from the structural and business-rule layers.

    Returns
    -------
    list[CashflowYear]
        One entry per year from 0 to ``inputs.vessel_life``, inclusive.
    """
    base_year = inputs.purchase_date.year
    daily_revenue = inputs.revenue_per_day * (1 - inputs.offhire_rate)
    annual_revenue = daily_revenue * inputs.days_of_year

    schedule: list[CashflowYear] = []
    cumulative = 0.0

    purchase_cf = -inputs.purchase_price
    cumulative += purchase_cf
    schedule.append(
        CashflowYear(
            year=0,
            period_end=_year_end(base_year, 0),
            revenue=0.0,
            opex=0.0,
            drydock_capex=0.0,
            upgrades_capex=0.0,
            free_cashflow=0.0,
            net_cashflow=purchase_cf,
            discounted_cashflow=purchase_cf,
            cumulative_cashflow=cumulative,
        )
    )

    for t in range(1, inputs.vessel_life + 1):
        inflation_factor = (1 + inputs.inflation_rate) ** t
        discount_factor = (1 + inputs.discount_rate) ** t

        opex = inputs.opex_per_day * inputs.days_of_year * inflation_factor

        is_drydock = (t % inputs.drydock_frequency == 0) and (t < inputs.vessel_life)
        drydock_capex = inputs.drydock_capex * inflation_factor if is_drydock else 0.0
        upgrades_capex = inputs.upgrades_capex * inflation_factor

        fcf = annual_revenue - opex - drydock_capex - upgrades_capex
        net_cf = fcf + (inputs.residual_value if t == inputs.vessel_life else 0.0)
        cumulative += net_cf

        schedule.append(
            CashflowYear(
                year=t,
                period_end=_year_end(base_year, t),
                revenue=annual_revenue,
                opex=opex,
                drydock_capex=drydock_capex,
                upgrades_capex=upgrades_capex,
                free_cashflow=fcf,
                net_cashflow=net_cf,
                discounted_cashflow=net_cf / discount_factor,
                cumulative_cashflow=cumulative,
            )
        )

    return schedule


def calculate_npv(schedule: list[CashflowYear], discount_rate: float) -> float:
    """Sum discounted net cashflows at the given rate.

    Recomputes discounting from the schedule's net cashflows so the
    function can be called with any rate (e.g. a scenario rate that
    differs from the rate used when the schedule was built).

    Parameters
    ----------
    schedule
        Annual cashflow schedule from ``build_schedule``.
    discount_rate
        Rate to apply, expressed as a decimal (e.g. 0.10 for 10%).
    """
    return sum(row.net_cashflow / (1 + discount_rate) ** row.year for row in schedule)


def calculate_irr(net_cashflows: list[float]) -> float | None:
    """Solve for the IRR using Brent's bracketed root-finding method.

    Returns ``None`` when no real solution exists in the bracket
    (−99 % to +999 %). The caller should display 'No solution' rather
    than propagate a missing value silently.

    Parameters
    ----------
    net_cashflows
        Series of net cashflows starting at year 0 (purchase outflow).
    """

    def _npv(r: float) -> float:
        return sum(cf / (1 + r) ** t for t, cf in enumerate(net_cashflows))

    try:
        # brentq stubs omit full_output=False; root is not narrowed to float.
        return float(cast('float', brentq(_npv, -0.99, 9.99)))
    except ValueError:
        return None


def investment_signal(
    irr: float | None,
    discount_rate: float,
    signal_band: float = SIGNAL_BAND,
) -> str:
    """Classify economics relative to the discount rate hurdle.

    FAVORABLE    IRR exceeds discount_rate by more than ``signal_band``.
    MARGINAL     IRR is within ``signal_band`` of discount_rate.
    UNFAVORABLE  IRR is below discount_rate by more than ``signal_band``,
                 or no IRR could be computed.
    """
    if irr is None:
        return 'UNFAVORABLE'
    if irr > discount_rate + signal_band:
        return 'FAVORABLE'
    if irr < discount_rate - signal_band:
        return 'UNFAVORABLE'
    return 'MARGINAL'


def _payback_year(schedule: list[CashflowYear]) -> int | None:
    """First year when cumulative undiscounted net cashflow turns positive."""
    for row in schedule:
        if row.cumulative_cashflow > 0:
            return row.year
    return None


def compute_npv_irr(
    inputs: VesselInputs,
    signal_band: float = SIGNAL_BAND,
) -> DcfResult:
    """Compute core DCF outputs for one vessel.

    Builds the cashflow schedule, derives NPV and IRR, and adds the
    payback year and investment signal. Breakeven rate, sensitivity,
    and scenario results are populated separately by ``decision_insights``.

    Parameters
    ----------
    inputs
        Fully validated vessel inputs.

    Returns
    -------
    DcfResult
        Schedule, NPV, IRR, payback, and investment signal only.
    """
    schedule = build_schedule(inputs)
    net_cashflows: list[float] = [row.net_cashflow for row in schedule]
    npv = calculate_npv(schedule, inputs.discount_rate)
    irr = calculate_irr(net_cashflows)

    return DcfResult(
        npv=npv,
        irr=irr,
        schedule=schedule,
        payback_year=_payback_year(schedule),
        investment_signal=investment_signal(
            irr,
            inputs.discount_rate,
            signal_band=signal_band,
        ),
    )
