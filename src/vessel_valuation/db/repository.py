"""All database reads and writes — maps domain dataclasses ↔ ORM rows."""

import statistics
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload, sessionmaker

from vessel_valuation.db.models import (
    Base,
    RawVesselSubmission,
    VesselBenchmarkRow,
    VesselCashflowYearRow,
    VesselInputRow,
    VesselValuationRow,
)
from vessel_valuation.decision_insights.enrich import enrich
from vessel_valuation.mapping import vessel_inputs_from_object, vessel_inputs_kwargs
from vessel_valuation.schema import (
    CashflowYear,
    ScenarioResult,
    SensitivityPoint,
    ValuationResult,
    VesselInputs,
)
from vessel_valuation.validation import (
    SENTINELS,
    median_pp_teu_factor,
    nearest_teu_bucket,
    validate,
)

# Seed medians for empty DB — matches validation._TEU_PRICE_SEEDS until fleet data exists.
_BENCHMARK_SEEDS: dict[int, float] = {
    7000: 80_000_000.0,
    8000: 90_000_000.0,
    10000: 100_000_000.0,
    12000: 115_000_000.0,
}


@dataclass
class VesselInputSummary:
    """Lightweight row for vessel pick-lists in the UI."""

    id: int
    vessel_name: str
    teu_size: int
    purchase_price: float
    purchase_date: date
    created_at: datetime


@dataclass
class PersistedVessel:
    """IDs and enriched result after a full persist pipeline."""

    submission_id: int
    vessel_input_id: int
    valuation_id: int
    result: ValuationResult


def init_schema(engine: Engine) -> None:
    """Create all tables (tests and local bootstrap without Alembic)."""
    Base.metadata.create_all(engine)
    seed_benchmarks_if_empty(engine)


def seed_benchmarks_if_empty(engine: Engine) -> None:
    """Insert seed TEU benchmarks when the table has no rows."""
    with Session(engine) as session:
        if session.scalar(select(VesselBenchmarkRow.teu_bucket).limit(1)) is not None:
            return
        now = datetime.now(UTC)
        for teu_bucket, median_price in _BENCHMARK_SEEDS.items():
            session.add(
                VesselBenchmarkRow(
                    teu_bucket=teu_bucket,
                    median_price=median_price,
                    vessel_count=0,
                    last_updated=now,
                )
            )
        session.commit()


def payload_had_sentinels(payload: Mapping[str, object]) -> bool:
    """Return True if any value in the raw payload is an Excel-style sentinel."""
    for value in payload.values():
        if _value_is_sentinel(value):
            return True
    return False


def _value_is_sentinel(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in SENTINELS:
        return True
    if isinstance(value, Mapping):
        return any(_value_is_sentinel(v) for v in value.values())
    if isinstance(value, list):
        return any(_value_is_sentinel(v) for v in value)
    return False


def save_raw_submission(
    session: Session,
    raw_payload: dict[str, object],
    source: str,
    filename: str | None = None,
) -> int:
    """Persist a bronze raw submission; return its id."""
    row = RawVesselSubmission(
        submitted_at=datetime.now(UTC),
        source=source,
        filename=filename,
        raw_had_errors=payload_had_sentinels(raw_payload),
        raw_payload=raw_payload,
    )
    session.add(row)
    session.flush()
    return row.id


def save_vessel_inputs(session: Session, submission_id: int, inputs: VesselInputs) -> int:
    """Persist silver ``vessel_inputs``; return its id."""
    row = VesselInputRow(
        submission_id=submission_id,
        created_at=datetime.now(UTC),
        **vessel_inputs_kwargs(inputs),  # type: ignore[arg-type]
    )
    session.add(row)
    session.flush()
    return row.id


def save_valuation(session: Session, vessel_input_id: int, result: ValuationResult) -> int:
    """Persist gold valuation summary and cashflow rows; return valuation id."""
    sensitivity_json = [
        {'revenue_per_day': p.revenue_per_day, 'irr': p.irr} for p in result.sensitivity
    ]
    scenarios_json = {
        name: {
            'npv': s.npv,
            'irr': s.irr,
            'investment_signal': s.investment_signal,
        }
        for name, s in result.scenarios.items()
    }
    row = VesselValuationRow(
        vessel_input_id=vessel_input_id,
        computed_at=datetime.now(UTC),
        npv=result.npv,
        irr=result.irr,
        payback_year=result.payback_year,
        investment_signal=result.investment_signal,
        breakeven_rate=result.breakeven_rate,
        sensitivity=sensitivity_json,
        scenarios=scenarios_json,
    )
    session.add(row)
    session.flush()
    save_cashflow_years(session, row.id, result.schedule)
    return row.id


def save_cashflow_years(
    session: Session,
    valuation_id: int,
    schedule: list[CashflowYear],
) -> None:
    """Persist one relational row per schedule year."""
    for year_row in schedule:
        session.add(
            VesselCashflowYearRow(
                valuation_id=valuation_id,
                year=year_row.year,
                period_end=year_row.period_end,
                revenue=year_row.revenue,
                opex=year_row.opex,
                drydock_capex=year_row.drydock_capex,
                upgrades_capex=year_row.upgrades_capex,
                free_cashflow=year_row.free_cashflow,
                net_cashflow=year_row.net_cashflow,
                discounted_cashflow=year_row.discounted_cashflow,
                cumulative_cashflow=year_row.cumulative_cashflow,
            )
        )


def vessel_input_identity_key(
    vessel_name: str,
    purchase_date: date,
    teu_size: int,
) -> tuple[str, date, int]:
    """Build normalized fleet identity for duplicate detection (name, date, TEU)."""
    return (vessel_name.strip().casefold(), purchase_date, teu_size)


def find_vessel_input_id_by_identity(session: Session, inputs: VesselInputs) -> int | None:
    """Return silver row id when the same vessel identity is already saved."""
    target = vessel_input_identity_key(
        inputs.vessel_name,
        inputs.purchase_date,
        inputs.teu_size,
    )
    for row in session.scalars(select(VesselInputRow)).all():
        row_key = vessel_input_identity_key(row.vessel_name, row.purchase_date, row.teu_size)
        if row_key == target:
            return row.id
    return None


def get_vessel_inputs(session: Session, vessel_input_id: int) -> VesselInputs | None:
    """Load a silver ``VesselInputs`` by id."""
    row = session.get(VesselInputRow, vessel_input_id)
    if row is None:
        return None
    return _row_to_vessel_inputs(row)


def get_valuation(session: Session, vessel_input_id: int) -> ValuationResult | None:
    """Load the latest enriched valuation for a vessel input, schedule ordered by year."""
    stmt = (
        select(VesselValuationRow)
        .options(selectinload(VesselValuationRow.cashflow_years))
        .where(VesselValuationRow.vessel_input_id == vessel_input_id)
        .order_by(VesselValuationRow.computed_at.desc())
        .limit(1)
    )
    valuation = session.scalar(stmt)
    if valuation is None:
        return None
    return _valuation_row_to_result(valuation)


def get_valuation_by_id(session: Session, valuation_id: int) -> ValuationResult | None:
    """Load a valuation by its gold-row id."""
    stmt = (
        select(VesselValuationRow)
        .options(selectinload(VesselValuationRow.cashflow_years))
        .where(VesselValuationRow.id == valuation_id)
    )
    valuation = session.scalar(stmt)
    if valuation is None:
        return None
    return _valuation_row_to_result(valuation)


def list_fleet_vessel_inputs(session: Session) -> list[VesselInputs]:
    """Return all saved silver vessels as domain inputs (for upload Tier 2 peers)."""
    rows = session.scalars(select(VesselInputRow)).all()
    return [_row_to_vessel_inputs(row) for row in rows]


def list_vessels(session: Session) -> list[VesselInputSummary]:
    """Return silver vessel rows newest-first for pick-lists."""
    stmt = select(VesselInputRow).order_by(VesselInputRow.created_at.desc())
    rows = session.scalars(stmt).all()
    return [
        VesselInputSummary(
            id=row.id,
            vessel_name=row.vessel_name,
            teu_size=row.teu_size,
            purchase_price=row.purchase_price,
            purchase_date=row.purchase_date,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _delete_vessel_input_core(session: Session, vessel_input_id: int) -> bool:
    """Remove one silver row and its gold rows without refreshing benchmarks."""
    row = session.get(VesselInputRow, vessel_input_id)
    if row is None:
        return False

    submission_id = row.submission_id
    valuation_ids = list(
        session.scalars(
            select(VesselValuationRow.id).where(
                VesselValuationRow.vessel_input_id == vessel_input_id
            )
        ).all()
    )
    if valuation_ids:
        session.execute(
            delete(VesselCashflowYearRow).where(
                VesselCashflowYearRow.valuation_id.in_(valuation_ids)
            )
        )
        session.execute(
            delete(VesselValuationRow).where(VesselValuationRow.vessel_input_id == vessel_input_id)
        )

    session.delete(row)
    session.flush()

    remaining_for_submission = session.scalar(
        select(func.count())
        .select_from(VesselInputRow)
        .where(VesselInputRow.submission_id == submission_id)
    )
    if remaining_for_submission == 0:
        submission = session.get(RawVesselSubmission, submission_id)
        if submission is not None:
            session.delete(submission)

    return True


def delete_vessel_input(session: Session, vessel_input_id: int) -> bool:
    """Delete one saved vessel and its gold rows; refresh TEU benchmarks."""
    if not _delete_vessel_input_core(session, vessel_input_id):
        return False
    refresh_benchmarks(session)
    return True


def delete_vessel_inputs(session: Session, vessel_input_ids: list[int]) -> int:
    """Delete multiple saved vessels; refresh TEU benchmarks once if any were removed."""
    deleted = 0
    seen: set[int] = set()
    for vessel_input_id in vessel_input_ids:
        if vessel_input_id in seen:
            continue
        seen.add(vessel_input_id)
        if _delete_vessel_input_core(session, vessel_input_id):
            deleted += 1
    if deleted:
        refresh_benchmarks(session)
    return deleted


def load_pp_teu_factor_benchmarks(session: Session) -> dict[int, float]:
    """Return exact TEU → median PP/TEU factor from the saved fleet (2+ vessels per TEU)."""
    fleet_rows = session.scalars(select(VesselInputRow)).all()
    inputs = [_row_to_vessel_inputs(row) for row in fleet_rows]
    return median_pp_teu_factor(inputs)


def lookup_purchase_price_benchmark(session: Session, teu: int) -> float | None:
    """Return interpolated median purchase price for ``teu``, or None if insufficient data."""
    gold_rows = session.scalars(select(VesselBenchmarkRow)).all()
    if gold_rows:
        medians = {row.teu_bucket: row.median_price for row in gold_rows}
    else:
        medians = dict(_BENCHMARK_SEEDS)

    bucket = nearest_teu_bucket(teu)
    if bucket in medians:
        return medians[bucket]

    sorted_buckets = sorted(medians)
    lower = [b for b in sorted_buckets if b < bucket]
    upper = [b for b in sorted_buckets if b > bucket]
    if not lower or not upper:
        return None

    lo_bucket = lower[-1]
    hi_bucket = upper[0]
    lo_price = medians[lo_bucket]
    hi_price = medians[hi_bucket]
    if hi_bucket == lo_bucket:
        return lo_price
    weight = (bucket - lo_bucket) / (hi_bucket - lo_bucket)
    return lo_price + weight * (hi_price - lo_price)


def refresh_benchmarks(session: Session) -> None:
    """Recompute ``vessel_benchmarks`` medians from all silver inputs."""
    rows = session.scalars(select(VesselInputRow)).all()
    buckets: defaultdict[int, list[float]] = defaultdict(list)
    for row in rows:
        buckets[nearest_teu_bucket(row.teu_size)].append(row.purchase_price)

    now = datetime.now(UTC)
    existing_rows = list(session.scalars(select(VesselBenchmarkRow)).all())
    active_buckets = set(buckets)

    for teu_bucket, prices in buckets.items():
        median_price = statistics.median(prices)
        existing = session.get(VesselBenchmarkRow, teu_bucket)
        if existing is None:
            session.add(
                VesselBenchmarkRow(
                    teu_bucket=teu_bucket,
                    median_price=median_price,
                    vessel_count=len(prices),
                    last_updated=now,
                )
            )
        else:
            existing.median_price = median_price
            existing.vessel_count = len(prices)
            existing.last_updated = now

    for row in existing_rows:
        if row.teu_bucket not in active_buckets:
            session.delete(row)


def persist_vessel_submission(
    session: Session,
    raw_payload: dict[str, object],
    source: str,
    filename: str | None = None,
    pp_teu_factor_benchmarks: dict[int, float] | None = None,
    rev_min: float | None = None,
    rev_max: float | None = None,
) -> PersistedVessel:
    """Run full pipeline: raw → validate → silver → enrich → gold → refresh benchmarks.

    Silver ``vessel_inputs`` is written before NPV/IRR so prior entries are
    addressable even if enrichment fails.
    """
    if pp_teu_factor_benchmarks is None:
        pp_teu_factor_benchmarks = load_pp_teu_factor_benchmarks(session)

    submission_id = save_raw_submission(session, raw_payload, source, filename)
    validation = validate(raw_payload, pp_teu_factor_benchmarks=pp_teu_factor_benchmarks)
    if validation.inputs is None:
        msg = '; '.join(validation.errors) if validation.errors else 'validation failed'
        raise ValueError(msg)

    inputs = validation.inputs
    existing_id = find_vessel_input_id_by_identity(session, inputs)
    if existing_id is not None:
        raise ValueError(
            f'Vessel already saved as entry #{existing_id} '
            f'({inputs.vessel_name}, {inputs.teu_size:,} TEU, '
            f'{inputs.purchase_date.isoformat()}). '
            'Load that entry or change name, TEU, or purchase date.'
        )

    vessel_input_id = save_vessel_inputs(session, submission_id, inputs)
    result = enrich(inputs, rev_min=rev_min, rev_max=rev_max)
    valuation_id = save_valuation(session, vessel_input_id, result)
    refresh_benchmarks(session)
    session.flush()
    return PersistedVessel(
        submission_id=submission_id,
        vessel_input_id=vessel_input_id,
        valuation_id=valuation_id,
        result=result,
    )


def create_test_session_factory() -> sessionmaker[Session]:
    """In-memory SQLite engine and session factory for integration tests."""
    from vessel_valuation.db.connection import create_db_engine, create_session_factory

    engine = create_db_engine('sqlite://', for_tests=True)
    init_schema(engine)
    return create_session_factory(engine)


def _json_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError('expected numeric JSON value')


def _sensitivity_from_json(
    payload: list[dict[str, object]] | None,
) -> list[SensitivityPoint]:
    if not payload:
        return []
    points: list[SensitivityPoint] = []
    for point in payload:
        irr_raw = point.get('irr')
        irr = _json_float(irr_raw) if irr_raw is not None else None
        points.append(
            SensitivityPoint(
                revenue_per_day=_json_float(point['revenue_per_day']),
                irr=irr,
            )
        )
    return points


def _scenarios_from_json(
    payload: dict[str, dict[str, object]] | None,
) -> dict[str, ScenarioResult]:
    if not payload:
        return {}
    return {
        name: ScenarioResult(
            npv=_json_float(data['npv']),
            irr=_json_float(data['irr']) if data['irr'] is not None else None,
            investment_signal=str(data['investment_signal']),
        )
        for name, data in payload.items()
    }


def _row_to_vessel_inputs(row: VesselInputRow) -> VesselInputs:
    return vessel_inputs_from_object(row)


def _valuation_row_to_result(valuation: VesselValuationRow) -> ValuationResult:
    schedule = [
        CashflowYear(
            year=row.year,
            period_end=row.period_end,
            revenue=row.revenue,
            opex=row.opex,
            drydock_capex=row.drydock_capex,
            upgrades_capex=row.upgrades_capex,
            free_cashflow=row.free_cashflow,
            net_cashflow=row.net_cashflow,
            discounted_cashflow=row.discounted_cashflow,
            cumulative_cashflow=row.cumulative_cashflow,
        )
        for row in valuation.cashflow_years
    ]
    sensitivity = _sensitivity_from_json(valuation.sensitivity)
    scenarios = _scenarios_from_json(valuation.scenarios)
    return ValuationResult(
        npv=valuation.npv,
        irr=valuation.irr,
        schedule=schedule,
        payback_year=valuation.payback_year,
        investment_signal=valuation.investment_signal,
        breakeven_rate=valuation.breakeven_rate,
        sensitivity=sensitivity,
        scenarios=scenarios,
    )
