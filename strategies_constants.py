from typing import Any, Dict, List
import pandas as pd
import operator
import os
import datetime as dt
import json

OHLCV_COLUMNS = {"Open", "High", "Low", "Close", "Volume"}  # как у тебя
OHLCV_DESCRIPTIONS = {
    "Open": "Opening price",
    "High": "Highest price",
    "Low": "Lowest price",
    "Close": "Closing price",
    "Volume": "Trading volume",
}
ohlcv_set = set(OHLCV_DESCRIPTIONS.keys())
ohlcv_set_lower = {c.lower() for c in ohlcv_set}
compare_description = {
    '>': 'Greater than',
    '>=': 'Greater than or equal to',
    '<': 'Less than',
    '<=': 'Less than or equal to',
    '=': 'Equal to'
}

COMPARISON_OPERATORS = [
    {"value": ">", "label": ">", "tooltip": "Greater than"},
    {"value": ">=", "label": ">=", "tooltip": "Greater than or equal to"},
    {"value": "<", "label": "<", "tooltip": "Less than"},
    {"value": "<=", "label": "<=", "tooltip": "Less than or equal to"},
    {"value": "=", "label": "=", "tooltip": "Equal to"},
]

tooltip_styles = {
            "tooltip": {
                "backgroundColor": "#ffffff",
                "color": "#111111",
                "border": "1px solid #f59f00",
                "boxShadow": "0 2px 8px rgba(245,159,0,0.3)",
                "borderRadius": "8px",
                "fontSize": "13px",
                "padding": "6px 10px",
            },
            "arrow": {
                "backgroundColor": "#ffffff",
                "border": "1px solid #f59f00",
            }}

df_input_parameters = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'need_files', 'indicators_input_parameters.csv'))

dict_ops = {
    '>':  operator.gt,
    '<':  operator.lt,
    '=':  operator.eq,
    '>=': operator.ge,
    '<=': operator.le,
    '!=': operator.ne
}

Key = str
Store = Dict[Key, Dict[str, Any]]
StrategyList = List[Dict[str, Any]]

submit_clicks = {"click": 0}

df_output_parameters = pd.read_csv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "need_files",
        "indicators_output_parameters.csv",
    )
)

today_str = dt.date.today().strftime("%Y-%m-%d")

df_coins = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'need_files', 'Symbols_mini.csv'))

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'need_files', 'indicator_list.txt'), 'r') as f:
    indicators_dict = json.loads(f.read())
