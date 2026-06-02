"""Dash callbacks — thin wiring to validation, repository, and decision insights."""


from typing import TYPE_CHECKING

from app.callbacks import catalog
from app.callbacks import compute
from app.callbacks import persistence
from app.callbacks import render
from app.callbacks import upload

if TYPE_CHECKING:
    from dash import Dash
    from sqlalchemy.orm import Session
    from sqlalchemy.orm import sessionmaker


def register_callbacks(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register all application callbacks on ``app``."""
    upload.register(app, session_factory)
    persistence.register(app, session_factory)
    compute.register(app, session_factory)
    render.register(app, session_factory)
    catalog.register(app, session_factory)
