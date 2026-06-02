"""View 1 — investment summary (inputs, results, sensitivity, scenarios)."""

from dash import dash_table, dcc, html

from app import component_ids as cid
from app.form_defaults import FORM_DEFAULTS
from app.form_formatting import format_form_field_value, form_field_input_type
from vessel_valuation.db.repository import VesselInputSummary
from vessel_valuation.serialize import json_float
from vessel_valuation.decision_insights.scenario_analysis import DEFAULT_SCENARIO_BUNDLES
from vessel_valuation.file_parser import ACCEPTED_UPLOAD_EXTENSIONS, REQUIRED_COLUMNS

_FORM_SPECS: tuple[tuple[str, str, str], ...] = (
    ('vessel_name', 'Vessel name', cid.INPUT_VESSEL_NAME),
    ('purchase_price', 'Purchase price ($)', cid.INPUT_PURCHASE_PRICE),
    ('vessel_life', 'Vessel life (years)', cid.INPUT_VESSEL_LIFE),
    ('residual_value', 'Residual value ($)', cid.INPUT_RESIDUAL_VALUE),
    ('lw_tonnage', 'LWT (tonnes)', cid.INPUT_LW_TONNAGE),
    ('revenue_per_day', 'Revenue per day ($)', cid.INPUT_REVENUE_PER_DAY),
    ('offhire_rate', 'Off-hire rate (decimal)', cid.INPUT_OFFHIRE_RATE),
    ('opex_per_day', 'OpEx per day ($)', cid.INPUT_OPEX_PER_DAY),
    ('drydock_capex', 'Drydock CapEx ($)', cid.INPUT_DRYDOCK_CAPEX),
    ('drydock_frequency', 'Drydock frequency (years)', cid.INPUT_DRYDOCK_FREQUENCY),
    ('upgrades_capex', 'Upgrades CapEx ($)', cid.INPUT_UPGRADES_CAPEX),
    ('inflation_rate', 'Inflation rate (decimal)', cid.INPUT_INFLATION_RATE),
    ('discount_rate', 'Discount rate (decimal)', cid.INPUT_DISCOUNT_RATE),
    ('days_of_year', 'Days per year', cid.INPUT_DAYS_OF_YEAR),
    ('teu_size', 'TEU size', cid.INPUT_TEU_SIZE),
    ('purchase_date', 'Purchase date', cid.INPUT_PURCHASE_DATE),
    ('engine_type', 'Engine type (optional)', cid.INPUT_ENGINE_TYPE),
    ('co2_carbon_factor', 'CO2 factor (optional)', cid.INPUT_CO2_CARBON_FACTOR),
)

FORM_FIELD_NAMES: tuple[str, ...] = tuple(spec[0] for spec in _FORM_SPECS)
FORM_COMPONENT_IDS: tuple[str, ...] = tuple(spec[2] for spec in _FORM_SPECS)


def format_saved_vessel_option_label(summary: VesselInputSummary) -> str:
    """Single-line label for saved-vessel dropdowns (id, name, TEU, price, date)."""
    return (
        f'#{summary.id} · {summary.vessel_name} · '
        f'{summary.teu_size:,} TEU · ${summary.purchase_price:,.0f} · '
        f'{summary.purchase_date.isoformat()}'
    )


def _workflow_help_text() -> str:
    """Describe the workflow from inputs through persistence to comparison."""
    return (
        '1. Edit the vessel form directly, upload a file, or load a saved entry from the database. '
        '2. Click Calculate valuation, then Save to database when you want to persist. '
        '3. Compare vessels tab — pick two saved entries from the database.'
    )


MODAL_HIDDEN_CLASS = 'modal-overlay modal-hidden'
MODAL_OPEN_CLASS = 'modal-overlay modal-open'
INPUT_SOURCE_BTN_CLASS = 'input-source-btn'
INPUT_SOURCE_BTN_ACTIVE_CLASS = 'input-source-btn input-source-btn-active'


def _icon_upload() -> html.Span:
    """Upload icon (styled via CSS)."""
    return html.Span(className='input-source-icon icon-upload')


def _icon_database() -> html.Span:
    """Database icon (styled via CSS)."""
    return html.Span(className='input-source-icon icon-database')


def _input_source_bar() -> html.Div:
    """Three input paths: manual form, file upload, database load."""
    return html.Div(
        [
            html.Button(
                'Option 1: Manual entry',
                id=cid.BTN_INPUT_OPTION_MANUAL,
                n_clicks=0,
                className=INPUT_SOURCE_BTN_ACTIVE_CLASS,
            ),
            html.Div(
                dcc.Upload(
                    id=cid.UPLOAD_FILE,
                    children=html.Button(
                        [_icon_upload(), ' Option 2: Upload from file'],
                        className=INPUT_SOURCE_BTN_CLASS,
                        type='button',
                    ),
                    multiple=False,
                    accept=','.join(sorted(ACCEPTED_UPLOAD_EXTENSIONS)),
                ),
                id=cid.INPUT_SOURCE_UPLOAD_WRAP,
                className='input-source-upload',
            ),
            html.Button(
                [_icon_database(), ' Option 3: Load from database'],
                id=cid.BTN_INPUT_OPTION_DATABASE,
                n_clicks=0,
                className=INPUT_SOURCE_BTN_CLASS,
            ),
        ],
        className='input-source-bar',
    )


def _upload_modal() -> html.Div:
    """Popup table for choosing a vessel row from an uploaded file."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3('Select vessel from file'),
                            html.Button(
                                '×',
                                id=cid.BTN_MODAL_UPLOAD_CLOSE,
                                n_clicks=0,
                                className='modal-close',
                            ),
                        ],
                        className='modal-header',
                    ),
                    html.P(
                        _upload_help_text(),
                        className='help-text',
                    ),
                    html.Details(
                        [
                            html.Summary('Required column names'),
                            html.Pre(', '.join(sorted(REQUIRED_COLUMNS))),
                        ],
                        className='help-text',
                    ),
                    dash_table_placeholder(),
                    html.P(
                        id=cid.UPLOAD_SELECTION_LABEL,
                        children='Click a row to load it into the form below.',
                        className='help-text upload-selection-label',
                    ),
                ],
                className='modal-dialog',
                role='dialog',
            ),
        ],
        id=cid.MODAL_UPLOAD,
        className=MODAL_HIDDEN_CLASS,
    )


def _database_modal() -> html.Div:
    """Popup picker for loading a saved database entry into the form."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H3('Load from database'),
                            html.Button(
                                '×',
                                id=cid.BTN_MODAL_DATABASE_CLOSE,
                                n_clicks=0,
                                className='modal-close',
                            ),
                        ],
                        className='modal-header',
                    ),
                    html.P(
                        'Choose a saved entry (newest first). Loading fills the vessel form and '
                        'restores the last valuation.',
                        className='help-text',
                    ),
                    html.Div(
                        [
                            html.Label('Saved entry'),
                            dcc.Dropdown(
                                id=cid.SELECT_SAVED_VESSEL,
                                options=[],
                                placeholder='No saved vessels yet — save a valuation first',
                                clearable=True,
                            ),
                        ],
                        className='saved-vessel-select',
                    ),
                    html.Div(
                        [
                            html.Button(
                                'Load into form',
                                id=cid.BTN_MODAL_DATABASE_LOAD,
                                n_clicks=0,
                            ),
                            html.Button(
                                'Cancel',
                                id=cid.BTN_MODAL_DATABASE_CANCEL,
                                n_clicks=0,
                                className='btn-secondary',
                            ),
                        ],
                        className='modal-actions',
                    ),
                ],
                className='modal-dialog',
                role='dialog',
            ),
        ],
        id=cid.MODAL_DATABASE,
        className=MODAL_HIDDEN_CLASS,
    )


def _settings_panel() -> html.Details:
    """Secondary actions: reset defaults and delete saved entries."""
    return html.Details(
        [
            html.Summary('Settings'),
            html.P(
                'Reset the vessel form to the default base-case values, or delete saved '
                'entries from the database (Compare tab lists remaining entries).',
                className='help-text',
            ),
            html.Div(
                [
                    html.Button(
                        'Reset form to base case',
                        id=cid.BTN_RESET_BASECASE,
                        n_clicks=0,
                    ),
                ],
                className='settings-actions',
            ),
            html.Div(
                [
                    html.Label('Delete saved entries'),
                    dcc.Dropdown(
                        id=cid.SELECT_SAVED_VESSELS_DELETE,
                        options=[],
                        placeholder='Select one or more entries to delete',
                        multi=True,
                        clearable=True,
                    ),
                ],
                className='saved-vessel-select',
            ),
            html.Div(
                [
                    html.Button(
                        'Delete selected',
                        id=cid.BTN_DELETE_SAVED,
                        n_clicks=0,
                        className='btn-danger',
                    ),
                ],
                className='saved-vessel-actions',
            ),
            dcc.ConfirmDialog(
                id=cid.CONFIRM_DELETE_SAVED,
                message='Delete the selected saved vessel and its valuation from the database?',
            ),
        ],
        className='settings-panel help-text',
    )


def _upload_help_text() -> str:
    """User-facing upload format: extensions, tabular layout, accepted headers."""
    extensions = ', '.join(sorted(ACCEPTED_UPLOAD_EXTENSIONS))
    return (
        f'Upload a tabular file ({extensions}). Row 1 is the header; each following row '
        'is one vessel. Headers may match the manual form (vessel_name, teu_size, '
        'purchase_price, …) or the case-study Sample Data sheet (e.g. TEU Size, '
        'Vessel Purchase Price). Multi-sheet Excel files use the Sample Data sheet when '
        'present. The vertical Input & Output sheet is not supported. '
        'Every non-blank row is validated; Tier 2 purchase-price÷TEU ratio checks use '
        'the saved fleet when two or more vessels share the same TEU, otherwise case-study '
        'reference values. Rows in the same upload are not compared to each other. '
        'The upload table shows file values with validation status and messages. '
        'Click a row to select it, then Calculate valuation, then Save to database.'
    )


def investment_view() -> html.Div:
    """Build the investment summary tab layout."""
    return html.Div(
        [
            html.P(_workflow_help_text(), className='help-text workflow-steps'),
            _input_source_bar(),
            dcc.Store(id=cid.STORE_ACTIVE_INPUT_SOURCE, data='manual'),
            dcc.Store(id=cid.STORE_UPLOAD_SELECTED_ROW, data=None),
            _upload_modal(),
            _database_modal(),
            html.H3('Vessel inputs'),
            html.P(
                'Edit fields below, or use the options above to load from a file or database.',
                className='help-text',
            ),
            html.Div(_manual_form(), className='input-form'),
            html.Div(
                [
                    html.Button(
                        'Calculate valuation',
                        id=cid.BTN_CALCULATE,
                        n_clicks=0,
                        className='btn-calculate',
                    ),
                    html.Button('Save to database', id=cid.BTN_SAVE_TO_DB, n_clicks=0),
                ],
                className='valuation-actions',
            ),
            html.Div(id=cid.BANNER_VALIDATION, className='validation-banner'),
            _settings_panel(),
            html.Hr(),
            html.H3('Results'),
            html.Div(
                [
                    html.Div([html.H4('NPV'), html.Div(id=cid.CARD_NPV)], className='metric-card'),
                    html.Div([html.H4('IRR'), html.Div(id=cid.CARD_IRR)], className='metric-card'),
                    html.Div(
                        [html.H4('Signal'), html.Div(id=cid.CARD_SIGNAL)],
                        className='metric-card',
                    ),
                    html.Div(
                        [html.H4('Breakeven revenue'), html.Div(id=cid.CARD_BREAKEVEN)],
                        className='metric-card',
                    ),
                    html.Div(
                        [html.H4('Payback year'), html.Div(id=cid.CARD_PAYBACK)],
                        className='metric-card',
                    ),
                ],
                className='metric-row',
            ),
            html.Hr(),
            html.H3('Scenarios'),
            html.P(
                'Fixed Best / Base / Worst bundles (macro inflation and discount rates).',
                className='help-text',
            ),
            dash_table.DataTable(
                id=cid.TABLE_SCENARIOS,
                columns=scenario_table_columns(),  # pyright: ignore[reportArgumentType]
                data=scenario_table_rows(),
                style_table={'overflowX': 'auto'},
                style_cell={
                    'textAlign': 'right',
                    'padding': '6px',
                    'fontFamily': 'system-ui, sans-serif',
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'scenario'}, 'textAlign': 'left'},
                ],
                style_header={'fontWeight': 'bold', 'fontFamily': 'system-ui, sans-serif'},
            ),
            html.Hr(),
            html.H3('Sensitivity — IRR vs revenue per day'),
            html.Div(
                [
                    html.Label('Revenue min ($/day)', htmlFor=cid.INPUT_REV_MIN),
                    dcc.Input(
                        id=cid.INPUT_REV_MIN,
                        type='number',
                        placeholder='auto',
                        step='any',
                    ),
                    html.Label('Revenue max ($/day)', htmlFor=cid.INPUT_REV_MAX),
                    dcc.Input(
                        id=cid.INPUT_REV_MAX,
                        type='number',
                        placeholder='auto',
                        step='any',
                    ),
                ],
                className='sensitivity-range',
            ),
            dcc.Graph(id=cid.CHART_SENSITIVITY),
        ],
        className='view-investment',
    )


def _manual_form() -> html.Div:
    children: list[html.Div] = []
    for field_name, label, component_id in _FORM_SPECS:
        default_raw = FORM_DEFAULTS[field_name]
        default = format_form_field_value(field_name, default_raw)
        input_type = form_field_input_type(field_name)
        step = 'any' if input_type == 'number' else None
        children.append(
            html.Div(
                [
                    html.Label(label),
                    dcc.Input(
                        id=component_id,
                        type=input_type,
                        value=default,
                        step=step,
                    ),
                ],
                className='form-field',
            )
        )
    return html.Div(children, className='form-grid')


def dash_table_placeholder():
    """Upload table: file values plus validation status and messages."""
    from dash import dash_table

    return dash_table.DataTable(
        id=cid.UPLOAD_SUMMARY_TABLE,
        columns=[
            {'name': 'Row', 'id': 'row_number'},
            {'name': 'Vessel', 'id': 'vessel_name'},
            {'name': 'TEU', 'id': 'teu_size'},
            {'name': 'Purchase price', 'id': 'purchase_price'},
            {'name': 'Status', 'id': 'status'},
            {'name': 'Messages', 'id': 'messages'},
        ],
        data=[],
        row_selectable='single',
        selected_rows=[],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '6px'},
        style_header={'fontWeight': 'bold'},
        style_data_conditional=[  # pyright: ignore[reportArgumentType]
            {
                'if': {'state': 'selected'},
                'backgroundColor': '#dbeafe',
                'border': '1px solid #2563eb',
            },
            {
                'if': {'filter_query': '{status} = error'},
                'backgroundColor': '#fee2e2',
            },
            {
                'if': {'filter_query': '{status} = warning'},
                'backgroundColor': '#fef9c3',
            },
        ],
    )


def format_npv(value: float) -> str:
    """Format NPV for display."""
    sign = '-' if value < 0 else ''
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f'{sign}${absolute / 1_000_000:,.2f}m'
    return f'{sign}${absolute:,.0f}'


def format_irr(value: float | None) -> str:
    """Format IRR as a percentage."""
    if value is None:
        return 'N/A'
    return f'{value:.2%}'


def format_rate_per_day(value: float | None) -> str:
    """Format breakeven revenue per day."""
    if value is None:
        return 'N/A'
    return f'${value:,.0f}/day'


def format_payback_year(value: int | None) -> str:
    """Format undiscounted payback year for display."""
    if value is None:
        return 'N/A'
    return str(value)


def format_signal_label(signal: str) -> str:
    """Human-readable investment signal with CSS hook."""
    labels = {
        'INVEST': 'Invest — IRR clearly above hurdle',
        'MARGINAL': 'Marginal — IRR near hurdle',
        'DO NOT INVEST': 'Do not invest — IRR below hurdle or not computable',
    }
    return labels.get(signal, signal)


def scenario_table_columns() -> list[dict[str, str]]:
    """Return DataTable column definitions for Best / Base / Worst scenarios."""
    return [
        {'name': 'Scenario', 'id': 'scenario'},
        {'name': 'Inflation', 'id': 'inflation'},
        {'name': 'Discount', 'id': 'discount'},
        {'name': 'NPV', 'id': 'npv'},
        {'name': 'IRR', 'id': 'irr'},
        {'name': 'Signal', 'id': 'signal'},
    ]


def scenario_table_rows(
    scenarios: dict[str, dict[str, object]] | None = None,
) -> list[dict[str, str]]:
    """Build scenario table rows with rate assumptions and optional valuation results."""
    rows: list[dict[str, str]] = []
    for bundle in DEFAULT_SCENARIO_BUNDLES:
        result = scenarios.get(bundle.name) if scenarios else None
        if result is not None:
            assert isinstance(result, dict)
            npv_cell = format_npv(json_float(result['npv'], 'npv'))
            irr_raw = result['irr']
            irr_cell = format_irr(json_float(result['irr'], 'irr') if irr_raw is not None else None)
            signal_cell = str(result['investment_signal'])
        else:
            npv_cell = irr_cell = signal_cell = '—'
        rows.append(
            {
                'scenario': bundle.name,
                'inflation': f'{bundle.inflation_rate:.0%}',
                'discount': f'{bundle.discount_rate:.0%}',
                'npv': npv_cell,
                'irr': irr_cell,
                'signal': signal_cell,
            }
        )
    return rows


def collect_form_values(*values: str | int | float | None) -> dict[str, str | int | float | None]:
    """Zip component values into a field-name dict."""
    names = FORM_FIELD_NAMES
    if len(values) != len(names):
        msg = f'expected {len(names)} form values, got {len(values)}'
        raise ValueError(msg)
    return dict(zip(names, values, strict=True))
