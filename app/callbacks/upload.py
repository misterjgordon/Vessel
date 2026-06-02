"""File upload and upload-row selection callbacks."""

import base64

from dash import Dash, no_update
from dash.dependencies import Input, Output, State
from sqlalchemy.orm import Session, sessionmaker

from app import component_ids as cid
from app.callbacks._helpers import (
    FORM_COMPONENT_IDS,
    LOAD_FORM_OUTPUTS_DUPLICATE,
    form_tuple_from_raw,
    raw_from_upload_store,
    upload_preview_row,
)
from app.views.investment import (
    INPUT_SOURCE_BTN_ACTIVE_CLASS,
    INPUT_SOURCE_BTN_CLASS,
    MODAL_HIDDEN_CLASS,
    MODAL_OPEN_CLASS,
)
from vessel_valuation.db.connection import session_scope
from vessel_valuation.db.repository import list_fleet_vessel_inputs
from vessel_valuation.file_parser import parse_upload


def register(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register upload and input-source callbacks."""

    @app.callback(
        Output(cid.STORE_UPLOAD, 'data'),
        Output(cid.UPLOAD_SUMMARY_TABLE, 'data'),
        Output(cid.UPLOAD_SUMMARY_TABLE, 'selected_rows'),
        Output(cid.STORE_UPLOAD_SELECTED_ROW, 'data'),
        Output(cid.UPLOAD_SELECTION_LABEL, 'children'),
        Output(cid.MODAL_UPLOAD, 'className'),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        Input(cid.UPLOAD_FILE, 'contents'),
        State(cid.UPLOAD_FILE, 'filename'),
        prevent_initial_call=True,
    )
    def on_file_upload(
        contents: str | None,
        filename: str | None,
    ) -> tuple[
        object,
        object,
        object,
        object,
        object,
        object,
        object,
    ]:
        """Parse an uploaded file and populate the row summary table."""
        if contents is None or filename is None:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update

        _content_type, content_string = contents.split(',', 1)
        raw_bytes = base64.b64decode(content_string)
        with session_scope(session_factory) as session:
            fleet_peers = list_fleet_vessel_inputs(session)
        parse_result = parse_upload(raw_bytes, filename, fleet_peer_inputs=fleet_peers)

        if not parse_result.ok:
            message = '; '.join(parse_result.header_errors)
            table_row = {
                'row_number': 0,
                'vessel_name': '',
                'teu_size': '',
                'purchase_price': '',
                'status': 'error',
                'messages': message,
            }
            return (
                None,
                [table_row],
                [],
                None,
                'Fix header errors above, then re-upload.',
                MODAL_OPEN_CLASS,
                'file',
            )

        upload_rows: list[dict[str, object]] = []
        table_data: list[dict[str, str | int]] = []

        for row in parse_result.rows:
            if row.errors:
                status = 'error'
            elif row.warnings:
                status = 'warning'
            else:
                status = 'ok'
            messages = '; '.join(row.errors + row.warnings)
            upload_rows.append(
                {
                    'row_number': row.row_number,
                    'raw': row.raw,
                    'errors': row.errors,
                    'warnings': row.warnings,
                }
            )
            table_data.append(
                {
                    **upload_preview_row(row.row_number, row.raw),
                    'status': status,
                    'messages': messages,
                }
            )
        store_payload: dict[str, object] = {'rows': upload_rows}
        return (
            store_payload,
            table_data,
            [],
            None,
            'Click a row to load it into the vessel form.',
            MODAL_OPEN_CLASS,
            'file',
        )

    @app.callback(
        Output(cid.MODAL_UPLOAD, 'className', allow_duplicate=True),
        Input(cid.BTN_MODAL_UPLOAD_CLOSE, 'n_clicks'),
        prevent_initial_call=True,
    )
    def close_upload_modal(_n_clicks: int | None) -> str:
        """Dismiss the file-upload picker."""
        return MODAL_HIDDEN_CLASS

    @app.callback(
        Output(cid.STORE_UPLOAD_SELECTED_ROW, 'data', allow_duplicate=True),
        Output(cid.UPLOAD_SELECTION_LABEL, 'children', allow_duplicate=True),
        Output(cid.MODAL_UPLOAD, 'className', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'children', allow_duplicate=True),
        Output(cid.BANNER_VALIDATION, 'className', allow_duplicate=True),
        Output(cid.UPLOAD_SUMMARY_TABLE, 'selected_rows', allow_duplicate=True),
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data', allow_duplicate=True),
        *LOAD_FORM_OUTPUTS_DUPLICATE,
        Input(cid.UPLOAD_SUMMARY_TABLE, 'selected_rows'),
        State(cid.UPLOAD_SUMMARY_TABLE, 'data'),
        State(cid.STORE_UPLOAD, 'data'),
        prevent_initial_call=True,
    )
    def on_upload_row_selected(
        selected_rows: list[int] | None,
        table_data: list[dict[str, str | int]] | None,
        upload_store: dict[str, object] | None,
    ) -> tuple[object, ...]:
        """Load a clicked upload row into the vessel form and close the modal."""
        form_no_updates = (no_update,) * len(FORM_COMPONENT_IDS)
        if not selected_rows or not table_data or upload_store is None:
            return (
                None,
                'Click a row to load it into the vessel form below.',
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        row_index = selected_rows[0]
        if row_index < 0 or row_index >= len(table_data):
            return (
                None,
                'Click a row to load it into the vessel form below.',
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        row = table_data[row_index]
        row_number = int(row['row_number'])
        vessel_name = str(row.get('vessel_name', ''))
        status = str(row.get('status', ''))

        if status == 'error':
            return (
                row_number,
                f'Row {row_number} ({vessel_name}) has errors and cannot be loaded.',
                MODAL_OPEN_CLASS,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        raw = raw_from_upload_store(upload_store, row_number)
        if raw is None:
            return (
                row_number,
                f'Row {row_number} ({vessel_name}) could not be read from the file.',
                MODAL_OPEN_CLASS,
                no_update,
                no_update,
                no_update,
                no_update,
                *form_no_updates,
            )

        form_tuple = form_tuple_from_raw(session_factory, raw)
        if form_tuple is None:
            return (
                row_number,
                f'Row {row_number} ({vessel_name}) failed validation.',
                MODAL_OPEN_CLASS,
                'Validation failed for the selected row.',
                'validation-banner error',
                no_update,
                no_update,
                *form_no_updates,
            )

        if status == 'warning':
            banner_class = 'validation-banner warning'
        else:
            banner_class = 'validation-banner ok'
        if status == 'warning':
            banner_text = (
                f'Loaded row {row_number} ({vessel_name}) from file — review warnings, '
                'then Calculate valuation.'
            )
        else:
            banner_text = (
                f'Loaded row {row_number} ({vessel_name}) from file into the form. '
                'Click Calculate valuation when ready.'
            )
        return (
            row_number,
            f'Loaded row {row_number} ({vessel_name}) into the form.',
            MODAL_HIDDEN_CLASS,
            banner_text,
            banner_class,
            [],
            'file',
            *form_tuple,
        )

    @app.callback(
        Output(cid.BTN_INPUT_OPTION_MANUAL, 'className'),
        Output(cid.INPUT_SOURCE_UPLOAD_WRAP, 'className'),
        Output(cid.BTN_INPUT_OPTION_DATABASE, 'className'),
        Input(cid.STORE_ACTIVE_INPUT_SOURCE, 'data'),
    )
    def highlight_input_source(active_source: str | None) -> tuple[str, str, str]:
        """Highlight the active vessel-input path in the top bar."""
        upload_class = 'input-source-upload'
        if active_source == 'file':
            upload_class = f'{upload_class} {INPUT_SOURCE_BTN_ACTIVE_CLASS}'
            return (
                INPUT_SOURCE_BTN_CLASS,
                upload_class,
                INPUT_SOURCE_BTN_CLASS,
            )
        if active_source == 'database':
            return (
                INPUT_SOURCE_BTN_CLASS,
                'input-source-upload',
                INPUT_SOURCE_BTN_ACTIVE_CLASS,
            )
        return (
            INPUT_SOURCE_BTN_ACTIVE_CLASS,
            'input-source-upload',
            INPUT_SOURCE_BTN_CLASS,
        )

    @app.callback(
        Output(cid.STORE_ACTIVE_INPUT_SOURCE, 'data'),
        Input(cid.BTN_INPUT_OPTION_MANUAL, 'n_clicks'),
        prevent_initial_call=True,
    )
    def select_manual_input_source(_n_clicks: int | None) -> str:
        """Mark manual entry as the active input path."""
        return 'manual'
