"""Shared validation types — rule dataclasses and the combined result shape."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vessel_valuation.schema import ValidationThresholds
    from vessel_valuation.schema import VesselInputs

SENTINELS: frozenset[str] = frozenset(
    {'#value!', '#n/a', '#ref!', '#div/0!', '#null!', 'n/a', '-', ''}
)


@dataclass
class RawRule:
    """Structural rule — operates on the raw input dict before type coercion."""

    code: str
    message: str
    check: Callable[[dict[str, object]], bool]


@dataclass
class RuleContext:
    """Injected context for business rules that need benchmarks or thresholds."""

    pp_teu_factor_benchmarks: dict[int, float]
    thresholds: ValidationThresholds


@dataclass
class BusinessRule:
    """One business-rule catalog entry — stable id, name, and warning evaluator."""

    code: str
    name: str
    warn: Callable[[VesselInputs, RuleContext], str | None]


@dataclass
class ValidationResult:
    """Outcome of running structural then business-rule validation on one record."""

    errors: list[str]
    warnings: list[str]
    inputs: VesselInputs | None
