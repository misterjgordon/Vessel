"""Input validation — structural checks then business-rule advisories.

Two-stage flow::

    raw dict  →  structural rules  →  VesselInputs  →  business rules
                    (errors)                            (warnings)

Structural validation collects type and presence errors that prevent
computation. Business rules produce advisory warnings the user may override.
"""

from vessel_valuation.schema import ValidationThresholds
from vessel_valuation.validation.business_rules import (
    TEU_BUCKET_ROUNDING as TEU_BUCKET_ROUNDING,
    business_rule_warnings,
    format_pp_teu_ratio as format_pp_teu_ratio,
    median_pp_teu_factor as median_pp_teu_factor,
    nearest_teu_bucket as nearest_teu_bucket,
    pp_teu_factor as pp_teu_factor,
    vessel_inputs_identity as vessel_inputs_identity,
)
from vessel_valuation.validation.coercion import coerce_inputs
from vessel_valuation.validation.structural_rules import STRUCTURAL_RULES
from vessel_valuation.validation.types import (
    BusinessRule as BusinessRule,
    RawRule as RawRule,
    RuleContext as RuleContext,
    SENTINELS as SENTINELS,
    ValidationResult,
)


def validate(
    raw: dict[str, object],
    pp_teu_factor_benchmarks: dict[int, float] | None = None,
    thresholds: ValidationThresholds | None = None,
) -> ValidationResult:
    """Run structural then business-rule validation against one raw vessel record.

    Parameters
    ----------
    raw
        Dict with keys matching ``VesselInputs`` field names. Produced by
        the manual form or ``file_parser`` before any coercion.
    pp_teu_factor_benchmarks
        Exact TEU → median PP÷TEU from saved fleet (2+ peers). Case-study
        defaults apply when the database has no peer median for that TEU.
    thresholds
        TEU benchmark warning bands. Uses ``DEFAULT_VALIDATION_THRESHOLDS``
        when None.

    Returns
    -------
    ValidationResult
        errors: structural failures (``inputs`` is None if non-empty).
        warnings: business-rule advisories (``inputs`` populated when structural passed).
        inputs: typed ``VesselInputs`` if structural validation passed, else None.
    """
    errors: list[str] = [rule.message for rule in STRUCTURAL_RULES if not rule.check(raw)]

    if errors:
        empty_warnings: list[str] = []
        return ValidationResult(errors=errors, warnings=empty_warnings, inputs=None)

    inputs = coerce_inputs(raw)
    warnings = business_rule_warnings(inputs, pp_teu_factor_benchmarks, thresholds)

    empty_errors: list[str] = []
    return ValidationResult(errors=empty_errors, warnings=warnings, inputs=inputs)


# Backward-compatible alias used by file_parser two-pass upload flow.
tier2_warnings = business_rule_warnings
