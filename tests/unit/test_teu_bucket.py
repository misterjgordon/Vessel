"""TEU bucket rounding for Tier 2 benchmarks."""

from vessel_valuation.validation import TEU_BUCKET_ROUNDING, nearest_teu_bucket


def test_teu_bucket_rounding_step_is_1000() -> None:
    """Fleet benchmarks group TEU sizes in 1,000-TEU steps."""
    assert TEU_BUCKET_ROUNDING == 1000


def test_nearest_teu_bucket_rounds_to_nearest_1000() -> None:
    """Case-study-sized vessels map to the expected benchmark bucket."""
    assert nearest_teu_bucket(7_460) == 7_000
    assert nearest_teu_bucket(10_400) == 10_000
    assert nearest_teu_bucket(10_600) == 11_000
