from dash import dcc, html
# import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import re
from typing import List, Dict, Optional, Union
from dash_iconify import DashIconify
from functools import lru_cache
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


def _parse_idx_from_value(option_value: str, base: str) -> Optional[str]:
    """
    Пытаемся вытащить индекс инстанса из value, например:
    'ADX_10 period ADX.' -> '10'; 'SMA_close' -> None
    """
    if not option_value or not base:
        return None
    m = re.search(rf"{re.escape(base)}_(\d+)", option_value)
    return m.group(1) if m else None


def _format_indicator_params_text(raw_or_value: str, param_source: Optional[Dict]) -> Optional[str]:
    if not raw_or_value or not param_source:
        return None

    base = re.split(r'[_\s(]', raw_or_value)[0]
    if not base:
        return None

    # индекс из raw ("ADX__2__...") или из value ("ADX_14 ...")
    idx_from_raw = None
    if "__" in raw_or_value:
        parts = raw_or_value.split("__")
        if len(parts) >= 2 and parts[1].isdigit():
            idx_from_raw = parts[1]

    idx_from_value = None
    m = re.search(rf"{re.escape(base)}_(\d+)", raw_or_value)
    if m:
        idx_from_value = m.group(1)

    idx = idx_from_raw or idx_from_value

    # плоские ключи ADX__{idx}__param
    flat_related = {k: v for k, v in (param_source or {}).items()
                    if isinstance(k, str) and k.startswith(base + "__")}
    grouped = {}
    for k, v in flat_related.items():
        try:
            _, gidx, param = k.split("__", 2)
        except ValueError:
            continue
        grouped.setdefault(gidx, {})[param] = v

    params = None
    if idx and idx in grouped:
        params = grouped[idx]
    elif grouped:
        params = next(iter(grouped.values()))

    # запасной источник
    if params is None:
        ip = param_source.get("indicator_params") if isinstance(param_source, dict) else None
        if isinstance(ip, dict):
            node = ip.get(base)
            if isinstance(node, dict):
                if idx and isinstance(node.get(idx), dict):
                    params = node[idx]
                else:
                    for v in node.values():
                        if isinstance(v, dict):
                            params = v
                            break
            elif isinstance(node, list):
                for it in node:
                    if isinstance(it, dict):
                        params = it
                        break

    if not isinstance(params, dict) or not params:
        return base

    clean = {k: v for k, v in params.items() if v not in ("", None, "None")}
    period = clean.pop("period", None)

    if period is not None:
        tail = (", " + ", ".join(f"{k} {v}" for k, v in clean.items())) if clean else ""
        return f"{base} (period {period}{tail})"

    inside = ", ".join(f"{k} {v}" for k, v in clean.items())
    return f"{base} ({inside})" if inside else base


def _pretty_option_label(value: str, label: str, param_source: Optional[Dict]) -> str:
    """
    Текст, который видит пользователь в РАСКРЫТОМ списке.
    - OHLCV: показываем исходный label ('Open')
    - Индикатор: красивый вид через _format_indicator_params_text(...)
    """
    if isinstance(value, str) and value.lower() in OHLCV_COLUMNS:
        return label or value
    pretty = _format_indicator_params_text(value, param_source)
    return pretty or (label or value)


def _short_from_any(value: Optional[str], param_source: Optional[Dict] = None) -> Optional[str]:
    if not isinstance(value, str):
        return None

    # RAW: "ADX__1__period" -> "ADX 1"
    m = re.match(r'^([A-Za-z][A-Za-z0-9]*)__(\d+)__', value)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    # Уже короткий: "ADX 1"
    m = re.match(r'^([A-Za-z][A-Za-z0-9]*)\s+(\d+)$', value)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    # Длинный с периодом: "ADX_12 period ..." -> ищем индекс по param_source
    m = re.match(r'^([A-Za-z][A-Za-z0-9]*)_(\d+(?:\.\d+)?)\s+period\b', value)
    if m and isinstance(param_source, dict):
        ind, period_str = m.group(1), m.group(2)

        def norm(x):
            try:
                fx = float(x)
                return str(int(fx)) if fx.is_integer() else str(fx)
            except Exception:
                return str(x)

        tgt = norm(period_str)
        for k, v in param_source.items():
            if isinstance(k, str) and k.startswith(f"{ind}__") and k.endswith("__period"):
                if norm(v) == tgt:
                    return f"{ind} {k.split('__')[1]}"

    return None


def _short_label_from_raw(raw: str) -> str:
    """
    'ADX__1__period' -> 'ADX 1'
    если формат другой — вернём исходное.
    """
    if isinstance(raw, str) and "__" in raw:
        parts = raw.split("__")
        if len(parts) >= 2 and parts[1]:
            return f"{parts[0]} {parts[1]}"
    return str(raw)


def _short_indicator_label(val: str, param_source: Optional[Dict]) -> str:
    return _short_from_any(val, param_source) or (val if isinstance(val, str) else str(val))


def _select_with_tooltip(
    component_id: dict,
    data: List[Dict],
    placeholder: str,
    selected_label: Optional[str],
    style: Optional[dict],
    param_source: Optional[Dict],
):
    button_text = selected_label or placeholder

    # только для тултипа на самой кнопке:
    tooltip_for_selected = None
    if selected_label:
        # пробегаемся по данным, но не строим весь options_src
        for opt in (data or []):
            if opt.get("label") == selected_label:
                tooltip_for_selected = opt.get("label")
                break

    button_component = dmc.Button(
        button_text,
        id={**component_id, "role": "input"},
        n_clicks=0,
        fullWidth=True,
        variant="outline",
        style=style,
    )
    if tooltip_for_selected:
        button_component = dmc.Tooltip(
            label=tooltip_for_selected,
            withArrow=True,
            position="top",
            children=button_component,
            styles=tooltip_styles
        )
    print('data', data)
    print('param_source', param_source)
    return dmc.Popover(
        id={**component_id, "role": "popover"},
        position="bottom-start",
        withArrow=True,
        shadow="md",
        children=[
            dmc.PopoverTarget(button_component),
            dmc.PopoverDropdown([
                dmc.TextInput(
                    id={**component_id, "role": "search"},
                    placeholder="Search…",
                    size="xs",
                    mb=10,
                ),
                html.Div(
                    id={**component_id, "role": "options"},
                    style={"display": "flex", "flexDirection": "column", "rowGap": "6px"},
                ),
                # ⚡️ теперь в Store кладём только исходные данные
                dcc.Store(id={**component_id, "role": "options-src"}, data={
                    "data": data,
                    "param_source": param_source
                }),
            ]),
        ],
    )


def _freeze(obj):
    """Превращает dict/list в JSON-строку для кэширования"""
    if obj is None:
        return None
    if isinstance(obj, (dict, list)):
        return json.dumps(obj, sort_keys=True)
    return obj


@lru_cache(maxsize=32)
def build_options_template(data_str: str, param_source_str: str):
    """
    Возвращает "чистый" список опций (label + tooltip), общий для всех dropdown'ов
    — без parent, чтобы кэш мог сработать для одинаковых data/param_source.
    """
    data = json.loads(data_str) if data_str else []
    param_source = json.loads(param_source_str) if param_source_str else None

    options = []
    for opt in (data or []):
        full_val = opt.get("value")
        raw_key = opt.get("raw") or full_val
        base_lbl = opt.get("label", full_val)

        if isinstance(full_val, str) and (full_val in OHLCV_COLUMNS or full_val.lower() in ohlcv_set_lower):
            display_label = base_lbl or full_val
            tip = OHLCV_DESCRIPTIONS.get(full_val) or OHLCV_DESCRIPTIONS.get(full_val.capitalize(), "")
        elif full_val in compare_description:
            display_label = base_lbl or full_val
            tip = compare_description.get(full_val) or ""
        elif full_val == "custom":
            display_label = base_lbl or full_val
            tip = ""
        else:
            display_label = _short_label_from_raw(raw_key)
            tip = _format_indicator_params_text(raw_key, param_source) or base_lbl or full_val

        options.append({
            "value": full_val,
            "label": display_label,
            "display": display_label,
            "tooltip": tip or "",
            "is_plain": full_val == "custom",
        })

    return options


def build_options_src(component_id: dict, data: list, param_source: dict):
    """
    Берёт "шаблонные" опции из кэша и добавляет уникальный parent для конкретного dropdown.
    """
    data_str = json.dumps(data, sort_keys=True) if data else ""
    param_source_str = json.dumps(param_source, sort_keys=True) if param_source else ""
    base_options = build_options_template(data_str, param_source_str)

    parent_id = {k: str(v) for k, v in {**component_id, "role": "options"}.items()}
    return [{**opt, "parent": parent_id} for opt in base_options]


def generate_conditions_block_group(
    strategy_id,
    condition_type,
    output_options,
    conditions_count,
    selected_values=None,   # ← СТОР выбраных значений (conditions_store_inputs)
    param_source=None       # ← Источник параметров индикаторов для тултипов
):
    sid = str(strategy_id)
    blocks = []

    # стандартные OHLCV
    ohlcv_data = [{'label': c, 'value': c} for c in OHLCV_COLUMNS]

    # только данные (без кастома)
    data_columns_only = (output_options or []) + ohlcv_data

    selected_values = selected_values or {}

    for i in range(int(conditions_count)):
        key = f"{sid}_{condition_type}_{i}"
        vals = selected_values.get(key, {})

        left_label = vals.get('column_label')
        right_label = vals.get('column_or_custom_label')

        blocks.append(
            html.Div([
                # Column selector (left)
                _select_with_tooltip(
                    component_id={'type': 'column_dropdown', 'strategy': sid, 'condition': condition_type, 'index': i},
                    data=data_columns_only,
                    placeholder="Column",
                    selected_label=left_label,
                    style={**tooltip_styles, 'flex': '1.2', 'flexShrink': '1', 'minWidth': '120px',
                           'marginRight': '8px'},
                    param_source=param_source,
                ),

                # Comparison operator (middle)
                _select_with_tooltip(
                    component_id={
                        "type": "comparison_operator",
                        "strategy": sid,
                        "condition": condition_type,
                        "index": i,
                    },
                    data=COMPARISON_OPERATORS,
                    placeholder="Operator",
                    selected_label=vals.get("comparison_operator_label"),
                    style={
                        **tooltip_styles,
                        "flex": "0.8",
                        "flexShrink": "1",
                        "minWidth": "80px",
                        "marginRight": "8px",
                    },
                    param_source=param_source,
                ),

                # Value selector (right)
                _select_with_tooltip(
                    component_id={'type': 'column_or_custom_dropdown', 'strategy': sid, 'condition': condition_type,
                                  'index': i},
                    data=[
                        *data_columns_only,
                        {'value': 'custom', 'label': 'Custom', 'tooltip': 'Enter custom value'}
                    ],
                    placeholder="Value",
                    selected_label=right_label,
                    style={**tooltip_styles, 'flex': '1.2', 'flexShrink': '1', 'minWidth': '120px',
                           'marginRight': '8px'},
                    param_source=param_source,
                ),

                # Custom input (inline with dropdown)
                dcc.Input(
                    id={'type': 'custom_input', 'strategy': sid, 'condition': condition_type, 'index': i},
                    type='number',
                    placeholder='Value',
                    className='custom_value' if (vals.get('column_or_custom') == 'custom') else 'hidden',
                    value=vals.get('custom')
                )
            ], style={
                'display': 'flex',
                'gap': '8px',
                'alignItems': 'center',
                'marginBottom': '12px',
                'flexWrap': 'nowrap',
                'width': '100%'
            })

        )

        # Control buttons
        buttons = [dmc.Button("Add",
                    id={'type': 'modify_condition', 'strategy': str(strategy_id), 'action': 'add', 'condition': condition_type},
                    color="green", size="xs", variant="light"
                ),
                   dmc.Button(f"Clear {condition_type}",
                              id={'type': 'modify_condition', 'strategy': str(strategy_id), 'action': 'clear',
                                  'condition': condition_type},
                              color="gray", size="xs", variant="light"
                              )
                   ]
        if conditions_count > 1:
            buttons.append(
                dmc.Button("Remove",
                       id={'type': 'modify_condition', 'strategy': str(strategy_id), 'action': 'remove',
                           'condition': condition_type},
                       color="red", size="xs", variant="light"
                       )
            )
    blocks.append(
        html.Div(buttons, style={'display': 'flex', 'justifyContent': 'space-between','alignItems': 'center','marginBottom': '15px', 'gap': '8px'})
    )

    return blocks

