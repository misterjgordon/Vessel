"""Unit tests for comma-separated form field formatting."""

from datetime import date

from app.form_formatting import format_display_number
from app.form_formatting import parse_display_number
from app.serialization import form_values_to_raw
from app.serialization import vessel_inputs_to_form_values
from vessel_valuation.mapping import VesselInputField
from vessel_valuation.schema import VesselInputs
from vessel_valuation.validation import validate


def test_format_display_number_uses_commas() -> None:
    """Large integers render with thousands separators."""
    assert format_display_number(9_000_000) == '9,000,000'
    assert format_display_number(45_500) == '45,500'


def test_parse_display_number_strips_commas() -> None:
    """Comma-grouped strings parse back to numeric values."""
    assert parse_display_number('9,000,000') == 9_000_000
    assert parse_display_number('45,500') == 45_500


def test_parse_display_number_returns_none_for_non_numeric_text() -> None:
    """Invalid numeric text returns None so Tier 1 structural rules can reject it."""
    assert parse_display_number('test') is None


def test_form_values_to_raw_parses_comma_fields() -> None:
    """form_values_to_raw converts comma-formatted money fields for validation."""
    raw = form_values_to_raw(
        {
            'vessel_name': 'Test',
            'purchase_price': '90,000,000',
            'vessel_life': '25',
            'residual_value': '5,238,000',
            'lw_tonnage': '13,095',
            'revenue_per_day': '45,500',
            'offhire_rate': 0.02,
            'opex_per_day': '10,500',
            'drydock_capex': '5,240,000',
            'drydock_frequency': '5',
            'upgrades_capex': '500,000',
            'inflation_rate': 0.03,
            'discount_rate': 0.1,
            'days_of_year': '365',
            'teu_size': '7,460',
            'purchase_date': '2026-03-31',
            'engine_type': '',
            'co2_carbon_factor': '',
        }
    )
    assert raw['purchase_price'] == 90_000_000
    assert raw['teu_size'] == 7_460


def test_form_values_to_raw_non_numeric_purchase_price_fails_tier1() -> None:
    """Non-numeric purchase price in the manual form yields a Tier 1 purchase-price error."""
    raw = form_values_to_raw(
        {
            'vessel_name': 'Base Case',
            'purchase_price': 'test',
            'vessel_life': '25',
            'residual_value': '5,000,000',
            'lw_tonnage': '12,500',
            'revenue_per_day': '50,000',
            'offhire_rate': 0.02,
            'opex_per_day': '10,000',
            'drydock_capex': '5,000,000',
            'drydock_frequency': '5',
            'upgrades_capex': '500,000',
            'inflation_rate': 0.03,
            'discount_rate': 0.1,
            'days_of_year': '365',
            'teu_size': '10,000',
            'purchase_date': '2025-12-31',
            'engine_type': '',
            'co2_carbon_factor': '',
        }
    )
    assert raw['purchase_price'] is None

    validation = validate(raw)
    assert validation.inputs is None
    assert any('Purchase price' in err for err in validation.errors)


def test_vessel_inputs_to_form_values_formats_large_numbers() -> None:
    """Loading inputs into the form applies comma display formatting."""
    inputs = VesselInputs(
        vessel_name='Athena',
        purchase_price=90_000_000.0,
        vessel_life=25,
        residual_value=5_238_000.0,
        lw_tonnage=13_095.0,
        revenue_per_day=45_500.0,
        offhire_rate=0.02,
        opex_per_day=10_500.0,
        drydock_capex=5_240_000.0,
        drydock_frequency=5,
        upgrades_capex=500_000.0,
        inflation_rate=0.03,
        discount_rate=0.10,
        days_of_year=365,
        teu_size=7_460,
        purchase_date=date(2026, 3, 31),
        engine_type='LNG DF',
        co2_carbon_factor=0.78,
    )
    form = vessel_inputs_to_form_values(inputs)
    assert form[VesselInputField.PURCHASE_PRICE] == '90,000,000'
    assert form[VesselInputField.OFFHIRE_RATE] == 0.02
