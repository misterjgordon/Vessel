"""
Form value collection for the calculate callback.
uv run pytest tests/unit/app/callbacks/test_compute_form.py -v
"""

from app.serialization import form_values_to_raw
from app.views.investment import collect_form_values


def test_form_values_to_raw_keeps_purchase_date_as_string() -> None:
    """Purchase date stays a string; comma-formatted fields parse as numbers."""
    values = (
        'Athena',
        '100,000,000',
        '25',
        '5,000,000',
        '50,000',
        '25,000',
        '0.05',
        '8,000',
        '2,000,000',
        '5',
        '1,000,000',
        '0.02',
        '0.08',
        '360',
        '8,500',
        '2025-12-31',
        '',
        '',
    )
    form = collect_form_values(*values)
    raw = form_values_to_raw(form)

    assert raw['purchase_date'] == '2025-12-31'
    assert raw['teu_size'] == 8500
    assert raw['purchase_price'] == 100_000_000
