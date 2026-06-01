# Run: uv run --extra dev pytest tests/unit/test_validation_pp_teu_factor.py -v
"""Tier 2 PP/TEU factor benchmark tests."""

from vessel_valuation.case_study_benchmarks import load_case_study_pp_teu_benchmarks
from vessel_valuation.validation import validate


def _raw(**overrides: object) -> dict[str, object]:
    from tests.unit.test_validation import BASE_RAW

    row = dict(BASE_RAW)
    row.update(overrides)
    return row


def test_pp_teu_factor_seed_for_8000_teu() -> None:
    """Seed benchmark for 8,000 TEU is $90M / 8,000 = 11,250×."""
    assert load_case_study_pp_teu_benchmarks()[8_000] == 11_250.0


def test_55m_on_8000_teu_warns_against_seed_without_database() -> None:
    """$55M at 8,000 TEU is outside ±10% of the seed PP/TEU factor with no fleet data."""
    raw = _raw(teu_size=8_000, purchase_price=55_000_000.0)
    result = validate(raw)
    assert result.errors == []
    assert any('Purchase-price÷TEU ratio' in w for w in result.warnings)
    assert any('6,875×' in w for w in result.warnings)


def test_90m_on_8000_teu_ok_against_seed() -> None:
    """$90M at 8,000 TEU matches the seed PP/TEU factor band."""
    raw = _raw(teu_size=8_000, purchase_price=90_000_000.0)
    result = validate(raw)
    assert result.errors == []
    assert not any('Purchase-price÷TEU ratio' in w for w in result.warnings)


def test_fleet_override_replaces_seed_for_same_teu() -> None:
    """Fleet median PP/TEU factor overrides the seed when provided."""
    raw = _raw(teu_size=8_000, purchase_price=90_000_000.0)
    result = validate(raw, pp_teu_factor_benchmarks={8_000: 5_000.0})
    assert any('Purchase-price÷TEU ratio' in w for w in result.warnings)
