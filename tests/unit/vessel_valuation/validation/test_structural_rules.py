# Run: uv run --extra dev pytest \
#   tests/unit/vessel_valuation/validation/test_structural_rules.py -v
"""Tests for ``validation.structural_rules`` via ``validate``."""

import pytest

from tests.unit.vessel_valuation.validation.conftest import BASE_RAW, raw
from vessel_valuation.validation import validate
from vessel_valuation.validation.structural_rules import STRUCTURAL_RULES


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


def test_missing_residual_value_raises_error() -> None:
    """Missing residual_value fails structural validation."""
    row = {k: v for k, v in BASE_RAW.items() if k != 'residual_value'}
    result = validate(row)
    assert result.errors
    assert result.inputs is None


def test_all_structural_rules_have_unique_codes() -> None:
    """Every structural validation rule has a distinct error code."""
    codes = [r.code for r in STRUCTURAL_RULES]
    assert len(codes) == len(set(codes))
