"""Default manual-form values for the investment view."""

from datetime import date

# Representative base-case values aligned with decision-insights test fixtures.
FORM_DEFAULTS: dict[str, str | int | float | None] = {
    'vessel_name': 'Base Case',
    'purchase_price': 100_000_000,
    'vessel_life': 25,
    'residual_value': 5_000_000,
    'lw_tonnage': 12_500,
    'revenue_per_day': 50_000,
    'offhire_rate': 0.02,
    'opex_per_day': 10_000,
    'drydock_capex': 5_000_000,
    'drydock_frequency': 5,
    'upgrades_capex': 500_000,
    'inflation_rate': 0.03,
    'discount_rate': 0.10,
    'days_of_year': 365,
    'teu_size': 10_000,
    'purchase_date': date(2025, 12, 31).isoformat(),
    'engine_type': '',
    'co2_carbon_factor': '',
}
