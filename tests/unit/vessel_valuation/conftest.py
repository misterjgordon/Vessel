"""Shared fixtures for vessel_valuation unit tests."""

from datetime import date

import pytest

from vessel_valuation.schema import VesselInputs


@pytest.fixture
def base_inputs() -> VesselInputs:
    """Return validated vessel inputs for a viable base-case valuation."""
    return VesselInputs(
        vessel_name='Base Case',
        purchase_price=100_000_000.0,
        vessel_life=25,
        residual_value=5_000_000.0,
        lw_tonnage=12_500.0,
        revenue_per_day=50_000.0,
        offhire_rate=0.02,
        opex_per_day=10_000.0,
        drydock_capex=5_000_000.0,
        drydock_frequency=5,
        upgrades_capex=500_000.0,
        inflation_rate=0.03,
        discount_rate=0.10,
        days_of_year=365,
        teu_size=10_000,
        purchase_date=date(2025, 12, 31),
    )
