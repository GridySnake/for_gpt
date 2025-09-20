# import dash_dangerously_set_inner_html
from dash import html, dcc
# import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from datetime import date
import pandas as pd
import json

df_coins = pd.read_csv('need_files/Symbols_mini.csv')

with open('need_files/indicator_list.txt', 'r') as f:
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
        'padding': '24px',
        'background': '#ffffff',
        'width': 'fit-content',
        'maxWidth': '400px',
        'margin': '0 0 0 0',
        'display': 'inline-block',
        'verticalAlign': 'top'
    }

    input_style = {
        'marginBottom': '2px',
        'borderRadius': '4px',
        'border': '1px solid #e0e0e0',
        'padding': '12px',
        'boxSizing': 'border-box'
    }

    strategies_choose_strategies_field = dmc.GridCol(
        dmc.Card(
            children=[
                dmc.CardSection(
                    dmc.Text("Choose strategy", ta="center", fw=700, size="lg"),
                    withBorder=True, inheritPadding=True
                ),
                dmc.CardSection(
                    dmc.Stack([
                        dcc.Dropdown(
                            df_coins['Symbol'].unique(),
                            'ETH-USD',
                            id='dropdown_coin',
                            style=input_style
                        ),
                        dcc.DatePickerRange(
                            id='date_picker',
                            min_date_allowed=date(2009, 1, 1),
                            max_date_allowed=date.today(),
                            start_date=date(2022, 1, 1),
                            end_date=date.today(),
                            style=input_style
                        ),
                        dcc.Dropdown(
                            id='dropdown_interval',
                            options=[{'label': i, 'value': i} for i in
                                     '1,3,5,15,30,60,120,240,360,720,D,W,M'.split(',')],
                            value='1d',
                            style=input_style
                        ),
                        dcc.Dropdown(
                            id='dropdown_indicators',
                            options=[{'label': indicator, 'value': indicator} for indicator in indicators_dict.keys()],
                            value=[],
                            multi=True,
                            style=input_style
                        ),
                        dmc.Button(
                            'Submit',
                            id='submit_button',
                            n_clicks=0,
                            variant="filled",
                            color="blue"
                        )
                    ])
                )
            ],
            shadow="sm",
            radius="md",
            withBorder=True,
            style=card_style
        ),
        span=4  # <-- именно на GridCol, не на Grid
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
    strategies_input_parameters_for_indicators = dmc.GridCol(
        dmc.Card(
            id='card_indicators_input',
            children=[
                dmc.CardSection(
                    dmc.Button(
                        "Clear ALL",
                        id="clear_all_global",
                        n_clicks=0,
                        color="gray",
                        variant="light",
                        size="xs",
                        style={"marginBottom": "10px"}
                    ),
                    withBorder=True, inheritPadding=True
                ),
                dmc.CardSection(
                    html.Div([], id='input_parameters_for_indicators')
                )
            ],
            style={'display': 'none'}
        ),
        span=3
    )

    # === BLOCK 4: Strategies and conditions ===
    strategies_strategies_and_conditions_buy_sell = dmc.GridCol(
        dmc.Card(
            children=[
                dmc.CardSection(
                    html.Div(
                        id='clear_all_container',
                        children=dmc.Button(
                            "Clear ALL",
                            id={'type': 'clear_all_conditions', 'strategy': 'ALL'},
                            n_clicks=0,
                            color="gray",
                            variant="light",
                            size="xs",
                            style={"marginBottom": "10px"}
                        ),
                        style={'display': 'none'}
                    ),
                    withBorder=True, inheritPadding=True
                ),
                dmc.CardSection(
                    html.Div(id='strategies_container', children=[])
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
                                size="sm",
                                style={'marginBottom': '10px', 'display': 'none'}
                            ),
                            dmc.Button(
                                'Remove strategy',
                                id='remove_strategy',
                                n_clicks=0,
                                color="red",
                                variant="filled",
                                size="sm",
                                style={'marginBottom': '10px', 'display': 'none'}
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
            withBorder=True
        ),
        span=5,
        id='parameters_conditions_block'
    )

    strategies_footer = dcc.Markdown("""
        <style>
            body, html {
                height: 100%;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
            }

            .container {
                flex: 1; /* Занимает всё доступное пространство */
                padding: 30px 0;
            }

            p {
                background-color: #333; 
                color: #fff;
                padding: 20px 0;
                text-align: center;
                margin: 0; /* Убираем стандартные отступы */
            }
        </style>
        <div class="container">
        </div>
        <p>&copy; 2025 Crypto Strategy App | All Rights Reserved</p>
        """, dangerously_allow_html=True)