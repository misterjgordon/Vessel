# Run: uv run --extra dev pytest tests/unit/vessel_valuation/validation/test_validate.py -v
"""Tests for ``validation.validate`` orchestration (``validation/__init__.py``)."""

from tests.unit.vessel_valuation.validation.conftest import BASE_RAW
from tests.unit.vessel_valuation.validation.conftest import raw
from vessel_valuation.validation import validate


def test_valid_inputs_produce_no_errors() -> None:
    """Well-formed inputs pass validation with no errors or warnings."""
    result = validate(BASE_RAW)
    assert result.errors == []
    assert result.warnings == []
    assert result.inputs is not None


def test_valid_inputs_coerce_to_vessel_inputs() -> None:
    """Valid raw dict coerces to VesselInputs with expected numeric fields."""
    result = validate(BASE_RAW)
    assert result.inputs is not None
    assert result.inputs.purchase_price == 100_000_000.0
    assert result.inputs.vessel_life == 25
    assert result.inputs.teu_size == 10_000


def test_structural_errors_skip_business_warnings() -> None:
    """Tier 1 failures return no coerced inputs and no Tier 2 warnings."""
    result = validate(raw(purchase_price=0.0))
    assert result.errors
    assert result.inputs is None
    assert result.warnings == []
