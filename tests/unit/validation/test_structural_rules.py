# Run: uv run --extra dev pytest tests/unit/validation/test_structural_rules.py -v
"""Structural validation tests — errors that block coercion and computation."""

from datetime import date, datetime

import pytest

from tests.unit.validation.conftest import BASE_RAW, raw
from vessel_valuation.validation import validate
from vessel_valuation.validation.structural_rules import STRUCTURAL_RULES


def test_valid_inputs_produce_no_errors() -> None:
    """Well-formed inputs pass structural validation with no errors."""
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
    """Excel sentinel strings in purchase_price fail structural validation."""
    result = validate(raw(purchase_price=sentinel))
    assert result.errors
    assert result.inputs is None


def test_sentinel_in_residual_value_raises_error() -> None:
    """Invalid residual sentinel fails structural validation."""
    result = validate(raw(residual_value='#VALUE!'))
    assert result.errors
    assert result.inputs is None


def test_missing_vessel_name_raises_error() -> None:
    """Empty vessel name fails structural validation."""
    result = validate(raw(vessel_name=''))
    assert any('name' in e.lower() for e in result.errors)
    assert result.inputs is None


def test_zero_purchase_price_raises_error() -> None:
    """Zero purchase price fails structural validation."""
    result = validate(raw(purchase_price=0.0))
    assert result.errors
    assert result.inputs is None


def test_vessel_life_zero_raises_error() -> None:
    """Zero vessel life fails structural validation."""
    result = validate(raw(vessel_life=0))
    assert result.errors
    assert result.inputs is None


def test_negative_lw_tonnage_raises_error() -> None:
    """Negative lightweight tonnage fails structural validation."""
    result = validate(raw(lw_tonnage=-1.0))
    assert result.errors
    assert result.inputs is None


def test_offhire_rate_at_or_above_one_raises_error() -> None:
    """Offhire rate at or above 100% fails structural validation."""
    result = validate(raw(offhire_rate=1.0))
    assert result.errors

    result2 = validate(raw(offhire_rate=1.5))
    assert result2.errors


def test_discount_rate_zero_raises_error() -> None:
    """Zero discount rate fails structural validation."""
    result = validate(raw(discount_rate=0.0))
    assert result.errors


def test_days_of_year_not_365_raises_error() -> None:
    """Days-of-year other than 365 fails structural validation."""
    result = validate(raw(days_of_year=360))
    assert result.errors
    assert result.inputs is None


def test_days_of_year_366_raises_error() -> None:
    """366 days per year fails structural validation."""
    result = validate(raw(days_of_year=366))
    assert result.errors


def test_missing_purchase_date_raises_error() -> None:
    """Missing purchase date fails structural validation."""
    result = validate(raw(purchase_date=None))
    assert result.errors
    assert result.inputs is None


def test_purchase_date_as_string_iso_format_accepted() -> None:
    """ISO date string purchase_date coerces to date without errors."""
    result = validate(raw(purchase_date='2025-12-31'))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_purchase_date_as_excel_datetime_accepted() -> None:
    """Excel datetime purchase_date coerces to date without errors."""
    result = validate(raw(purchase_date=datetime(2025, 12, 31)))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_missing_residual_value_raises_error() -> None:
    """Missing residual_value fails structural validation."""
    row = {k: v for k, v in BASE_RAW.items() if k != 'residual_value'}
    result = validate(row)
    assert result.errors
    assert result.inputs is None


def test_residual_value_coerced_when_provided() -> None:
    """Explicit residual_value is coerced to float on the VesselInputs instance."""
    result = validate(raw(residual_value=4_000_000.0))
    assert result.inputs is not None
    assert result.inputs.residual_value == pytest.approx(4_000_000.0)


def test_all_structural_rules_have_unique_codes() -> None:
    """Every structural validation rule has a distinct error code."""
    codes = [r.code for r in STRUCTURAL_RULES]
    assert len(codes) == len(set(codes))
