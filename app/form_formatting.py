"""Display and parse thousand-separated numbers in manual form fields."""

from vessel_valuation.mapping import FormRawValue, VesselInputField, VesselInputFormRawDict

# Whole-number fields shown with thousands separators (text inputs in the UI).
COMMA_FORMATTED_FIELDS: frozenset[str] = frozenset(
    {
        'purchase_price',
        'vessel_life',
        'residual_value',
        'lw_tonnage',
        'revenue_per_day',
        'opex_per_day',
        'drydock_capex',
        'drydock_frequency',
        'upgrades_capex',
        'days_of_year',
        'teu_size',
    }
)

# Decimal rates — no comma grouping.
DECIMAL_FORM_FIELDS: frozenset[str] = frozenset(
    {
        'offhire_rate',
        'inflation_rate',
        'discount_rate',
        'co2_carbon_factor',
    }
)


def format_display_number(value: int | float) -> str:
    """Format a numeric form value with thousands separators."""
    if isinstance(value, float) and value.is_integer():
        return f'{int(value):,}'
    if isinstance(value, int):
        return f'{value:,}'
    return f'{value:,.2f}'.rstrip('0').rstrip('.')


def parse_display_number(value: str | int | float | None) -> int | float | None:
    """Parse a form field value that may include comma grouping."""
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise TypeError('expected a numeric form value')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value

    cleaned = str(value).replace(',', '').strip()
    if not cleaned:
        return None

    parsed = float(cleaned)
    if parsed.is_integer():
        return int(parsed)
    return parsed


def format_form_field_value(
    field_name: VesselInputField | str, value: FormRawValue
) -> FormRawValue:
    """Format a single form default or bound value for display."""
    if value is None or value == '':
        return value
    if field_name in COMMA_FORMATTED_FIELDS and isinstance(value, (int, float)):
        return format_display_number(value)
    return value


def format_form_values_for_display(
    values: VesselInputFormRawDict,
) -> VesselInputFormRawDict:
    """Return a copy of form values with comma formatting applied where configured."""
    return {key: format_form_field_value(key, value) for key, value in values.items()}


def form_field_input_type(field_name: VesselInputField | str) -> str:
    """Return Dash ``dcc.Input`` type for a form field."""
    if field_name in (
        VesselInputField.VESSEL_NAME,
        VesselInputField.PURCHASE_DATE,
        VesselInputField.ENGINE_TYPE,
    ):
        return 'text'
    if field_name in COMMA_FORMATTED_FIELDS:
        return 'text'
    return 'number'
