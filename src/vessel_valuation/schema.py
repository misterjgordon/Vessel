"""Domain dataclasses for vessel valuation inputs and computed results."""

from dataclasses import dataclass, field
from datetime import date

SCRAP_RATE_PER_TONNE: float = 400.0
SIGNAL_BAND: float = 0.02


@dataclass
class VesselInputs:
    """Validated inputs for a single vessel DCF valuation.

    Instances only exist after Tier 1 validation passes. All numeric
    fields are coerced to their declared types by the validation layer.
    ``purchase_date`` is required — it anchors the cashflow schedule to
    real calendar dates (each year-end is Dec 31 of purchase_year + t).
    """

    vessel_name: str
    purchase_price: float
    vessel_life: int
    residual_value: float
    lw_tonnage: float
    revenue_per_day: float
    offhire_rate: float
    opex_per_day: float
    drydock_capex: float
    drydock_frequency: int
    upgrades_capex: float
    inflation_rate: float
    discount_rate: float
    days_of_year: int
    teu_size: int
    purchase_date: date
    engine_type: str | None = None
    co2_carbon_factor: float | None = None


@dataclass
class ValidationThresholds:
    """Business-rule TEU benchmark warning sensitivity.

    Defaults match the case-study sample data (D-009). The app may supply
    overrides per session; validation logic reads these values only via
    parameters, not module globals.
    """

    revenue_band: float = 5_000.0
    price_tolerance: float = 0.10


DEFAULT_VALIDATION_THRESHOLDS = ValidationThresholds()


@dataclass
class ScenarioBundle:
    """A paired inflation + discount rate scenario bundle.

    Rates are linked via the Fisher equation — pairing prevents
    economically inconsistent combinations such as low inflation
    with a high discount rate.
    """

    name: str
    inflation_rate: float
    discount_rate: float


@dataclass
class CashflowYear:
    """One row of the annual cashflow schedule, matching the Calculation sheet.

    ``year`` is 0 for the purchase year, 1–T for operating years.
    ``period_end`` is Dec 31 of ``purchase_date.year + year``.
    ``net_cashflow`` includes the purchase price outflow at year 0
    and the residual value inflow at year T.
    """

    year: int
    period_end: date
    revenue: float
    opex: float
    drydock_capex: float
    upgrades_capex: float
    free_cashflow: float
    net_cashflow: float
    discounted_cashflow: float
    cumulative_cashflow: float


@dataclass
class SensitivityPoint:
    """Single data point on the IRR-vs-revenue sensitivity curve."""

    revenue_per_day: float
    irr: float | None


@dataclass
class ScenarioResult:
    """NPV, IRR, and investment signal for one Best/Base/Worst scenario."""

    npv: float
    irr: float | None
    investment_signal: str


def _empty_sensitivity_points() -> list[SensitivityPoint]:
    return []


def _empty_scenario_results() -> dict[str, ScenarioResult]:
    return {}


@dataclass
class DcfResult:
    """Core DCF outputs from ``dcf.compute_npv_irr`` — schedule, NPV, IRR, and signal.

    Does not include decision-insight fields (breakeven, sensitivity, scenarios).
    Those are attached by ``decision_insights.enrich`` in a ``ValuationResult``.
    """

    npv: float
    irr: float | None
    schedule: list[CashflowYear]
    payback_year: int | None
    investment_signal: str


@dataclass
class ValuationResult(DcfResult):
    """Enriched valuation — DCF core plus decision-insight analytics.

    Returned by ``decision_insights.enrich`` and persisted in the gold
    ``vessel_valuations`` table. Insight fields are empty until enrichment runs.
    """

    breakeven_rate: float | None = None
    sensitivity: list[SensitivityPoint] = field(default_factory=_empty_sensitivity_points)
    scenarios: dict[str, ScenarioResult] = field(default_factory=_empty_scenario_results)
