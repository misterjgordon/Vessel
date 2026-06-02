"""Saved-vessel dropdown refresh callbacks."""

from typing import TYPE_CHECKING

from dash.dependencies import Input
from dash.dependencies import Output

from app import component_ids as cid
from app.callbacks._helpers import vessel_dropdown_options
from vessel_valuation.db.connection import session_scope

if TYPE_CHECKING:
    from dash import Dash
    from sqlalchemy.orm import Session
    from sqlalchemy.orm import sessionmaker


def register(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register catalog refresh callbacks."""

    @app.callback(
        Output(cid.SELECT_SAVED_VESSEL, 'options'),
        Output(cid.SELECT_SAVED_VESSELS_DELETE, 'options'),
        Output(cid.SELECT_COMPARE_VESSELS, 'options'),
        Output(cid.SELECT_CALCULATION_VESSEL, 'options'),
        Input(cid.BTN_CALCULATE, 'n_clicks'),
        Input(cid.BTN_SAVE_TO_DB, 'n_clicks'),
        Input(cid.BTN_MODAL_DATABASE_LOAD, 'n_clicks'),
        Input(cid.CONFIRM_DELETE_SAVED, 'submit_n_clicks'),
        prevent_initial_call=False,
    )
    def refresh_vessel_catalog(
        _calc_clicks: int | None,
        _save_clicks: int | None,
        _load_clicks: int | None,
        _delete_clicks: int | None,
    ) -> tuple[
        list[dict[str, str | int]],
        list[dict[str, str | int]],
        list[dict[str, str | int]],
        list[dict[str, str | int]],
    ]:
        """Populate saved-vessel dropdowns from the database."""
        with session_scope(session_factory) as session:
            options = vessel_dropdown_options(session)
        return options, options, options, options
