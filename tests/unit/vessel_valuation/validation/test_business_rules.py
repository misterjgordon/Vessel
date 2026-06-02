# Run: uv run --extra dev pytest \
#   tests/unit/vessel_valuation/validation/test_business_rules.py -v
"""Tests for ``validation.business_rules`` via ``validate``."""

from tests.unit.vessel_valuation.validation.conftest import BASE_RAW, raw
from vessel_valuation.case_study_benchmarks import load_case_study_pp_teu_benchmarks
from vessel_valuation.schema import ValidationThresholds
from vessel_valuation.validation import validate
from vessel_valuation.validation.business_rules import (
    BUSINESS_RULES,
    TEU_BUCKET_ROUNDING,
    nearest_teu_bucket,
)


def test_residual_exceeds_purchase_price_triggers_warning() -> None:
    """Residual above purchase price triggers a business-rule warning, not an error."""
    result = validate(raw(residual_value=200_000_000.0))
    assert result.errors == []
    assert result.inputs is not None
    assert any('residual' in w.lower() for w in result.warnings)


def test_revenue_below_opex_triggers_warning() -> None:
    """Daily revenue below daily opex triggers a business-rule warning."""
    result = validate(raw(revenue_per_day=5_000.0, opex_per_day=10_000.0))
    assert result.errors == []
    assert any('opex' in w.lower() or 'revenue' in w.lower() for w in result.warnings)


def test_pp_teu_factor_outside_benchmark_triggers_warning() -> None:
    """PP/TEU factor far from the 10,000 TEU seed triggers a business-rule warning."""
    result = validate(raw(purchase_price=9_000_000.0))
    assert result.errors == []
    assert any('Purchase-price÷TEU ratio' in w for w in result.warnings)


def test_revenue_outside_teu_benchmark_triggers_warning() -> None:
    """Revenue per day far from the TEU-size benchmark triggers a business-rule warning."""
    result = validate(raw(revenue_per_day=10_000.0))
    assert result.errors == []
    assert any('revenue' in w.lower() for w in result.warnings)


def test_all_business_rules_have_unique_codes() -> None:
    """Every business validation rule has a distinct warning code."""
    codes = [r.code for r in BUSINESS_RULES]
    assert len(codes) == len(set(codes))


def test_all_business_rules_have_unique_names() -> None:
    """Every business validation rule has a distinct catalog name."""
    names = [r.name for r in BUSINESS_RULES]
    assert len(names) == len(set(names))


def test_business_rule_catalog_includes_four_rules() -> None:
    """Catalog lists residual, margin, PP÷TEU, and TEU revenue rules."""
    names = {r.name for r in BUSINESS_RULES}
    assert names == {
        'residual_below_purchase',
        'revenue_below_opex',
        'pp_teu_factor_band',
        'teu_revenue_band',
    }


def test_wider_revenue_band_suppresses_teu_revenue_warning() -> None:
    """A larger revenue_band threshold suppresses the TEU revenue warning."""
    strict = validate(raw(revenue_per_day=44_000.0))
    assert any('outside the expected range' in w for w in strict.warnings)

    loose = ValidationThresholds(revenue_band=50_000.0)
    relaxed = validate(raw(revenue_per_day=44_000.0), thresholds=loose)
    assert not any('outside the expected range' in w for w in relaxed.warnings)


def test_pp_teu_factor_seed_for_8000_teu() -> None:
    """Seed benchmark for 8,000 TEU is $90M / 8,000 = 11,250×."""
    assert load_case_study_pp_teu_benchmarks()[8_000] == 11_250.0


def test_55m_on_8000_teu_warns_against_seed_without_database() -> None:
    """$55M at 8,000 TEU is outside ±10% of the seed PP/TEU factor with no fleet data."""
    result = validate(raw(teu_size=8_000, purchase_price=55_000_000.0))
    assert result.errors == []
    assert any('Purchase-price÷TEU ratio' in w for w in result.warnings)
    assert any('6,875×' in w for w in result.warnings)


def test_90m_on_8000_teu_ok_against_seed() -> None:
    """$90M at 8,000 TEU matches the seed PP/TEU factor band."""
    result = validate(raw(teu_size=8_000, purchase_price=90_000_000.0))
    assert result.errors == []
    assert not any('Purchase-price÷TEU ratio' in w for w in result.warnings)


def test_fleet_override_replaces_seed_for_same_teu() -> None:
    """Fleet median PP/TEU factor overrides the seed when provided."""
    result = validate(
        raw(teu_size=8_000, purchase_price=90_000_000.0),
        pp_teu_factor_benchmarks={8_000: 5_000.0},
    )
    assert any('Purchase-price÷TEU ratio' in w for w in result.warnings)


def test_teu_bucket_rounding_step_is_1000() -> None:
    """Fleet benchmarks group TEU sizes in 1,000-TEU steps."""
    assert TEU_BUCKET_ROUNDING == 1000


def test_nearest_teu_bucket_rounds_to_nearest_1000() -> None:
    """Case-study-sized vessels map to the expected benchmark bucket."""
    assert nearest_teu_bucket(7_460) == 7_000
    assert nearest_teu_bucket(10_400) == 10_000
    assert nearest_teu_bucket(10_600) == 11_000
