"""Parse and validate user-edited Best / Base / Worst scenario rate bundles."""

from vessel_valuation.decision_insights.scenario_analysis import DEFAULT_SCENARIO_BUNDLES
from vessel_valuation.schema import ScenarioBundle
from vessel_valuation.serialize import json_float

SCENARIO_NAMES: tuple[str, ...] = ('Best', 'Base', 'Worst')


def scenario_bundle_warnings(bundles: list[ScenarioBundle]) -> list[str]:
    """Tier 2 warnings for macro pairs that break the default Fisher spread (D-010)."""
    warnings: list[str] = []
    spreads = [bundle.discount_rate - bundle.inflation_rate for bundle in bundles]
    if any(spread < 0 for spread in spreads):
        warnings.append(
            'Discount rate should exceed inflation rate in each scenario '
            '(nominal hurdle vs cost escalation).'
        )
    rounded = {round(spread, 4) for spread in spreads}
    if len(rounded) > 1:
        warnings.append(
            'Real required return (discount minus inflation) differs across scenarios; '
            'default bundles keep a constant 2% spread.'
        )
    return warnings


def _parse_rate(value: object, label: str) -> tuple[float | None, str | None]:
    if value is None or value == '':
        return None, f'{label} is required'
    try:
        rate = json_float(value, label)
    except (TypeError, ValueError):
        return None, f'{label} must be a number (e.g. 0.10 for 10%)'
    if rate < 0:
        return None, f'{label} must be zero or positive and below 1 (e.g. 0.10 for 10%)'
    if rate >= 1:
        return None, f'{label} must be below 1 (e.g. 0.10 for 10%)'
    return rate, None


def scenario_bundles_from_table_rows(
    rows: list[dict[str, object]] | None,
) -> tuple[list[ScenarioBundle] | None, list[str]]:
    """Build scenario bundles from the editable scenarios table.

    Returns ``(None, errors)`` when any rate is invalid. When *rows* is empty,
    returns default bundles with no errors.
    """
    if not rows:
        return list(DEFAULT_SCENARIO_BUNDLES), []

    errors: list[str] = []
    bundles: list[ScenarioBundle] = []
    for row in rows:
        name_raw = row.get('scenario')
        name = str(name_raw).strip() if name_raw is not None else ''
        if not name:
            errors.append('Each scenario row must have a name.')
            continue

        inflation, inflation_err = _parse_rate(
            row.get('inflation_rate'),
            f'{name} inflation rate',
        )
        discount, discount_err = _parse_rate(
            row.get('discount_rate'),
            f'{name} discount rate',
        )
        if inflation_err:
            errors.append(inflation_err)
        if discount_err:
            errors.append(discount_err)
        if inflation is None or discount is None:
            continue
        if discount <= 0:
            errors.append(f'{name} discount rate must be greater than zero.')
            continue

        bundles.append(
            ScenarioBundle(
                name=name,
                inflation_rate=inflation,
                discount_rate=discount,
            )
        )

    if errors:
        return None, errors

    if not bundles:
        return list(DEFAULT_SCENARIO_BUNDLES), []

    return bundles, []


def resolve_scenario_bundles(
    rows: list[dict[str, object]] | None,
) -> tuple[list[ScenarioBundle], list[str]]:
    """Return bundles to use for enrichment, plus Tier 2 warnings."""
    bundles, errors = scenario_bundles_from_table_rows(rows)
    if bundles is None:
        msg = '; '.join(errors) if errors else 'Invalid scenario rates'
        raise ValueError(msg)
    return bundles, scenario_bundle_warnings(bundles)
