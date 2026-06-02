"""
Repository integration tests — SQLite in-memory round-trips.

uv run --extra dev pytest tests/integration/vessel_valuation/db/test_repository.py -v
"""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.conftest import CASE_STUDY_XLSX
from vessel_valuation.db.models import (
    RawVesselSubmission,
    VesselBenchmarkRow,
    VesselCashflowYearRow,
    VesselInputRow,
    VesselValuationRow,
)
from vessel_valuation.db.repository import (
    delete_vessel_input,
    delete_vessel_inputs,
    get_valuation,
    get_vessel_inputs,
    list_vessels,
    load_pp_teu_factor_benchmarks,
    lookup_purchase_price_benchmark,
    persist_vessel_submission,
    refresh_benchmarks,
    save_raw_submission,
    save_vessel_inputs,
    save_valuation,
)
from vessel_valuation.decision_insights.enrich import enrich
from vessel_valuation.excel_reference import load_sample_vessels
from vessel_valuation.file_parser import parse_dataframe
from vessel_valuation.validation import validate

_NEW_8000_TEU_PURCHASE_DATE = '2026-01-15'
_OTHER_8000_TEU_PURCHASE_DATE = '2026-02-01'

RAW_PAYLOAD = {
    'vessel_name': 'Integration Test',
    'purchase_price': 100_000_000.0,
    'vessel_life': 25,
    'residual_value': 5_000_000.0,
    'lw_tonnage': 12_500.0,
    'revenue_per_day': 50_000.0,
    'offhire_rate': 0.02,
    'opex_per_day': 10_000.0,
    'drydock_capex': 5_000_000.0,
    'drydock_frequency': 5,
    'upgrades_capex': 500_000.0,
    'inflation_rate': 0.03,
    'discount_rate': 0.10,
    'days_of_year': 365,
    'teu_size': 10_000,
    'purchase_date': '2025-12-31',
}


def _case_study_sample_raw(name_part: str, workbook: Path = CASE_STUDY_XLSX) -> dict[str, object]:
    """Return the normalized raw dict for a Sample Data row matching ``name_part``."""
    df = load_sample_vessels(workbook)
    result = parse_dataframe(df, source_name='sample_data')
    for row in result.rows:
        vessel_name = str(row.raw.get('vessel_name', ''))
        if name_part in vessel_name:
            return dict(row.raw)
    raise AssertionError(f'no sample row matching {name_part!r}')


def _new_8000_teu_from_sample_nine() -> dict[str, object]:
    """Build a third 8,000 TEU vessel payload aligned with sample #9 pricing."""
    raw = _case_study_sample_raw('#9')
    raw['vessel_name'] = 'New 8000 TEU Vessel'
    raw['purchase_date'] = _NEW_8000_TEU_PURCHASE_DATE
    return raw


def test_persist_full_pipeline_round_trip(db_session: Session) -> None:
    """Full persist stores silver before gold and reloads an enriched valuation."""
    persisted = persist_vessel_submission(
        db_session,
        RAW_PAYLOAD,
        source='manual_form',
    )
    db_session.commit()

    reloaded_inputs = get_vessel_inputs(db_session, persisted.vessel_input_id)
    assert reloaded_inputs is not None
    assert reloaded_inputs.vessel_name == 'Integration Test'

    reloaded = get_valuation(db_session, persisted.vessel_input_id)
    assert reloaded is not None
    assert reloaded.npv == pytest.approx(persisted.result.npv, rel=1e-9)
    assert len(reloaded.schedule) == len(persisted.result.schedule)
    assert reloaded.breakeven_rate is not None
    assert len(reloaded.sensitivity) == 11
    assert set(reloaded.scenarios.keys()) == {'Best', 'Base', 'Worst'}


def test_silver_row_exists_before_valuation_on_manual_save(db_session: Session) -> None:
    """Silver vessel_inputs row is written before valuation rows are created."""
    validation = validate(RAW_PAYLOAD)
    assert validation.inputs is not None

    submission_id = save_raw_submission(db_session, RAW_PAYLOAD, 'manual_form')
    vessel_input_id = save_vessel_inputs(db_session, submission_id, validation.inputs)
    db_session.flush()

    input_row = db_session.get(VesselInputRow, vessel_input_id)
    assert input_row is not None
    assert db_session.scalar(select(VesselValuationRow.id).limit(1)) is None

    result = enrich(validation.inputs)
    save_valuation(db_session, vessel_input_id, result)
    db_session.commit()

    assert get_valuation(db_session, vessel_input_id) is not None


def test_cashflow_years_stored_vertically_by_year(db_session: Session) -> None:
    """Cashflow rows grow vertically (one row per year), ordered 0..T for reload."""
    persisted = persist_vessel_submission(db_session, RAW_PAYLOAD, source='file_upload')
    db_session.commit()

    rows = db_session.scalars(
        select(VesselCashflowYearRow)
        .where(VesselCashflowYearRow.valuation_id == persisted.valuation_id)
        .order_by(VesselCashflowYearRow.year)
    ).all()
    years = [row.year for row in rows]
    assert years == list(range(0, 26))
    assert rows[0].revenue == pytest.approx(persisted.result.schedule[0].revenue)
    assert rows[-1].net_cashflow == pytest.approx(persisted.result.schedule[-1].net_cashflow)

    reloaded = get_valuation(db_session, persisted.vessel_input_id)
    assert reloaded is not None
    assert [row.year for row in reloaded.schedule] == years


def test_raw_had_errors_flags_sentinel_payload(db_session: Session) -> None:
    """Bronze raw_had_errors is true when the payload contains Excel sentinels."""
    dirty = dict(RAW_PAYLOAD)
    dirty['purchase_price'] = '#VALUE!'
    submission_id = save_raw_submission(db_session, dirty, 'file_upload', filename='bad.xlsx')
    db_session.commit()

    raw = db_session.get(RawVesselSubmission, submission_id)
    assert raw is not None
    assert raw.raw_had_errors is True


def test_list_vessels_returns_saved_entries(db_session: Session) -> None:
    """list_vessels returns id, name, TEU, price, and purchase date for pick-lists."""
    persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')
    db_session.commit()

    vessels = list_vessels(db_session)
    assert len(vessels) == 1
    summary = vessels[0]
    assert summary.vessel_name == 'Integration Test'
    assert summary.teu_size == 10_000
    assert summary.purchase_price == 100_000_000.0
    assert summary.purchase_date == date(2025, 12, 31)


def test_refresh_benchmarks_updates_from_fleet(db_session: Session) -> None:
    """Saving vessels refreshes TEU-bucket medians from fleet data."""
    persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')
    db_session.commit()
    refresh_benchmarks(db_session)
    db_session.commit()

    row = db_session.get(VesselBenchmarkRow, 10_000)
    assert row is not None
    assert row.median_price == pytest.approx(100_000_000.0)


def test_lookup_purchase_price_benchmark_interpolates(db_session: Session) -> None:
    """Benchmark lookup linearly interpolates between adjacent TEU buckets."""
    # 9,200 TEU → bucket 9,000 (no seed row); price falls between 8k and 10k TEU medians.
    price = lookup_purchase_price_benchmark(db_session, 9_200)
    assert price is not None
    assert 90_000_000.0 < price < 100_000_000.0


def test_lookup_returns_none_with_insufficient_buckets(db_session: Session) -> None:
    """Benchmark lookup returns None when only one neighbour bucket exists."""
    price = lookup_purchase_price_benchmark(db_session, 50_000)
    assert price is None


def test_delete_vessel_input_removes_gold_and_silver(db_session: Session) -> None:
    """delete_vessel_input removes valuations, cashflows, and the silver row."""
    persisted = persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')
    db_session.commit()
    vessel_input_id = persisted.vessel_input_id

    assert delete_vessel_input(db_session, vessel_input_id) is True
    db_session.commit()

    assert get_vessel_inputs(db_session, vessel_input_id) is None
    assert get_valuation(db_session, vessel_input_id) is None
    assert list_vessels(db_session) == []


def test_delete_vessel_input_returns_false_when_missing(db_session: Session) -> None:
    """delete_vessel_input returns False when the silver id does not exist."""
    assert delete_vessel_input(db_session, 999_999) is False


def test_delete_vessel_inputs_removes_multiple_rows(db_session: Session) -> None:
    """delete_vessel_inputs removes each selected silver row in one transaction."""
    first = persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')
    second_payload = dict(RAW_PAYLOAD)
    second_payload['vessel_name'] = 'Second Vessel'
    second = persist_vessel_submission(db_session, second_payload, source='manual_form')
    db_session.commit()

    deleted_count = delete_vessel_inputs(
        db_session,
        [first.vessel_input_id, second.vessel_input_id],
    )
    db_session.commit()

    assert deleted_count == 2
    assert list_vessels(db_session) == []


def test_delete_one_of_two_preserves_other(db_session: Session) -> None:
    """Deleting one entry leaves other saved vessels and refreshes benchmarks."""
    first = persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')
    second_payload = dict(RAW_PAYLOAD)
    second_payload['vessel_name'] = 'Second Vessel'
    second = persist_vessel_submission(db_session, second_payload, source='manual_form')
    db_session.commit()

    assert delete_vessel_input(db_session, first.vessel_input_id) is True
    db_session.commit()

    remaining = list_vessels(db_session)
    assert len(remaining) == 1
    assert remaining[0].id == second.vessel_input_id
    assert get_vessel_inputs(db_session, first.vessel_input_id) is None
    assert get_vessel_inputs(db_session, second.vessel_input_id) is not None


def test_persist_rejects_duplicate_vessel_identity(db_session: Session) -> None:
    """Second save with the same name, TEU, and purchase date is rejected."""
    first = persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')
    db_session.commit()

    with pytest.raises(ValueError, match='already saved'):
        persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')

    assert list_vessels(db_session)[0].id == first.vessel_input_id


def test_persist_allows_same_name_different_teu_size(db_session: Session) -> None:
    """Same vessel name with different TEU size is treated as a distinct entry."""
    persist_vessel_submission(db_session, RAW_PAYLOAD, source='manual_form')
    other = dict(RAW_PAYLOAD)
    other['teu_size'] = 8_000
    persisted = persist_vessel_submission(db_session, other, source='manual_form')
    db_session.commit()

    assert len(list_vessels(db_session)) == 2
    assert persisted.vessel_input_id is not None


def test_persist_rejects_invalid_payload(db_session: Session) -> None:
    """Invalid raw payload raises after bronze save without creating silver."""
    bad = dict(RAW_PAYLOAD)
    bad['days_of_year'] = 360
    with pytest.raises(ValueError):
        persist_vessel_submission(db_session, bad, source='manual_form')

    assert db_session.scalar(select(VesselInputRow).limit(1)) is None


def test_load_pp_teu_factor_benchmarks_median_for_mixed_8000_teu_fleet(db_session: Session) -> None:
    """8,000 TEU fleet with $9M and $90M prices uses the median PP/TEU factor ($11,250/TEU)."""
    low = dict(RAW_PAYLOAD)
    low['teu_size'] = 8_000
    low['purchase_price'] = 9_000_000.0
    low['vessel_name'] = 'Low 8000'
    high = dict(RAW_PAYLOAD)
    high['teu_size'] = 8_000
    high['purchase_price'] = 90_000_000.0
    high['vessel_name'] = 'High 8000 A'
    high['purchase_date'] = '2026-02-01'
    high_b = dict(high)
    high_b['vessel_name'] = 'High 8000 B'
    high_b['purchase_date'] = '2026-03-01'
    persist_vessel_submission(db_session, low, source='manual_form')
    persist_vessel_submission(db_session, high, source='manual_form')
    persist_vessel_submission(db_session, high_b, source='manual_form')
    db_session.commit()

    assert load_pp_teu_factor_benchmarks(db_session)[8_000] == pytest.approx(11_250.0)


def test_sample_vessels_9_and_10_set_8000_teu_pp_teu_factor_benchmark(db_session: Session) -> None:
    """Persisting sample #9 and #10 sets the 8,000 TEU fleet PP/TEU factor to $11,250/TEU."""
    persist_vessel_submission(db_session, _case_study_sample_raw('#9'), source='file_upload')
    persist_vessel_submission(db_session, _case_study_sample_raw('#10'), source='file_upload')
    db_session.commit()

    benchmarks = load_pp_teu_factor_benchmarks(db_session)
    assert benchmarks[8_000] == pytest.approx(11_250.0)


def test_new_8000_teu_vessel_at_fleet_pp_teu_factor_has_no_warning(
    db_session: Session,
) -> None:
    """A new 8,000 TEU vessel at $90M does not warn when the fleet is sample #9 and #10 only."""
    persist_vessel_submission(db_session, _case_study_sample_raw('#9'), source='file_upload')
    persist_vessel_submission(db_session, _case_study_sample_raw('#10'), source='file_upload')
    db_session.commit()

    new_raw = _new_8000_teu_from_sample_nine()
    benchmarks = load_pp_teu_factor_benchmarks(db_session)
    result = validate(new_raw, pp_teu_factor_benchmarks=benchmarks)

    assert result.errors == []
    assert result.inputs is not None
    assert result.inputs.teu_size == 8_000
    assert result.inputs.purchase_price == pytest.approx(90_000_000.0)
    assert not any('Purchase-price÷TEU ratio' in w for w in result.warnings)


def test_deleting_all_8000_teu_vessels_clears_stale_benchmark_row(
    db_session: Session,
) -> None:
    """Removing all 8,000 TEU rows must not leave a stale median that warns peers at $90M."""
    low = dict(RAW_PAYLOAD)
    low['teu_size'] = 8_000
    low['purchase_price'] = 50_000_000.0
    low['vessel_name'] = 'Low 8000 TEU'

    high = dict(RAW_PAYLOAD)
    high['teu_size'] = 8_000
    high['purchase_price'] = 60_000_000.0
    high['vessel_name'] = 'High 8000 TEU'
    high['purchase_date'] = _OTHER_8000_TEU_PURCHASE_DATE

    first = persist_vessel_submission(db_session, low, source='manual_form')
    second = persist_vessel_submission(db_session, high, source='manual_form')
    db_session.commit()
    assert load_pp_teu_factor_benchmarks(db_session)[8_000] == pytest.approx(6_875.0)

    delete_vessel_inputs(
        db_session,
        [first.vessel_input_id, second.vessel_input_id],
    )
    db_session.commit()

    assert db_session.get(VesselBenchmarkRow, 8_000) is None

    new_raw = _new_8000_teu_from_sample_nine()
    result = validate(new_raw, pp_teu_factor_benchmarks=load_pp_teu_factor_benchmarks(db_session))
    assert not any('Purchase-price÷TEU ratio' in w for w in result.warnings)


def test_persisting_sample_9_and_10_sets_fleet_pp_teu_factor_benchmark(
    db_session: Session,
) -> None:
    """Saving sample #9 and #10 sets the fleet PP/TEU factor benchmark for 8,000 TEU."""
    low = dict(RAW_PAYLOAD)
    low['teu_size'] = 8_000
    low['purchase_price'] = 50_000_000.0
    low['vessel_name'] = 'Low 8000 TEU'

    high = dict(RAW_PAYLOAD)
    high['teu_size'] = 8_000
    high['purchase_price'] = 60_000_000.0
    high['vessel_name'] = 'High 8000 TEU'
    high['purchase_date'] = _OTHER_8000_TEU_PURCHASE_DATE

    first = persist_vessel_submission(db_session, low, source='manual_form')
    second = persist_vessel_submission(db_session, high, source='manual_form')
    db_session.commit()
    delete_vessel_inputs(
        db_session,
        [first.vessel_input_id, second.vessel_input_id],
    )
    db_session.commit()
    assert db_session.get(VesselBenchmarkRow, 8_000) is None

    persist_vessel_submission(db_session, _case_study_sample_raw('#9'), source='file_upload')
    persist_vessel_submission(db_session, _case_study_sample_raw('#10'), source='file_upload')
    db_session.commit()

    benchmarks = load_pp_teu_factor_benchmarks(db_session)
    assert benchmarks[8_000] == pytest.approx(11_250.0)

    result = validate(_new_8000_teu_from_sample_nine(), pp_teu_factor_benchmarks=benchmarks)
    assert not any('Purchase-price÷TEU ratio' in w for w in result.warnings)


def test_validate_55m_8000_teu_warns_against_three_vessel_fleet(db_session: Session) -> None:
    """$55M at 8,000 TEU warns against a fleet whose median PP/TEU factor is $11,250/TEU."""
    low = dict(RAW_PAYLOAD)
    low['teu_size'] = 8_000
    low['purchase_price'] = 9_000_000.0
    low['vessel_name'] = 'Sample Vessle #8'
    low['purchase_date'] = '2025-03-31'
    nine = _case_study_sample_raw('#9')
    ten = _case_study_sample_raw('#10')
    persist_vessel_submission(db_session, low, source='manual_form')
    persist_vessel_submission(db_session, nine, source='file_upload')
    persist_vessel_submission(db_session, ten, source='file_upload')
    db_session.commit()

    new_raw = _new_8000_teu_from_sample_nine()
    new_raw['vessel_name'] = 'test vessle #12'
    new_raw['purchase_price'] = 55_000_000.0
    benchmarks = load_pp_teu_factor_benchmarks(db_session)
    result = validate(new_raw, pp_teu_factor_benchmarks=benchmarks)
    assert any('Purchase-price÷TEU ratio' in w for w in result.warnings)
