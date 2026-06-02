"""Unit tests for saved-vessel dropdown label formatting."""

from datetime import UTC
from datetime import date
from datetime import datetime

from app.views.investment import format_saved_vessel_option_label
from vessel_valuation.db.repository import VesselInputSummary


def test_format_saved_vessel_option_label_includes_key_fields() -> None:
    """Dropdown label shows id, name, TEU, price, and purchase date."""
    summary = VesselInputSummary(
        id=42,
        vessel_name='Athena',
        teu_size=8500,
        purchase_price=90_000_000.0,
        purchase_date=date(2024, 6, 1),
        created_at=datetime(2024, 6, 2, 12, 0, tzinfo=UTC),
    )
    label = format_saved_vessel_option_label(summary)
    assert label == '#42 · Athena · 8,500 TEU · $90,000,000 · 2024-06-01'
