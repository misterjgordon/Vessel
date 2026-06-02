"""Dash callbacks — thin wiring to validation, repository, and decision insights."""

from dash import Dash
from sqlalchemy.orm import Session, sessionmaker

from app.callbacks import catalog, compute, persistence, render, upload


def register_callbacks(app: Dash, session_factory: sessionmaker[Session]) -> None:
    """Register all application callbacks on ``app``."""
    upload.register(app, session_factory)
    persistence.register(app, session_factory)
    compute.register(app, session_factory)
    render.register(app, session_factory)
    catalog.register(app, session_factory)
