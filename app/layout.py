"""Top-level Dash layout — header and tabbed views."""

from dash import dcc
from dash import html

from app import component_ids as cid
from app.views.calculation import calculation_view
from app.views.compare import compare_view
from app.views.investment import investment_view


def app_layout() -> html.Div:
    """Build the root application layout."""
    return html.Div(
        [
            html.Header(
                [
                    html.H1('Vessel Valuation'),
                    html.P('DCF investment analysis'),
                ],
                className='app-header',
            ),
            dcc.Store(id=cid.STORE_COMPUTE),
            dcc.Store(id=cid.STORE_UPLOAD),
            dcc.Tabs(
                [
                    dcc.Tab(
                        label='Investment summary',
                        value=cid.TAB_VALUE_INVESTMENT,
                        children=[investment_view()],
                    ),
                    dcc.Tab(
                        label='Calculation detail',
                        value=cid.TAB_VALUE_CALCULATION,
                        children=[calculation_view()],
                    ),
                    dcc.Tab(
                        label='Compare vessels',
                        value=cid.TAB_VALUE_COMPARE,
                        children=[compare_view()],
                    ),
                ],
                id=cid.APP_TABS,
                value=cid.TAB_VALUE_INVESTMENT,
                className='app-tabs',
            ),
        ],
        className='app-root',
    )
