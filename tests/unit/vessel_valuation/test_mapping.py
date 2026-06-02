"""Unit tests for ``VesselInputs`` field-driven mapping."""

from dataclasses import replace
from datetime import date

import pytest

from vessel_valuation.mapping import VESSEL_INPUT_FIELD_NAMES
from vessel_valuation.mapping import VesselInputField
from vessel_valuation.mapping import vessel_inputs_from_dict
from vessel_valuation.mapping import vessel_inputs_from_object
from vessel_valuation.mapping import vessel_inputs_to_dict
from vessel_valuation.mapping import vessel_inputs_to_form_raw_dict
from vessel_valuation.schema import VesselInputs


@pytest.fixture
def sample_inputs() -> VesselInputs:
    """Return validated vessel inputs for mapping round-trip tests."""
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


def test_vessel_inputs_dict_round_trip(sample_inputs: VesselInputs) -> None:
    """``to_dict`` then ``from_dict`` preserves all field values including optionals."""
    inputs = replace(sample_inputs, engine_type='LNG DF', co2_carbon_factor=0.78)
    restored = vessel_inputs_from_dict(vessel_inputs_to_dict(inputs))
    assert restored == inputs


def test_vessel_inputs_from_object_matches_dataclass(sample_inputs: VesselInputs) -> None:
    """``from_object`` on a dataclass instance returns an equal ``VesselInputs``."""
    assert vessel_inputs_from_object(sample_inputs) == sample_inputs


def test_vessel_input_field_names_match_dataclass_fields() -> None:
    """``VesselInputField`` values cover every ``VesselInputs`` field exactly once."""
    assert frozenset(VesselInputField) == frozenset(VESSEL_INPUT_FIELD_NAMES)


def test_vessel_inputs_to_form_raw_dict_uses_iso_date_and_empty_optionals(
    sample_inputs: VesselInputs,
) -> None:
    """Form raw dict uses ISO purchase date and empty strings for unset optionals."""
    raw = vessel_inputs_to_form_raw_dict(sample_inputs)
    assert raw[VesselInputField.PURCHASE_DATE] == '2025-12-31'
    assert raw[VesselInputField.ENGINE_TYPE] == ''
    assert raw[VesselInputField.CO2_CARBON_FACTOR] == ''


def test_vessel_inputs_from_dict_rejects_non_iso_purchase_date() -> None:
    """Non-string ``purchase_date`` in store payload raises ``TypeError``."""
    data = vessel_inputs_to_dict(
        VesselInputs(
            vessel_name='X',
            purchase_price=1.0,
            vessel_life=1,
            residual_value=1.0,
            lw_tonnage=1.0,
            revenue_per_day=1.0,
            offhire_rate=0.01,
            opex_per_day=1.0,
            drydock_capex=1.0,
            drydock_frequency=1,
            upgrades_capex=1.0,
            inflation_rate=0.01,
            discount_rate=0.01,
            days_of_year=365,
            teu_size=100,
            purchase_date=date(2025, 1, 1),
        )
    )
    data['purchase_date'] = 20250101
    with pytest.raises(TypeError, match='purchase_date'):
        vessel_inputs_from_dict(data)
