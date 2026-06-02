"""
NPV and IRR for four purchase-price scenarios (80M–110M), shared operating assumptions.
uv run --extra dev pytest tests/unit/vessel_valuation/test_purchase_price_scenarios.py -v
"""

from dataclasses import replace

import pytest

from vessel_valuation.dcf import compute_npv_irr
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vessel_valuation.schema import VesselInputs


@pytest.mark.parametrize(
    ('purchase_price', 'expected_npv', 'expected_irr'),
    [
        (80_000_000.0, 24_143_625.443279, 0.141644),
        (90_000_000.0, 14_143_625.443279, 0.121946),
        (100_000_000.0, 4_143_625.443279, 0.105855),
        (110_000_000.0, -5_856_374.556721, 0.092389),
    ],
    ids=['80M', '90M', '100M', '110M'],
)
def test_compute_npv_irr_by_purchase_price(
    base_inputs: VesselInputs,
    purchase_price: float,
    expected_npv: float,
    expected_irr: float,
) -> None:
    """NPV and IRR match engine output for each purchase-price scenario."""
    inputs = replace(base_inputs, purchase_price=purchase_price)
    result = compute_npv_irr(inputs)

    assert result.npv == pytest.approx(expected_npv, rel=1e-4)
    assert result.irr == pytest.approx(expected_irr, rel=1e-4)
