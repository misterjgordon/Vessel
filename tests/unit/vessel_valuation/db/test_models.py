"""Unit tests for ``db.models`` ORM definitions."""

from sqlalchemy import inspect

from vessel_valuation.db.models import VesselInputRow
from vessel_valuation.mapping import VESSEL_INPUT_FIELD_NAMES, VESSEL_INPUT_ROW_META_COLUMNS


def test_vessel_input_row_columns_match_field_names() -> None:
    """Silver ORM columns (excluding metadata) match every ``VesselInputs`` field name."""
    orm_columns = {column.key for column in inspect(VesselInputRow).columns}
    dataclass_fields = frozenset(VESSEL_INPUT_FIELD_NAMES)
    assert orm_columns - VESSEL_INPUT_ROW_META_COLUMNS == dataclass_fields
