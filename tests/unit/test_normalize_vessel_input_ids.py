"""Tests for saved-vessel delete dropdown id coercion."""

from app.callbacks import _normalize_vessel_input_ids


def test_normalize_vessel_input_ids_accepts_single_int() -> None:
    """A bare int from Dash multi-select is coerced to a one-element id list."""
    assert _normalize_vessel_input_ids(8) == [8]


def test_normalize_vessel_input_ids_accepts_int_list() -> None:
    """A list of ids is returned unchanged as ints."""
    assert _normalize_vessel_input_ids([3, 8]) == [3, 8]


def test_normalize_vessel_input_ids_accepts_string_ids() -> None:
    """String ids from JSON serialization are parsed as integers."""
    assert _normalize_vessel_input_ids(['8', '10']) == [8, 10]


def test_normalize_vessel_input_ids_none_is_empty() -> None:
    """None selection yields an empty list."""
    assert _normalize_vessel_input_ids(None) == []
