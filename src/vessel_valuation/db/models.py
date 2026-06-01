"""SQLAlchemy ORM models — column names mirror ``schema.py`` dataclass fields."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Declarative base for all ORM tables."""


class RawVesselSubmission(Base):
    """Bronze — append-only raw payload as received."""

    __tablename__ = 'raw_vessel_submissions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_had_errors: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)

    vessel_inputs: Mapped[list['VesselInputRow']] = relationship(back_populates='submission')


class VesselInputRow(Base):
    """Silver — validated ``VesselInputs`` persisted before valuation."""

    __tablename__ = 'vessel_inputs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('raw_vessel_submissions.id'),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    vessel_name: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    vessel_life: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_value: Mapped[float] = mapped_column(Float, nullable=False)
    lw_tonnage: Mapped[float] = mapped_column(Float, nullable=False)
    revenue_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    offhire_rate: Mapped[float] = mapped_column(Float, nullable=False)
    opex_per_day: Mapped[float] = mapped_column(Float, nullable=False)
    drydock_capex: Mapped[float] = mapped_column(Float, nullable=False)
    drydock_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    upgrades_capex: Mapped[float] = mapped_column(Float, nullable=False)
    inflation_rate: Mapped[float] = mapped_column(Float, nullable=False)
    discount_rate: Mapped[float] = mapped_column(Float, nullable=False)
    days_of_year: Mapped[int] = mapped_column(Integer, nullable=False)
    teu_size: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    engine_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    co2_carbon_factor: Mapped[float | None] = mapped_column(Float, nullable=True)

    submission: Mapped[RawVesselSubmission] = relationship(back_populates='vessel_inputs')
    valuations: Mapped[list['VesselValuationRow']] = relationship(back_populates='vessel_input')


class VesselValuationRow(Base):
    """Gold — summary metrics and JSON insight payloads."""

    __tablename__ = 'vessel_valuations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vessel_input_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('vessel_inputs.id'),
        nullable=False,
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    npv: Mapped[float] = mapped_column(Float, nullable=False)
    irr: Mapped[float | None] = mapped_column(Float, nullable=True)
    payback_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    investment_signal: Mapped[str] = mapped_column(String(32), nullable=False)
    breakeven_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sensitivity: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    scenarios: Mapped[dict[str, dict[str, object]] | None] = mapped_column(JSON, nullable=True)

    vessel_input: Mapped[VesselInputRow] = relationship(back_populates='valuations')
    cashflow_years: Mapped[list['VesselCashflowYearRow']] = relationship(
        back_populates='valuation',
        order_by='VesselCashflowYearRow.year',
    )


class VesselCashflowYearRow(Base):
    """Gold — one row per schedule year (vertical growth by ``year``).

    Stored in engine order (year 0, 1, …, T). The calculation-sheet UI pivots
    this to years on the Y-axis and cashflow types on the X-axis in Phase 7.
    """

    __tablename__ = 'vessel_cashflow_years'
    __table_args__ = (UniqueConstraint('valuation_id', 'year', name='uq_valuation_year'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    valuation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('vessel_valuations.id'),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    revenue: Mapped[float] = mapped_column(Float, nullable=False)
    opex: Mapped[float] = mapped_column(Float, nullable=False)
    drydock_capex: Mapped[float] = mapped_column(Float, nullable=False)
    upgrades_capex: Mapped[float] = mapped_column(Float, nullable=False)
    free_cashflow: Mapped[float] = mapped_column(Float, nullable=False)
    net_cashflow: Mapped[float] = mapped_column(Float, nullable=False)
    discounted_cashflow: Mapped[float] = mapped_column(Float, nullable=False)
    cumulative_cashflow: Mapped[float] = mapped_column(Float, nullable=False)

    valuation: Mapped[VesselValuationRow] = relationship(back_populates='cashflow_years')


class VesselBenchmarkRow(Base):
    """Gold — TEU-bucket median purchase prices (self-updating)."""

    __tablename__ = 'vessel_benchmarks'

    teu_bucket: Mapped[int] = mapped_column(Integer, primary_key=True)
    median_price: Mapped[float] = mapped_column(Float, nullable=False)
    vessel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
