"""Dash application entry point."""

import os
from pathlib import Path

from dash import Dash

from app.callbacks import register_callbacks
from app.layout import app_layout
from vessel_valuation.config import get_app_database_url
from vessel_valuation.db.connection import create_db_engine
from vessel_valuation.db.connection import create_session_factory


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
    session_factory = create_session_factory(engine)

    dash_app.layout = app_layout
    register_callbacks(dash_app, session_factory)
    return dash_app


def _print_browser_hint(port: int) -> None:
    """Tell users how to open the app when the terminal link is not clickable."""
    local_url = f'http://localhost:{port}'
    print()
    print(f'Open {local_url} in your browser.')
    print(
        'If the link below is not clickable in your terminal, '
        f'copy and paste {local_url} into the address bar.'
    )
    print()


def main() -> None:
    """Run the development server."""
    port = int(os.environ.get('PORT', '8050'))
    debug = os.environ.get('DASH_DEBUG', '1') == '1'
    _print_browser_hint(port)
    create_app().run(debug=debug, host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()
