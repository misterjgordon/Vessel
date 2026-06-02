"""
Unit tests for ``validate`` — Tier 1 structural errors and Tier 2 business warnings.
uv run --extra dev pytest tests/unit/vessel_valuation/test_validation.py -v
"""

from datetime import date, datetime

import pytest

from tests.unit.vessel_valuation.validation.conftest import BASE_RAW, raw
from vessel_valuation.case_study_benchmarks import load_case_study_pp_teu_benchmarks
from vessel_valuation.schema import ValidationThresholds
from vessel_valuation.validation import validate
from vessel_valuation.validation.business_rules import (
    BUSINESS_RULES,
    TEU_BUCKET_ROUNDING,
    nearest_teu_bucket,
)
from vessel_valuation.validation.structural_rules import STRUCTURAL_RULES


# --- Tier 1 (structural) ---


def test_valid_inputs_produce_no_errors() -> None:
    """Well-formed inputs pass structural validation with no errors."""
    result = validate(BASE_RAW)
    assert result.errors == []
    assert result.inputs is not None


def test_valid_inputs_coerce_to_vessel_inputs() -> None:
    """Valid raw dict coerces to VesselInputs with expected numeric fields."""
    result = validate(BASE_RAW)
    assert result.inputs is not None
    assert result.inputs.purchase_price == 100_000_000.0
    assert result.inputs.vessel_life == 25
    assert result.inputs.teu_size == 10_000


@pytest.mark.parametrize(
    'sentinel',
    ['#VALUE!', '#N/A', '-', '', 'n/a', '#REF!'],
)
def test_sentinel_in_purchase_price_raises_error(sentinel: str) -> None:
    """Excel sentinel strings in purchase_price fail structural validation."""
    result = validate(raw(purchase_price=sentinel))
    assert result.errors
    assert result.inputs is None


def test_sentinel_in_residual_value_raises_error() -> None:
    """Invalid residual sentinel fails structural validation."""
    result = validate(raw(residual_value='#VALUE!'))
    assert result.errors
    assert result.inputs is None


def test_missing_vessel_name_raises_error() -> None:
    """Empty vessel name fails structural validation."""
    result = validate(raw(vessel_name=''))
    assert any('name' in e.lower() for e in result.errors)
    assert result.inputs is None


def test_zero_purchase_price_raises_error() -> None:
    """Zero purchase price fails structural validation."""
    result = validate(raw(purchase_price=0.0))
    assert result.errors
    assert result.inputs is None


def test_vessel_life_zero_raises_error() -> None:
    """Zero vessel life fails structural validation."""
    result = validate(raw(vessel_life=0))
    assert result.errors
    assert result.inputs is None


def test_negative_lw_tonnage_raises_error() -> None:
    """Negative lightweight tonnage fails structural validation."""
    result = validate(raw(lw_tonnage=-1.0))
    assert result.errors
    assert result.inputs is None


def test_offhire_rate_at_or_above_one_raises_error() -> None:
    """Offhire rate at or above 100% fails structural validation."""
    result = validate(raw(offhire_rate=1.0))
    assert result.errors

    result2 = validate(raw(offhire_rate=1.5))
    assert result2.errors


def test_discount_rate_zero_raises_error() -> None:
    """Zero discount rate fails structural validation."""
    result = validate(raw(discount_rate=0.0))
    assert result.errors


def test_days_of_year_not_365_raises_error() -> None:
    """Days-of-year other than 365 fails structural validation."""
    result = validate(raw(days_of_year=360))
    assert result.errors
    assert result.inputs is None


def test_days_of_year_366_raises_error() -> None:
    """366 days per year fails structural validation."""
    result = validate(raw(days_of_year=366))
    assert result.errors


def test_missing_purchase_date_raises_error() -> None:
    """Missing purchase date fails structural validation."""
    result = validate(raw(purchase_date=None))
    assert result.errors
    assert result.inputs is None


def test_purchase_date_as_string_iso_format_accepted() -> None:
    """ISO date string purchase_date coerces to date without errors."""
    result = validate(raw(purchase_date='2025-12-31'))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_purchase_date_as_excel_datetime_accepted() -> None:
    """Excel datetime purchase_date coerces to date without errors."""
    result = validate(raw(purchase_date=datetime(2025, 12, 31)))
    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.purchase_date == date(2025, 12, 31)


def test_missing_residual_value_raises_error() -> None:
    """Missing residual_value fails structural validation."""
    row = {k: v for k, v in BASE_RAW.items() if k != 'residual_value'}
    result = validate(row)
    assert result.errors
    assert result.inputs is None


def test_residual_value_coerced_when_provided() -> None:
    """Explicit residual_value is coerced to float on the VesselInputs instance."""
    result = validate(raw(residual_value=4_000_000.0))
    assert result.inputs is not None
    assert result.inputs.residual_value == pytest.approx(4_000_000.0)


def test_all_structural_rules_have_unique_codes() -> None:
    """Every structural validation rule has a distinct error code."""
    codes = [r.code for r in STRUCTURAL_RULES]
    assert len(codes) == len(set(codes))


# --- Tier 2 (business rules) ---


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


def test_clean_inputs_produce_no_warnings() -> None:
    """Benchmark-consistent base inputs produce no business-rule warnings."""
    result = validate(BASE_RAW)
    assert result.warnings == []


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
