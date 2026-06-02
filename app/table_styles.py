"""Shared Dash DataTable presentation styles."""

DATA_TABLE_CELL_STYLE: dict[str, str] = {
    'textAlign': 'right',
    'padding': '6px',
    'fontFamily': 'system-ui, sans-serif',
    'fontSize': '0.9375rem',
    'fontVariantNumeric': 'tabular-nums',
}

DATA_TABLE_HEADER_STYLE: dict[str, str] = {
    'fontWeight': 'bold',
    'fontFamily': 'system-ui, sans-serif',
    'fontSize': '0.9375rem',
}

DATA_TABLE_LABEL_CELL_STYLE: dict[str, str] = {
    **DATA_TABLE_CELL_STYLE,
    'textAlign': 'left',
}

DATA_TABLE_STYLE_TABLE: dict[str, str] = {'overflowX': 'auto'}


def data_table_left_align(column_id: str) -> dict[str, object]:
    """Conditional style: left-align a row-label column."""
    return {
        'if': {'column_id': column_id},
        'textAlign': 'left',
    }
