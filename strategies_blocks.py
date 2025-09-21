# import dash_dangerously_set_inner_html
from dash import html, dcc
# import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from datetime import date
import pandas as pd
import json

import os
df_coins = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'need_files', 'Symbols_mini.csv'))

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'need_files', 'indicator_list.txt'), 'r') as f:
    indicators_dict = json.loads(f.read())

    strategies_header = html.Header([
        html.Div([
            html.Nav([
                html.A("Crypto Strategy", href="/home", className="navbar-brand"),
                html.Ul([
                    html.Li(html.A("Home", href="/home", className="nav-link")),
                    html.Li(html.A("Strategies", href="/strategies", className="nav-link")),
                    html.Li(html.A("History", href="/history", className="nav-link")),
                    html.Li(html.A("Helpful Materials", href="/helpful_materials", className="nav-link")),
                    html.Li(html.A("About Us", href="/about_us", className="nav-link")),
                    html.Li(html.A("Logout", href="/logout", className="nav-link"))
                ], className="navbar-nav ml-auto")
            ], className="navbar navbar-expand-lg")
        ], className="container")
    ])

    card_style = {
        'boxShadow': '0 4px 8px rgba(0,0,0,0.1)',
        'borderRadius': '8px',
        'padding': '0',
        'background': '#ffffff',
        'width': '90%',
        'margin': '0 auto',
        'border': '1px solid #e1e5e9',
        'minHeight': '800px'
    }

    input_style = {
        'marginBottom': '4px',
        'borderRadius': '4px',
        'border': '1px solid #e0e0e0',
        'padding': '4px 8px',
        'boxSizing': 'border-box',
        'width': '100%',
        'height': '28px',
        'lineHeight': '20px'
    }

    strategies_choose_strategies_field = dmc.Card(
        children=[
            dmc.CardSection(
                dmc.Group([
                    dmc.Text("Strategy parameters", fw=700, size="lg"),
                    dmc.Button(
                        "Clear ALL",
                        id="clear_all_strategy",
                        n_clicks=0,
                        color="gray",
                        variant="light",
                        size="xs"
                    )
                ], justify="space-between"),
                withBorder=True, inheritPadding=True,
                style={
                    "paddingTop": "20px",
                    "paddingBottom": "16px",
                    "lineHeight": "1.5"
                }
            ),
            dmc.CardSection(
                dmc.Stack([
                    dcc.Dropdown(
                        df_coins['Symbol'].unique(),
                        'ETH-USD',
                        id='dropdown_coin',
                        searchable=True,
                        style={
                            **input_style,
                            "height": "28px",
                            "padding": "0 6px"
                        }
                    ),
                    dcc.DatePickerRange(
                        id='date_picker',
                        min_date_allowed=date(2009, 1, 1),
                        max_date_allowed=date.today(),
                        start_date=date(2022, 1, 1),
                        end_date=date.today(),
                        style={
                            **input_style,
                            "height": "28px",
                            "padding": "0 6px"
                        }
                    ),
                    dcc.Dropdown(
                        id='dropdown_interval',
                        options=[{'label': i, 'value': i} for i in
                                 '1,3,5,15,30,60,120,240,360,720,D,W,M'.split(',')],
                        value='1d',
                        style={
                            **input_style,
                            "height": "32px",
                            "padding": "0 6px"
                        }
                    ),
                    dcc.Dropdown(
                        id='dropdown_indicators',
                        options=[{'label': indicator, 'value': indicator} for indicator in indicators_dict.keys()],
                        value=[],
                        multi=True,
                        searchable=True,
                        style={
                            **input_style,
                            "height": "32px",
                            "padding": "0 6px"
                        }
                    ),
                    dmc.Button(
                        'Submit',
                        id='submit_button',
                        n_clicks=0,
                        variant="filled",
                        color="blue",
                        size="md",
                        style={"height": "20px", "marginTop": "10px"}
                    )
                ])
            )
        ],
        radius="md",
        style={**card_style, "minHeight": "1000px", "align":"center",
	"justify":"space-between",
	"gap":"xs",}
    )

    # === BLOCK 2: Graphs ===
    strategies_graphs = dcc.Loading(
        [
            html.H4(id='no_data_message', children=['Sorry. There is no data'], style={'visibility': 'hidden'}),
            html.H4(id='header', children=[]),
            html.Div(id='graph_strategy_div', children=[]),
            html.Div(id='graph_coin_div', children=[]),
            html.Div(id='graphs_indicators', children=[])
        ],
        target_components={
            'no_data_message': 'children',
            'header': 'children',
            'graph_strategy_div': 'children',
            'graph_coin_div': 'children',
            'graphs_indicators': 'children'
        }
    )

    # === BLOCK 3: Input parameters ===
    # === BLOCK 3: Input parameters for indicators ===
    strategies_input_parameters_for_indicators = dmc.Card(
        id='card_indicators_input',
        children=[
            dmc.CardSection(
                dmc.Group([
                    dmc.Text("Indicator Parameters", fw=700, size="lg"),
                    dmc.Button(
                        "Clear ALL",
                        id="clear_all_global",
                        n_clicks=0,
                        color="gray",
                        variant="light",
                        size="xs"
                    )
                ], justify="space-between"),
                withBorder=True, inheritPadding=True,
                style={
                    "paddingTop": "20px",
                    "paddingBottom": "16px",
                    "lineHeight": "1.5"
                }
            ),
            dmc.CardSection(
                html.Div([], id='input_parameters_for_indicators')
            )
        ], style={}
    )

    # === BLOCK 4: Strategies and conditions ===
    strategies_strategies_and_conditions_buy_sell = dmc.Card(
        children=[
            dmc.CardSection(
                dmc.Group([
                    dmc.Text("Strategy Conditions", fw=700, size="lg"),
                    html.Div(
                        id='clear_all_container',
                        children=dmc.Button(
                            "Clear ALL",
                            id={'type': 'clear_all_conditions', 'strategy': 'ALL'},
                            n_clicks=0,
                            color="gray",
                            variant="light",
                            size="xs"
                        ),
                        style={'display': 'none'}
                    )
                ], justify="space-between"),
                withBorder=True, inheritPadding=True,
                style={
                    "paddingTop": "20px",
                    "paddingBottom": "16px",
                    "lineHeight": "1.5"
                }
            ),
            dmc.CardSection(
                html.Div(id="strategies_cards_container", className="strategy-conditions")
            ),
            dmc.CardSection(
                dmc.Group(
                    [
                        dmc.Button(
                            'Add strategy',
                            id='add_strategy',
                            n_clicks=0,
                            color="green",
                            variant="filled",
                            size="md",
                            style={'marginBottom': '10px', 'display': 'none', 'height': '40px'}
                        ),
                        dmc.Button(
                            'Remove strategy',
                            id='remove_strategy',
                            n_clicks=0,
                            color="red",
                            variant="filled",
                            size="md",
                            style={'marginBottom': '10px', 'display': 'none', 'height': '40px'}
                        )
                    ],
                    justify="space-between",  # кнопки разнесены по краям
                    gap="md",
                    style={"marginBottom": "20px"}
                ),
                inheritPadding=True
            )
        ],
        shadow="sm",
        radius="md",
        withBorder=True,
        id='parameters_conditions_block'
    )

    strategies_footer = html.Footer([
        html.P("© 2025 Crypto Strategy App | All Rights Reserved")
    ], style={
        "background-color": "#333",
        "color": "#fff",
        "padding": "20px 0",
        "text-align": "center",
        "margin-top": "30px",
        "flex-shrink": "0"
    })
