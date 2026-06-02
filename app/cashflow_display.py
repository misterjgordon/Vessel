"""Shared cashflow line-item labels and money formatting for Dash views."""

from datetime import date

CASHFLOW_LINE_ITEMS: tuple[tuple[str, str], ...] = (
    ('revenue', 'Revenue'),
    ('opex', 'OpEx'),
    ('drydock_capex', 'Drydock CapEx'),
    ('upgrades_capex', 'Upgrades CapEx'),
    ('free_cashflow', 'Free cashflow'),
    ('net_cashflow', 'Net cashflow'),
    ('discounted_cashflow', 'Discounted CF'),
    ('cumulative_cashflow', 'Cumulative CF'),
)

CASHFLOW_MONEY_FIELDS: frozenset[str] = frozenset(field for field, _label in CASHFLOW_LINE_ITEMS)

DEFAULT_COMPARE_METRIC = 'free_cashflow'

COMPARE_MIN_VESSELS = 2
COMPARE_MAX_VESSELS = 20


def cashflow_line_item_label(field: str) -> str:
    """Return display label for a schedule field name."""
    for item_field, label in CASHFLOW_LINE_ITEMS:
        if item_field == field:
            return label
    msg = f'unknown cashflow field: {field}'
    raise ValueError(msg)


def cashflow_metric_dropdown_options() -> list[dict[str, str]]:
    """Options for compare-metric and similar dropdowns."""
    return [{'label': label, 'value': field} for field, label in CASHFLOW_LINE_ITEMS]


def format_period_header(period_end: date) -> str:
    """Column header for a schedule period end."""
    return period_end.strftime('%d %b %Y')


def format_money(value: float) -> str:
    """Compact USD display for tables and cards."""
    sign = '-' if value < 0 else ''
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f'{sign}${absolute / 1_000_000:,.2f}m'
    if absolute >= 1_000:
        return f'{sign}${absolute / 1_000:,.1f}k'
    return f'{sign}${absolute:,.0f}'
