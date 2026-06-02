"""Shared raw vessel dict fixtures for validation unit tests."""

from datetime import date

BASE_RAW: dict[str, object] = {
    'vessel_name': 'Test Vessel',
    'purchase_price': 100_000_000.0,
    'vessel_life': 25,
    'residual_value': 5_000_000.0,
    'lw_tonnage': 12_500.0,
    'revenue_per_day': 50_000.0,
    'offhire_rate': 0.02,
    'opex_per_day': 10_000.0,
    'drydock_capex': 5_000_000.0,
    'drydock_frequency': 5,
    'upgrades_capex': 500_000.0,
    'inflation_rate': 0.03,
    'discount_rate': 0.10,
    'days_of_year': 365,
    'teu_size': 10_000,
    'purchase_date': date(2025, 12, 31),
}


def raw(**overrides: object) -> dict[str, object]:
    """Return a copy of ``BASE_RAW`` with optional field overrides."""
    return {**BASE_RAW, **overrides}
