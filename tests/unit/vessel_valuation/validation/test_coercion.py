# Run: uv run --extra dev pytest tests/unit/vessel_valuation/validation/test_coercion.py -v
"""Tests for ``validation.coercion``."""

from datetime import date, datetime

import pytest

from tests.unit.vessel_valuation.validation.conftest import raw
from vessel_valuation.validation import validate
from vessel_valuation.validation.coercion import coerce_inputs, is_sentinel, to_date


@pytest.mark.parametrize('sentinel', ['#VALUE!', '-', '', None])
def test_is_sentinel_recognizes_excel_placeholders(sentinel: object) -> None:
    """Excel-style sentinel values are treated as missing."""
    assert is_sentinel(sentinel)


def test_to_date_parses_iso_string() -> None:
    """ISO date strings coerce to ``date``."""
    assert to_date({'purchase_date': '2025-12-31'}, 'purchase_date') == date(2025, 12, 31)


def test_to_date_extracts_date_from_datetime() -> None:
    """Datetime values coerce to calendar dates."""
    assert to_date({'purchase_date': datetime(2025, 12, 31)}, 'purchase_date') == date(
        2025, 12, 31
    )


def test_purchase_date_as_string_iso_format_accepted() -> None:
    """ISO date string purchase_date coerces through ``validate`` without errors."""
    result = validate(raw(purchase_date='2025-12-31'))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_purchase_date_as_excel_datetime_accepted() -> None:
    """Excel datetime purchase_date coerces through ``validate`` without errors."""
    result = validate(raw(purchase_date=datetime(2025, 12, 31)))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_coerce_inputs_maps_residual_value() -> None:
    """``coerce_inputs`` maps explicit residual_value to float on ``VesselInputs``."""
    inputs = coerce_inputs(raw(residual_value=4_000_000.0))
    assert inputs.residual_value == pytest.approx(4_000_000.0)
