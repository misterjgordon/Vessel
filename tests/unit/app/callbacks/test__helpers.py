"""Tests for saved-vessel delete dropdown id coercion."""

import pytest

from app.callbacks._helpers import normalize_vessel_input_ids
from app.callbacks._helpers import parse_signal_band
from vessel_valuation.schema import SIGNAL_BAND


def test_normalize_vessel_input_ids_accepts_single_int() -> None:
    """A bare int from Dash multi-select is coerced to a one-element id list."""
    assert normalize_vessel_input_ids(8) == [8]


def test_normalize_vessel_input_ids_accepts_int_list() -> None:
    """A list of ids is returned unchanged as ints."""
    assert normalize_vessel_input_ids([3, 8]) == [3, 8]


def test_normalize_vessel_input_ids_accepts_string_ids() -> None:
    """String ids from JSON serialization are parsed as integers."""
    assert normalize_vessel_input_ids(['8', '10']) == [8, 10]


def test_normalize_vessel_input_ids_none_is_empty() -> None:
    """None selection yields an empty list."""
    assert normalize_vessel_input_ids(None) == []


def test_parse_signal_band_defaults_when_empty() -> None:
    """Blank settings input falls back to the module default band."""
    assert parse_signal_band(None) == SIGNAL_BAND
    assert parse_signal_band('') == SIGNAL_BAND


def test_parse_signal_band_accepts_sub_cent_values() -> None:
    """Sub–whole-percentage bands such as 0.005 (0.5 pp) are valid."""
    assert parse_signal_band(0.005) == 0.005
    assert parse_signal_band('0.005') == 0.005


def test_parse_signal_band_rejects_out_of_range() -> None:
    """Signal band must be a positive decimal strictly below 1."""
    with pytest.raises(ValueError, match='greater than 0'):
        parse_signal_band(0)
    with pytest.raises(ValueError, match='greater than 0'):
        parse_signal_band(1.0)
