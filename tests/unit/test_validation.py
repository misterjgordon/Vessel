"""Validation layer tests — Tier 1 errors and Tier 2 warnings."""

from datetime import date, datetime

import pytest

from vessel_valuation.validation import (
    TIER1_RULES,
    TIER2_RULES,
    validate,
)

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


def _raw(**overrides: object) -> dict[str, object]:
    return {**BASE_RAW, **overrides}


def test_valid_inputs_produce_no_errors() -> None:
    """Well-formed inputs pass Tier 1 validation with no errors."""
    result = validate(BASE_RAW)
    assert result.errors == []
    assert result.inputs is not None


def test_valid_inputs_coerce_to_vessel_inputs() -> None:
    """Valid raw dict coerces to VesselInputs with expected numeric fields."""
    result = validate(BASE_RAW)
    assert result.inputs is not None
    assert result.inputs.purchase_price == 100_000_000.0
    assert result.inputs.vessel_life == 25
    assert result.inputs.teu_size == 10_000


@pytest.mark.parametrize(
    'sentinel',
    ['#VALUE!', '#N/A', '-', '', 'n/a', '#REF!'],
)
def test_sentinel_in_purchase_price_raises_error(sentinel: str) -> None:
    """Excel sentinel strings in purchase_price fail Tier 1 validation."""
    result = validate(_raw(purchase_price=sentinel))
    assert result.errors
    assert result.inputs is None


def test_sentinel_in_residual_does_not_block_if_lw_tonnage_valid() -> None:
    """Invalid residual sentinel falls back to lw_tonnage-derived value when tonnage is valid."""
    result = validate(_raw(residual_value='#VALUE!'))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.residual_value == pytest.approx(12_500.0 * 400.0)


def test_missing_vessel_name_raises_error() -> None:
    """Empty vessel name fails Tier 1 validation."""
    result = validate(_raw(vessel_name=''))
    assert any('name' in e.lower() for e in result.errors)
    assert result.inputs is None


def test_zero_purchase_price_raises_error() -> None:
    """Zero purchase price fails Tier 1 validation."""
    result = validate(_raw(purchase_price=0.0))
    assert result.errors
    assert result.inputs is None


def test_vessel_life_zero_raises_error() -> None:
    """Zero vessel life fails Tier 1 validation."""
    result = validate(_raw(vessel_life=0))
    assert result.errors
    assert result.inputs is None


def test_negative_lw_tonnage_raises_error() -> None:
    """Negative lightweight tonnage fails Tier 1 validation."""
    result = validate(_raw(lw_tonnage=-1.0))
    assert result.errors
    assert result.inputs is None


def test_offhire_rate_at_or_above_one_raises_error() -> None:
    """Offhire rate at or above 100% fails Tier 1 validation."""
    result = validate(_raw(offhire_rate=1.0))
    assert result.errors

    result2 = validate(_raw(offhire_rate=1.5))
    assert result2.errors


def test_discount_rate_zero_raises_error() -> None:
    """Zero discount rate fails Tier 1 validation."""
    result = validate(_raw(discount_rate=0.0))
    assert result.errors


def test_days_of_year_not_365_raises_error() -> None:
    """Days-of-year other than 365 fails Tier 1 validation."""
    result = validate(_raw(days_of_year=360))
    assert result.errors
    assert result.inputs is None


def test_days_of_year_366_raises_error() -> None:
    """366 days per year fails Tier 1 validation."""
    result = validate(_raw(days_of_year=366))
    assert result.errors


def test_missing_purchase_date_raises_error() -> None:
    """Missing purchase date fails Tier 1 validation."""
    result = validate(_raw(purchase_date=None))
    assert result.errors
    assert result.inputs is None


def test_purchase_date_as_string_iso_format_accepted() -> None:
    """ISO date string purchase_date coerces to date without errors."""
    result = validate(_raw(purchase_date='2025-12-31'))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_purchase_date_as_excel_datetime_accepted() -> None:
    """Excel datetime purchase_date coerces to date without errors."""
    result = validate(_raw(purchase_date=datetime(2025, 12, 31)))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_residual_derived_from_lw_tonnage_when_absent() -> None:
    """Missing residual_value is derived from lw_tonnage at $400 per tonne."""
    raw = {k: v for k, v in BASE_RAW.items() if k != 'residual_value'}
    result = validate(raw)
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.residual_value == pytest.approx(12_500.0 * 400.0)


def test_provided_residual_takes_precedence_over_derived() -> None:
    """Explicit residual_value overrides the lw_tonnage-derived default."""
    result = validate(_raw(residual_value=4_000_000.0))
    assert result.inputs is not None
    assert result.inputs.residual_value == pytest.approx(4_000_000.0)


def test_residual_exceeds_purchase_price_triggers_warning() -> None:
    """Residual above purchase price triggers a Tier 2 warning, not an error."""
    result = validate(_raw(residual_value=200_000_000.0))
    assert result.errors == []
    assert result.inputs is not None
    assert any('residual' in w.lower() for w in result.warnings)


def test_revenue_below_opex_triggers_warning() -> None:
    """Daily revenue below daily opex triggers a Tier 2 warning."""
    result = validate(_raw(revenue_per_day=5_000.0, opex_per_day=10_000.0))
    assert result.errors == []
    assert any('opex' in w.lower() or 'revenue' in w.lower() for w in result.warnings)


def test_purchase_price_outside_teu_benchmark_triggers_warning() -> None:
    """Purchase price far from the TEU-size benchmark triggers a Tier 2 warning."""
    result = validate(_raw(purchase_price=9_000_000.0))
    assert result.errors == []
    assert any('teu' in w.lower() or 'purchase price' in w.lower() for w in result.warnings)


def test_revenue_outside_teu_benchmark_triggers_warning() -> None:
    """Revenue per day far from the TEU-size benchmark triggers a Tier 2 warning."""
    result = validate(_raw(revenue_per_day=10_000.0))
    assert result.errors == []
    assert any('revenue' in w.lower() for w in result.warnings)


def test_clean_inputs_produce_no_warnings() -> None:
    """Benchmark-consistent base inputs produce no Tier 2 warnings."""
    result = validate(BASE_RAW)
    assert result.warnings == []


def test_all_tier1_rules_have_unique_codes() -> None:
    """Every Tier 1 validation rule has a distinct error code."""
    codes = [r.code for r in TIER1_RULES]
    assert len(codes) == len(set(codes))


def test_all_tier2_rules_have_unique_codes() -> None:
    """Every Tier 2 validation rule has a distinct warning code."""
    codes = [r.code for r in TIER2_RULES]
    assert len(codes) == len(set(codes))
