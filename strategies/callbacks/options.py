from dash import Input, Output, State, MATCH
from strategies.strategies_helpful_functions import (
    build_options_template,
)
from strategies.strategies_constants import (
    COMPARISON_OPERATORS,
    OHLCV_COLUMNS,
    tooltip_styles,
    df_output_parameters,
)
import dash_mantine_components as dmc


def register_callbacks(app):

    # Отображение кнопок для выбора условий стратегий
    @app.callback(
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
            raw_options=data,  # ← список опций напрямую
            param_source=param_source or {}  # ← словарь напрямую
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
                (conditions_store_inputs or {}).get(store_key, {}).get("column_raw", None)
            )
        elif field_type == "column_or_custom_dropdown":
            selected_value = (
                (conditions_store_inputs or {})
                .get(store_key, {})
                .get("column_or_custom_raw", None)
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

            # если выбран COMPARISON_OPERATORS или OHLCV_COLUMNS или custom
            if selected_value in [i['value'] for i in COMPARISON_OPERATORS] + ['custom'] + list(OHLCV_COLUMNS):
                opt_value = opt.get("value")
                is_selected = (opt_value == selected_value)

            # если выбран индикатор
            elif isinstance(selected_value, str) and "_" in selected_value:
                opt_raw = opt.get("raw")
                is_selected = (opt_raw == selected_value)

            # если ничего не выбрано
            else:
                is_selected = False

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
                "raw": opt.get("raw") or str(opt.get("value") or ""),
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

    # Генератор параметров индикаторов для стратегий
    @app.callback(
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
                df_selected[df_selected["indicator"] == ind]["output_name"].unique().tolist()
            )
            all_options.extend([f"{ind}_{c}" for c in cols])

        # === структурированные опции по инстансам с подстановкой period ===
        param_instances = param_instances or {}
        stored_inputs = stored_inputs or {}
        output_options = []

        for ind in indicators:
            cols = (
                df_selected[df_selected["indicator"] == ind]["output_name"].unique().tolist()
            )
            count = int(param_instances.get(ind, 1) or 1)
            for inst in range(1, count + 1):
                key_period = f"{ind}__{inst}__period"
                period_val = stored_inputs.get(key_period, None)
                if period_val in (None, "", "None"):
                    period_label = "i"
                else:
                    try:
                        period_label = (
                            str(int(period_val)) if float(period_val).is_integer() else str(period_val)
                        )
                    except Exception:
                        period_label = str(period_val)

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
