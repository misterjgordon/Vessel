"""Dash application entry point."""

import os
from pathlib import Path

from dash import Dash

from app.callbacks import register_callbacks
from app.layout import app_layout
from vessel_valuation.config import get_app_database_url
from vessel_valuation.db.connection import create_db_engine, create_session_factory
from vessel_valuation.db.repository import init_schema


def create_app() -> Dash:
    """Create and configure the Dash application."""
    assets_path = Path(__file__).parent / 'assets'
    dash_app = Dash(
        __name__,
        assets_folder=str(assets_path),
        suppress_callback_exceptions=True,
    )
    dash_app.title = 'Vessel Valuation'

    db_url = get_app_database_url().url
    engine = create_db_engine(db_url)
    init_schema(engine)
    session_factory = create_session_factory(engine)

    dash_app.layout = app_layout
    register_callbacks(dash_app, session_factory)
    return dash_app


def main() -> None:
    """Run the development server."""
    port = int(os.environ.get('PORT', '8050'))
    debug = os.environ.get('DASH_DEBUG', '1') == '1'
    create_app().run(debug=debug, host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()
