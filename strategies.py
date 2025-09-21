# =========================================================
# === Imports
# =========================================================
from dash import Dash, dcc, html, Input, Output, State, ALL, MATCH, ctx

import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculate import Coin, Indicator
from secure_middleware_for_dash import AuthMiddleware
from dash.exceptions import PreventUpdate
from pages_apps.strategies_blocks import (
    strategies_footer,
    strategies_header,
    strategies_choose_strategies_field,
    strategies_input_parameters_for_indicators,
    strategies_strategies_and_conditions_buy_sell,
    strategies_graphs,
)
from pages_apps.strategies_generate_blocks_functions import (
    generate_conditions_block_group,
    tooltip_styles,
    build_options_template,
    COMPARISON_OPERATORS,
)
from pages_apps.strategies_helpful_functions import (
    group_params,
    _max_ui_index_for,
    dict_ops,
    delete_instance_keys,
    delete_indicator_keys,
    as_selected_set,
    _fmt_pct,
    _color_scale_number,
    extract_indicator_params,
    replace_ids_with_names,
    prune_by_alive_strategies,
    handle_input_groups,
    handle_clear_all,
    handle_modify_condition,
    handle_option_button_click,
    is_noop_trigger,
    generate_all_strategy_cards,
    build_strategy_render_context,
)
import json
import itertools
import plotly.colors as pc
import dash_mantine_components as dmc

# =========================================================
# === Constants & Config
# =========================================================

d = {"click": 0}
style_table = (
    {
        "overflowX": "auto",
        "marginBottom": "0px",  # убираем отступ снизу
    },
)
style_cell = ({"textAlign": "center", "padding": "4px"},)
style_data = {"whiteSpace": "normal", "height": "auto"}

df_input_parameters = pd.read_csv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "need_files",
        "indicators_input_parameters.csv",
    )
)
df_output_parameters = pd.read_csv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "need_files",
        "indicators_output_parameters.csv",
    )
)

strategies_app = Dash(
    __name__,
    requests_pathname_prefix="/strategies/",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",
    ],
    suppress_callback_exceptions=True,
)

# =========================================================
# === Layout
# =========================================================

strategies_app.layout = dmc.MantineProvider(
    theme={"colorScheme": "light"},
    children=html.Div(
        [
            # Стили и мета-теги
            # strategies_styles,
            # Header с навигацией
            strategies_header,
            # Основной контент
            html.Div(
                [
                    dmc.Grid(
                        children=[
                            dmc.GridCol(
                                strategies_choose_strategies_field,
                                span=3,
                                id="column_1",
                                style={"padding": "0 8px 0 0"},
                            ),
                            dmc.GridCol(
                                strategies_input_parameters_for_indicators,
                                span=3,
                                id="column_2",
                                style={
                                    "display": "none",
                                    "padding": "0 8px",
                                    "borderLeft": "1px solid #e1e5e9",
                                },
                            ),
                            dmc.GridCol(
                                strategies_strategies_and_conditions_buy_sell,
                                span=6,
                                id="column_3",
                                style={
                                    "display": "none",
                                    "padding": "0 0 0 8px",
                                    "borderLeft": "1px solid #e1e5e9",
                                },
                            ),
                        ],
                        gutter="md",  # увеличиваем промежуток между колонками
                        style={
                            "maxWidth": "1400px",
                            "margin": "0 auto",
                            "padding": "20px",
                        },
                    ),
                    # Загружаем графики и прочие данные
                    strategies_graphs,
                ],
                style={"flex": "1", "minHeight": "0"},
            ),
            # Сторы
            dcc.Store(id="stored_inputs", storage_type="memory"),
            dcc.Store(id="conditions_store", data={}, storage_type="memory"),
            dcc.Store(id="conditions_store_inputs", data={"1_buy_0": {}, "1_sell_0": {}}),
            dcc.Store(id="tab-parameters-store", storage_type="memory"),
            dcc.Store(
                id="strategies_store",
                data=[{"id": 1, "conditions_store": {"buy": 1, "sell": 1}}],
                storage_type="memory",
            ),
            dcc.Store(id="param_instances", data={}, storage_type="memory"),
            dcc.Store(id="indicator_inputs_ready", data=False),
            # Footer в конце страницы
            strategies_footer,
        ],
        style={
            "min-height": "100vh",
            "margin": "0",
            "font-family": ["Arial", "sans-serif"],
            "background-color": "#f4f7fa",
            "display": "flex",
            "flex-direction": "column",
        },
    ),
)

# =========================================================
# === Clientside Callbacks
# =========================================================

# CLIENT-SIDE callback: мгновенное открытие/закрытие popover и смена label
strategies_app.clientside_callback(
    """
    function(input_clicks, option_clicks, store_data, input_id, current_label) {
        // безопасные алиасы
        var dc = window.dash_clientside || {};
        var no_update = dc.no_update || {'__dash_clientside_no_update': true};

        var opened = no_update;
        var label = no_update;

        // defensive: если нет input_id - ничего не делаем
        if (!input_id) {
            return [opened, label];
        }

        // try to get triggered id from client ctx
        var ctx = (dc && dc.callback_context) ? dc.callback_context : (window.dash_clientside_callback_context || null);
        var triggered = null;
        if (ctx && ctx.triggered && ctx.triggered.length > 0) {
            triggered = ctx.triggered[0];
        }

        if (triggered && triggered.prop_id) {
            var prop = triggered.prop_id.split('.')[0];
            var trig_id = null;
            try {
                trig_id = JSON.parse(prop);
            } catch (e) {
                trig_id = null;
            }

            if (trig_id) {
                // клик по эл-ту input (тот, у которого role == 'input')
                if (trig_id.role && trig_id.role === 'input') {
                    if ((input_clicks || 0) > 0) {
                        opened = true;
                    }
                }
                // клик по option-btn
                else if (trig_id.type && trig_id.type === 'option-btn') {
                    // сравниваем скоуп: strategy/condition/index
                    if (String(trig_id.strategy) === String(input_id.strategy) &&
                        trig_id.condition === input_id.condition &&
                        String(trig_id.index) === String(input_id.index)) {
                        opened = false;
                        label = trig_id.label || current_label;
                    }
                }
            }
        }

        // Если в store есть фиксированная подпись — приоритет
        try {
            var key = String(input_id.strategy) + '_' + input_id.condition + '_' + input_id.index;
            var t = input_id.type;
            if (t === 'column_dropdown' && store_data && store_data[key] && store_data[key].column_label) {
                label = store_data[key].column_label;
            } else if (t === 'comparison_operator' && store_data && store_data[key] && store_data[key].comparison_operator_label) {
                label = store_data[key].comparison_operator_label;
            } else if (t === 'column_or_custom_dropdown' && store_data && store_data[key] && store_data[key].column_or_custom_label) {
                label = store_data[key].column_or_custom_label;
            }
        } catch (e) {
            // ignore
        }

        return [opened, label];
    }
    """,
    [
        Output(
            {
                "type": MATCH,
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "role": "popover",
            },
            "opened",
        ),
        Output(
            {
                "type": MATCH,
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "role": "input",
            },
            "children",
        ),
    ],
    # Inputs (clientside получает Inputs и States в том порядке, в котором их перечислим)
    [
        Input(
            {
                "type": MATCH,
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "role": "input",
            },
            "n_clicks",
        ),
        # pattern-matching input для опций в том же скоупе (входит массив n_clicks)
        Input(
            {
                "type": "option-btn",
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "value": ALL,
                "label": ALL,
            },
            "n_clicks",
        ),
        Input("conditions_store_inputs", "data"),
    ],
    # States (передаются в ту же функцию после Inputs)
    [
        State(
            {
                "type": MATCH,
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "role": "input",
            },
            "id",
        ),
        State(
            {
                "type": MATCH,
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "role": "input",
            },
            "children",
        ),
    ],
)

strategies_app.clientside_callback(
    """
    function(ready, children){
        // Show only if ready AND has children
        const hasChildren = children && children.length > 0;
        return {display: (ready && hasChildren) ? "block" : "none"};
    }
        """,
    Output("column_2", "style"),
    [
        Input("indicator_inputs_ready", "data"),
        Input("input_parameters_for_indicators", "children"),
    ],
)

# Client-side callback to show columns 2 and 3 when indicators are selected
strategies_app.clientside_callback(
    """
    function(selected_indicators) {
        // Show columns if any indicators are selected
        const shouldShow = selected_indicators && selected_indicators.length > 0;
        return [
            {"display": shouldShow ? "block" : "none"}   // column_3 style
        ];
    }
    """,
    [Output("column_3", "style")],
    [Input("dropdown_indicators", "value")],
)

# =========================================================
# === Server-side Callbacks
# =========================================================

@strategies_app.callback(
    Output(
        {
            "type": MATCH,
            "strategy": MATCH,
            "condition": MATCH,
            "index": MATCH,
            "role": "options",
        },
        "children",
    ),
    [
        Input(
            {
                "type": MATCH,
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "role": "search",
            },
            "value",
        ),
        Input(
            {
                "type": MATCH,
                "strategy": MATCH,
                "condition": MATCH,
                "index": MATCH,
                "role": "options-src",
            },
            "data",
        ),
        Input("conditions_store_inputs", "data"),
    ],
    State(
        {
            "type": MATCH,
            "strategy": MATCH,
            "condition": MATCH,
            "index": MATCH,
            "role": "options",
        },
        "id",
    ),
    prevent_initial_call=False,
)
def render_options(
    search_value, options_payload, conditions_store_inputs, container_id
):
    query = (search_value or "").strip().lower()

    if not options_payload:
        return []

    # достаём из Store исходные данные
    data = options_payload.get("data") or []
    param_source = options_payload.get("param_source")

    # ⚡️ тут используем кэшируемую функцию
    options = build_options_template(
        json.dumps(data, sort_keys=True),
        json.dumps(param_source, sort_keys=True) if param_source else "",
    )

    parent_id = {k: str(v) for k, v in {**container_id, "role": "options"}.items()}
    if container_id.get("type") == "comparison_operator":
        options_src = [
            {**opt, "parent": {**container_id, "role": "options"}}
            for opt in COMPARISON_OPERATORS
        ]
    else:
        options_src = [{**opt, "parent": parent_id} for opt in options]

    filtered = []
    for opt in options_src:
        lbl = opt.get("label") or ""
        if not query or query in str(lbl).lower():
            filtered.append(opt)

    # определяем текущее выбранное значение
    strategy_id = str(container_id["strategy"])
    condition = container_id["condition"]
    index = str(container_id["index"])
    field_type = container_id["type"]
    store_key = f"{strategy_id}_{condition}_{index}"

    selected_value = None
    if field_type == "column_dropdown":
        selected_value = (
            (conditions_store_inputs or {}).get(store_key, {}).get("column", None)
        )
    elif field_type == "column_or_custom_dropdown":
        selected_value = (
            (conditions_store_inputs or {})
            .get(store_key, {})
            .get("column_or_custom", None)
        )
    elif field_type == "comparison_operator":
        selected_value = (
            (conditions_store_inputs or {})
            .get(store_key, {})
            .get("comparison_operator", None)
        )

    # собираем кнопки
    children = []
    for opt in filtered:
        is_selected = opt.get("value") == selected_value
        button_style = {"justifyContent": "flex-start"}
        if is_selected:
            button_style.update(
                {
                    "backgroundColor": "#f59f00",
                    "color": "white",
                    "border": "1px solid #f59f00",
                }
            )

        btn_id = {
            "type": "option-btn",
            "strategy": container_id["strategy"],
            "condition": container_id["condition"],
            "index": container_id["index"],
            "field_type": container_id["type"],
            "value": opt.get("value"),
            "label": opt.get("display") or opt.get("label"),
        }

        btn = dmc.Button(
            opt.get("display") or opt.get("label"),
            id=btn_id,
            variant="subtle",
            size="xs",
            fullWidth=True,
            style=button_style,
        )

        if not opt.get("is_plain"):
            btn = dmc.Tooltip(
                label=opt.get("tooltip") or opt.get("display") or opt.get("label"),
                withArrow=True,
                position="right",
                children=btn,
                styles=tooltip_styles,
            )

        children.append(btn)

    return children


@strategies_app.callback(
    Output('conditions_store_inputs', 'data'),
    [
        Input({'type': 'option-btn', 'strategy': ALL, 'condition': ALL, 'index': ALL, 'field_type': ALL, 'value': ALL, 'label': ALL}, 'n_clicks'),
        Input({'type': 'comparison_operator', 'strategy': ALL, 'condition': ALL, 'index': ALL}, 'value'),
        Input({'type': 'column_or_custom_dropdown', 'strategy': ALL, 'condition': ALL, 'index': ALL}, 'value'),
        Input({'type': 'custom_input', 'strategy': ALL, 'condition': ALL, 'index': ALL}, 'value'),
        Input({'type': 'modify_condition', 'strategy': ALL, 'action': ALL, 'condition': ALL}, 'n_clicks'),
        Input({'type': 'clear_all_conditions', 'strategy': ALL}, 'n_clicks'),
        Input('remove_strategy', 'n_clicks'),
        Input('strategies_store', 'data'),
    ],
    State('conditions_store_inputs', 'data'),
    prevent_initial_call=True
)
def save_condition_inputs(
    option_clicks,
    operator_values,
    right_values,
    custom_values,
    modify_clicks,
    clear_all_clicks,
    remove_strategy_clicks,
    strategies,
    stored_data,
):
    """
    Обновляет состояние conditions_store_inputs.
    Логика полностью сохранена, просто разнесена по хелперам.
    """

    stored_data = stored_data or {}

    # Защита от «пустого» триггера (как в исходнике)
    if is_noop_trigger():
        raise PreventUpdate

    trig = ctx.triggered_id

    # --- CLEAR ALL ---
    if isinstance(trig, dict) and trig.get('type') == 'clear_all_conditions':
        return handle_clear_all(stored_data)

    # --- MODIFY CONDITION (clear/remove по конкретной стороне) ---
    if isinstance(trig, dict) and trig.get('type') == 'modify_condition':
        return handle_modify_condition(stored_data, trig)

    # --- OPTION BUTTON (popover) ---
    if isinstance(trig, dict) and trig.get('type') == 'option-btn':
        new_store = handle_option_button_click(stored_data, trig)
        # отфильтруем по живым стратегиям (как в конце исходника)
        return prune_by_alive_strategies(new_store, strategies)

    # --- Обычные контролы (comparison_operator / column_or_custom / custom_input) ---
    new_store = handle_input_groups(stored_data, operator_values, right_values, custom_values)
    return prune_by_alive_strategies(new_store, strategies)


@strategies_app.callback(
    Output("strategies_cards_container", "children"),
    [
        Input("strategies_store", "data"),
        Input("tab-parameters-store", "data"),
        Input("conditions_store_inputs", "data"),
        Input("stored_inputs", "data"),
    ],
    prevent_initial_call=False,
)
def render_strategy_cards_cb(strategies, tab_parameters, conditions_inputs, stored_inputs_params):
    strategies = strategies or []
    if not strategies:
        return []

    output_options, param_source = build_strategy_render_context(
        tab_parameters, stored_inputs_params
    )

    if not output_options:
        return []

    return generate_all_strategy_cards(
        strategies_store=strategies,
        conditions_store_inputs=conditions_inputs,
        output_options=output_options,
        param_source=param_source,
    )


@strategies_app.callback(
    [
        Output("tab-parameters-store", "data"),
        Output("add_strategy", "style"),
        Output("parameters_conditions_block", "style"),
        Output("clear_all_container", "style"),
    ],
    [
        Input("dropdown_indicators", "value"),
        Input("param_instances", "data"),
        Input("stored_inputs", "data"),
    ],
    prevent_initial_call=True,
)
def generate_indicator_parameters_outputs(indicators, param_instances, stored_inputs):
    if not indicators:
        return None, {"display": "none"}, {"display": "none"}, {"display": "none"}

    df_selected = df_output_parameters[
        df_output_parameters["indicator"].isin(indicators)
    ]
    df_selected = df_selected[df_selected["output_name"] != "no_parameters"]
    if df_selected.empty:
        return None, {"display": "none"}, {"display": "none"}, {"display": "none"}

    # прежний плоский список (оставим для обратной совместимости и отладки)
    all_options = []
    for ind in indicators:
        cols = (
            df_selected[df_selected["indicator"] == ind]["output_name"]
            .unique()
            .tolist()
        )
        all_options.extend([f"{ind}_{c}" for c in cols])

    # === структурированные опции по инстансам с подстановкой period ===
    param_instances = param_instances or {}
    stored_inputs = stored_inputs or {}
    output_options = []

    for ind in indicators:
        cols = (
            df_selected[df_selected["indicator"] == ind]["output_name"]
            .unique()
            .tolist()
        )
        count = int(param_instances.get(ind, 1) or 1)
        for inst in range(1, count + 1):
            key_period = f"{ind}__{inst}__period"
            pval = stored_inputs.get(key_period, None)
            if pval in (None, "", "None"):
                period_label = "i"
            else:
                try:
                    period_label = (
                        str(int(pval)) if float(pval).is_integer() else str(pval)
                    )
                except Exception:
                    period_label = str(pval)

            base = f"{period_label} period"
            for col in cols:
                label_val = f"{ind}_{col.replace('i period', base)}"
                raw_key = f"{ind}__{inst}__{col}"  # 👈 добавляем сырой ключ для связи с param_source
                output_options.append(
                    {
                        "label": label_val,  # длинное название, с подставленным периодом
                        "value": label_val,  # как и раньше, чтобы не ломать совместимость
                        "raw": raw_key,  # сырой ключ: "ADX__1__period"
                    }
                )

    result = {"output_names": all_options, "output_options": output_options}

    return result, {"display": "block"}, {"display": "block"}, {"display": "block"}


@strategies_app.callback(
    [Output("strategies_store", "data"), Output("remove_strategy", "style")],
    [
        Input("remove_strategy", "n_clicks"),
        Input("add_strategy", "n_clicks"),
        Input(
            {
                "type": "modify_condition",
                "strategy": ALL,
                "action": ALL,
                "condition": ALL,
            },
            "n_clicks",
        ),
        Input({"type": "clear_all_conditions", "strategy": ALL}, "n_clicks"),
        Input(
            {"type": "strategy_name_input", "strategy": ALL}, "value"
        ),  # <─ добавлен input
    ],
    State("strategies_store", "data"),
    prevent_initial_call=True,
)
def update_strategies(
    remove_click, add_click, modify_clicks, clear_all_clicks, names, strategies
):
    """
    Управляет количеством стратегий, условиями и именами.
    """
    strategies = strategies or [
        {"id": 1, "name": "1", "conditions_store": {"buy": 1, "sell": 1}}
    ]
    style = {"display": "none"}

    trig = ctx.triggered_id
    if trig is None:
        raise PreventUpdate

    # --- CLEAR ALL ---
    if isinstance(trig, dict) and trig.get("type") == "clear_all_conditions":
        return [
            {"id": 1, "name": "1", "conditions_store": {"buy": 1, "sell": 1}}
        ], style

    # --- ADD STRATEGY ---
    if trig == "add_strategy":
        new_id = max([int(s.get("id", 0)) for s in strategies] or [0]) + 1
        strategies = strategies + [
            {
                "id": new_id,
                "name": str(new_id),
                "conditions_store": {"buy": 1, "sell": 1},
            }
        ]
        if len(strategies) > 1:
            style = {"display": "block"}
        return strategies, style

    # --- REMOVE STRATEGY ---
    if trig == "remove_strategy":
        max_index = max(range(len(strategies)), key=lambda i: strategies[i]["id"])
        strategies.pop(max_index)
        if len(strategies) > 1:
            style = {"display": "block"}
        return strategies, style

    # --- MODIFY CONDITION ---
    if isinstance(trig, dict) and trig.get("type") == "modify_condition":
        strategy_id = str(trig.get("strategy"))
        cond = trig.get("condition")
        action = trig.get("action")

        idx = next(
            (i for i, s in enumerate(strategies) if str(s.get("id")) == strategy_id),
            None,
        )
        if idx is None:
            raise PreventUpdate

        target = dict(strategies[idx])
        store = dict(target.get("conditions_store", {"buy": 1, "sell": 1}))
        if cond not in store:
            store[cond] = 1

        if action == "add":
            store[cond] += 1
        elif action == "remove" and store[cond] > 1:
            store[cond] -= 1
        elif action == "clear":
            store[cond] = 1

        target["conditions_store"] = store
        strategies = strategies.copy()
        strategies[idx] = target

        if len(strategies) > 1:
            style = {"display": "block"}
        return strategies, style

    # --- UPDATE NAMES ---
    if isinstance(trig, dict) and trig.get("type") == "strategy_name_input":
        updated = strategies.copy()
        for i, strat in enumerate(updated):
            if i < len(names) and names[i] is not None:
                strat["name"] = names[i]
        if len(updated) > 1:
            style = {"display": "block"}
        return updated, style

    # fallback
    if len(strategies) > 1:
        style = {"display": "block"}
    return strategies, style


@strategies_app.callback(
    Output("param_instances", "data"),
    Output("stored_inputs", "data"),
    # события
    Input("dropdown_indicators", "value"),  # <— твой дропдаун
    Input({"type": "add_param", "indicator": ALL}, "n_clicks"),
    Input({"type": "remove_param", "indicator": ALL}, "n_clicks"),
    Input({"type": "clear_param", "indicator": ALL}, "n_clicks"),
    Input("clear_all_global", "n_clicks"),  # глобальный Clear All
    Input({"type": "param_input", "id": ALL}, "value"),
    # состояния
    State({"type": "param_input", "id": ALL}, "id"),
    State("param_instances", "data"),
    State("stored_inputs", "data"),
    prevent_initial_call=False,  # ВАЖНО: разрешаем старт
)
def sync_all(
    selected_indicators,
    add_clicks,
    remove_clicks,
    clear_clicks,
    clear_all_global,
    values,
    value_ids,
    param_instances,
    stored_inputs,
):
    param_instances = (param_instances or {}).copy()
    stored_inputs = (stored_inputs or {}).copy()

    # Унифицированный парсер «что нас триггернуло»
    tid = getattr(ctx, "triggered_id", None)  # Dash>=2.9
    if tid is None:
        # Старые версии Dash
        trg = ctx.triggered
        if not trg:
            # INIT: первый вызов без явного триггера — заведём счётчики из дропдауна
            selected = as_selected_set(selected_indicators)
            new_counts = {i: int(param_instances.get(i, 1) or 1) for i in selected}
            return new_counts, stored_inputs
        raw = trg[0]["prop_id"].split(".")[0]
        if raw == "dropdown_indicators":
            tid = "dropdown_indicators"
        elif raw == "clear_all_global":
            tid = "clear_all_global"
        elif raw.startswith("{"):
            try:
                tid = json.loads(raw)
            except Exception:
                raise PreventUpdate
        else:
            raise PreventUpdate

    # ---------- Глобальный Clear All ----------
    if tid == "clear_all_global":
        selected = as_selected_set(selected_indicators)
        return (
            {i: 1 for i in selected},
            {},
        )  # 1 инстанс на каждый выбранный индикатор, store пустой

    # ---------- Dropdown ----------
    if tid == "dropdown_indicators":
        selected = as_selected_set(selected_indicators)
        new_counts = {i: int(param_instances.get(i, 1) or 1) for i in selected}
        # чистим значения удалённых индикаторов
        removed = set(param_instances.keys()) - selected
        for r in removed:
            stored_inputs = delete_indicator_keys(stored_inputs, r)
        return new_counts, stored_inputs

    # ---------- Pattern IDs ----------
    if isinstance(tid, dict):
        t = tid.get("type")

        # Ввод в поля
        if t == "param_input":
            new_store = stored_inputs.copy()
            for id_, val in zip(value_ids, values):
                key = id_.get("id") if isinstance(id_, dict) else None
                if key is not None:
                    new_store[key] = val
            return param_instances, new_store

        # Кнопки + / - / clear (локальные)
        ind = tid.get("indicator")
        if not ind:
            raise PreventUpdate

        cnt = int(param_instances.get(ind, 1) or 1)

        if t == "add_param":
            param_instances[ind] = cnt + 1
            return param_instances, stored_inputs

        if t == "remove_param":
            if cnt > 1:
                stored_inputs = delete_instance_keys(stored_inputs, ind, cnt)
                param_instances[ind] = cnt - 1
            return param_instances, stored_inputs

        if t == "clear_param":
            stored_inputs = delete_indicator_keys(stored_inputs, ind)
            param_instances[ind] = 1
            return param_instances, stored_inputs

    # Ничего подходящего — без изменений
    return param_instances, stored_inputs


@strategies_app.callback(
    Output("input_parameters_for_indicators", "children"),
    Output("indicator_inputs_ready", "data"),
    # Output('card_indicators_input', 'style'),
    Input("param_instances", "data"),
    State("stored_inputs", "data"),
    prevent_initial_call=False,  # важно, чтобы карточка могла появиться сразу
)
def generate_indicator_inputs(param_instances, stored_data):
    # Нет выбранных индикаторов / нет счётчиков — нечего рисовать
    if not param_instances:
        return [], {"display": "none"}

    stored_data = stored_data or {}
    all_cards = []
    has_any_input = False  # флаг: есть ли хотя бы одно поле ввода

    for indicator, count in param_instances.items():
        # Берём параметры для индикатора
        df_selected = df_input_parameters[df_input_parameters["indicator"] == indicator]
        df_selected = df_selected[df_selected["input_name"] != "no_parameters"]
        if df_selected.empty:
            # у этого индикатора нет полей — пропускаем
            continue

        card_body = [
            html.H5(f"{indicator} Parameters", className="card-title text-center")
        ]
        # Инстансы (1..count)
        for instance_num in range(1, count + 1):
            card_body.append(html.H6(f"Instance {instance_num}", className="mt-3"))

            for _, row in df_selected.iterrows():
                param = row["input_name"]
                input_type = row["input_type"]

                dash_input_type = "text"
                if input_type in ["int", "float", "bool"]:
                    dash_input_type = "number"

                placeholder = {
                    "int": f"{param}, e.g. 1",
                    "float": f"{param}, e.g. 1.0",
                    "bool": f"{param}, 0 or 1",
                }.get(input_type, param)

                input_id_str = f"{indicator}__{instance_num}__{param}"
                wrapper_id = f"wrap__{input_id_str}"
                value = stored_data.get(input_id_str, "")

                # как только добавили хотя бы один input — поднимем флаг
                has_any_input = True

                card_body.append(
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Input(
                                        id={"type": "param_input", "id": input_id_str},
                                        placeholder=placeholder,
                                        type=dash_input_type,
                                        className="form-control",
                                        value=value,
                                        persistence=True,
                                        persistence_type="memory",
                                    ),
                                ],
                                id=wrapper_id,
                            )
                        ],
                        className="mb-2",
                    )
                )

        # Кнопки внутри карточки
        buttons = [
            dmc.Button(
                "Add",
                id={"type": "add_param", "indicator": indicator},
                n_clicks=0,
                color="green",
                size="xs",
            ),
            dmc.Button(
                f"Clear {indicator}",
                id={"type": "clear_param", "indicator": indicator},
                n_clicks=0,
                color="gray",
                size="xs",
                variant="light",
            ),
        ]

        if count > 1:
            buttons.append(
                dmc.Button(
                    "Remove",
                    id={"type": "remove_param", "indicator": indicator},
                    n_clicks=0,
                    color="red",
                    size="xs",
                )
            )

        card_body.append(
            dmc.Group(
                buttons,
                justify="space-between",  # равномерно по краям
                gap="md",
                style={"marginBottom": "20px"},
            )
        )

        all_cards.append(
            dmc.Card(
                dmc.CardSection(card_body),
                shadow="sm",
                radius="md",
                withBorder=True,
                style={"marginBottom": "20px"},
            )
        )

        if not has_any_input:
            return [], False

    return all_cards, True


@strategies_app.callback(
    [
        Output("graph_coin_div", "children"),
        Output("graph_strategy_div", "children"),
        Output("graphs_indicators", "children"),
        Output("header", "children"),
        Output("no_data_message", "style"),
    ],
    [
        Input("dropdown_coin", "value"),
        Input("dropdown_indicators", "value"),
        Input("date_picker", "start_date"),
        Input("date_picker", "end_date"),
        Input("dropdown_interval", "value"),
        Input("submit_button", "n_clicks"),
    ],
    [
        State("stored_inputs", "data"),
        State("conditions_store_inputs", "data"),
        State("strategies_store", "data"),
    ],
)
def create_charts(
    ticker,
    indicators,
    start,
    end,
    interval,
    clicks,
    stored_inputs,
    conditions_store_inputs,
    strategies,
):
    print("CHART-----------------------")
    print("conditions_store_inputs", conditions_store_inputs)
    print("stored_inputs", stored_inputs)
    if clicks == d["click"]:
        return [], [], [], [], {"display": "none"}
    d["click"] = clicks
    conditions_store_inputs = replace_ids_with_names(
        conditions_store_inputs, strategies
    )
    # print(stored_inputs)
    kwargs = group_params(stored_inputs) if stored_inputs else {}
    # print(kwargs)
    coin = Coin(ticker, start, end, interval)
    if len(coin.data) == 0:
        return [], [], [], [], {"visibility": "visible"}

    # Бэктест (дедуп имён индикаторов делается внутри backtest_all_strategies)
    results, df, added_cols = Indicator.backtest_all_strategies(
        df=coin.data.copy(),
        conditions=conditions_store_inputs or {},
        indicator_names=indicators or [],
        kwargs_map=kwargs,
        dict_operators=dict_ops,
        debug=True,
    )

    # ---------- Цвета ----------
    strategy_colors = itertools.cycle(pc.qualitative.Set1 + pc.qualitative.Set2)
    indicator_colors = itertools.cycle(pc.qualitative.Plotly)
    strat_color_map = {sid: next(strategy_colors) for sid in results.keys()}
    ind_color_map = {
        col: next(indicator_colors)
        for _, cols in (added_cols or {}).items()
        for col in cols
    }

    # --- График монеты ---
    fig_coin = go.Figure()
    fig_coin.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
        )
    )
    fig_coin.update_layout(
        title=f"Candlestick chart of {ticker} price",
        xaxis_title="Date",
        yaxis_title="Price",
    )
    coin_component = dcc.Graph(id="graph_coin", figure=fig_coin)

    # --- График стратегий ---
    fig_strategy = go.Figure()
    df["Buy_Hold_Cumulative_Return"] = (df["Close"] / df["Close"].iloc[0]) - 1
    fig_strategy.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Buy_Hold_Cumulative_Return"],
            name="Buy & Hold",
            line=dict(color="orange", width=2),
        )
    )
    for sid, res in results.items():
        cum_col = res["cum_returns_column"]
        deal_col = res["deal_column"]
        color = strat_color_map[sid]
        fig_strategy.add_trace(
            go.Scatter(
                x=df.index,
                y=df[cum_col],
                name=f"Strategy: {sid}",
                line=dict(width=2, color=color),
            )
        )
        # buy/sell маркеры
        fig_strategy.add_trace(
            go.Scatter(
                x=df.loc[df[deal_col] == 1].index,
                y=df.loc[df[deal_col] == 1][cum_col],
                mode="markers",
                name=f"{sid} buy",
                marker=dict(color="green", size=7),
            )
        )
        fig_strategy.add_trace(
            go.Scatter(
                x=df.loc[df[deal_col] == -1].index,
                y=df.loc[df[deal_col] == -1][cum_col],
                mode="markers",
                name=f"{sid} sell",
                marker=dict(color="red", size=7),
            )
        )
    fig_strategy.update_layout(
        title="Graph of cumulative returns",
        xaxis_title="Date",
        yaxis_title="Cumulative Return",
    )

    # --- Сводная таблица по стратегиям (если они есть) ---
    summary_component = None
    if results:
        # соберём метрики
        rows = []
        n_periods = int(df["Close"].count()) if df["Close"].count() else 0
        for sid, res in results.items():
            cum_col = res["cum_returns_column"]
            # ret_col = res['returns_column']
            deal_col = res["deal_column"]

            cum = df[cum_col].astype(float)
            final_factor = float(cum.iloc[-1]) if len(cum) else 1.0
            total_return = final_factor - 1.0
            # CAGR согласуем с 252 из твоего бэктеста
            cagr = (final_factor ** (252.0 / n_periods) - 1.0) if n_periods > 0 else 0.0
            max_dd = float((cum / cum.cummax() - 1.0).min()) if len(cum) else 0.0
            buys = int((df[deal_col] == 1).sum()) if deal_col in df.columns else 0
            sells = int((df[deal_col] == -1).sum()) if deal_col in df.columns else 0

            rows.append(
                {
                    "Strategy": sid,
                    "Final Balance": res["final_balance"],
                    "Total Return %": total_return,
                    "CAGR %": cagr,
                    "Sharpe": res["sharpe_ratio"],
                    "Sortino": res["sortino_ratio"],
                    "Max Drawdown %": max_dd,
                    "Buys": buys,
                    "Sells": sells,
                }
            )

        # формируем колонки для таблицы
        strategies = [r["Strategy"] for r in rows]
        final_bal = [f"{r['Final Balance']:,.2f}" for r in rows]
        total_ret = [r["Total Return %"] for r in rows]
        cagr_vals = [r["CAGR %"] for r in rows]
        sharpe = [r["Sharpe"] for r in rows]
        sortino = [r["Sortino"] for r in rows]
        maxdd = [r["Max Drawdown %"] for r in rows]
        buys = [r["Buys"] for r in rows]
        sells = [r["Sells"] for r in rows]

        # текста для процентов
        total_ret_txt = [_fmt_pct(x) for x in total_ret]
        cagr_txt = [_fmt_pct(x) for x in cagr_vals]
        maxdd_txt = [_fmt_pct(x) for x in maxdd]

        # цвета фона для важного
        sharpe_bg = [_color_scale_number(x, good_high=True) for x in sharpe]
        sortino_bg = [_color_scale_number(x, good_high=True) for x in sortino]
        ret_bg = [
            _color_scale_number(x, good_high=True, thr_good=0.25, thr_ok=0.05)
            for x in total_ret
        ]
        cagr_bg = [
            _color_scale_number(x, good_high=True, thr_good=0.20, thr_ok=0.05)
            for x in cagr_vals
        ]
        maxdd_bg = [_color_scale_number(x, good_high=False) for x in maxdd]

        header_vals = [
            "Strategy",
            "Final Balance",
            "Total Return",
            "CAGR",
            "Sharpe",
            "Sortino",
            "Max DD",
            "Buys",
            "Sells",
        ]
        cell_vals = [
            strategies,
            final_bal,
            total_ret_txt,
            cagr_txt,
            [f"{x:.2f}" for x in sharpe],
            [f"{x:.2f}" for x in sortino],
            maxdd_txt,
            buys,
            sells,
        ]

        # для разных колонок дадим собственный фон
        col_bg = [
            ["white"] * len(strategies),  # Strategy
            ["white"] * len(strategies),  # Final Balance
            ret_bg,  # Total Return
            cagr_bg,  # CAGR
            sharpe_bg,  # Sharpe
            sortino_bg,  # Sortino
            maxdd_bg,  # Max DD
            ["white"] * len(strategies),  # Buys
            ["white"] * len(strategies),  # Sells
        ]

        fig_summary = go.Figure(
            data=[
                go.Table(
                    columnorder=list(range(1, len(header_vals) + 1)),
                    columnwidth=[80, 90, 90, 80, 70, 70, 90, 60, 60],
                    header=dict(
                        values=header_vals,
                        fill_color="#f0f2f6",
                        align="left",
                        font=dict(color="#2a2f45", size=13),
                    ),
                    cells=dict(
                        values=cell_vals,
                        fill_color=col_bg,
                        align="left",
                        font=dict(size=12),
                        height=26,
                    ),
                )
            ]
        )
        fig_summary.update_layout(
            margin=dict(l=0, r=0, t=8, b=8),
            autosize=True,
            height=40 + 28 * len(strategies),
        )

        summary_component = dcc.Graph(
            id="strategy_summary",
            figure=fig_summary,
            config={"displayModeBar": False},
            style={"marginBottom": "0px", "paddingBottom": "0px"},
        )

    # --- Header ---
    if not results:
        header = "Performance: Buy & Hold"
    elif len(results) == 1:
        header = f"Performance: Strategy {list(results.keys())[0]} vs Buy & Hold"
    else:
        header = f"Performance: Strategies {', '.join(results.keys())} vs Buy & Hold"

    # --- Графики индикаторов ---
    children_indicators = []
    for ind, cols in (added_cols or {}).items():
        for col in cols:
            fig_indicator = go.Figure()
            fig_indicator.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[col],
                    name=f"Indicator {ind}",
                    line=dict(width=2, color=ind_color_map[col]),
                )
            )
            fig_indicator.update_layout(
                title=f"Graph of {col}", xaxis_title="Date", yaxis_title=col
            )
            children_indicators.append(
                dcc.Graph(id=f"graph_{col}", figure=fig_indicator)
            )

    # собираем блок стратегии (график + таблица)
    if summary_component is not None:
        strategy_children = html.Div(
            [
                summary_component,
                dcc.Graph(
                    id="graph_strategy",
                    figure=fig_strategy,
                    style={"marginTop": "0px", "paddingTop": "0px"},
                ),
            ],
            style={"marginBottom": "0px", "paddingBottom": "0px"},
        )
    else:
        strategy_children = dcc.Graph(id="graph_strategy", figure=fig_strategy)

    return (
        coin_component,
        strategy_children,
        children_indicators,
        header,
        {"visibility": "hidden"},
    )


secured_strategies_app = AuthMiddleware(strategies_app.server)
