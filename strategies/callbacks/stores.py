from dash import Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate
from strategies.strategies_helpful_functions import (
    delete_instance_keys,
    delete_indicator_keys,
    as_selected_set,
    prune_by_alive_strategies,
    handle_input_groups,
    handle_clear_all,
    handle_clear_strategy,
    handle_modify_condition,
    handle_option_button_click,
    is_noop_trigger,
)
import json


def register_callbacks(app):

    # Сохраняем информацию о выбранных условиях в стратегиях
    @app.callback(
        Output('conditions_store_inputs', 'data'),
        [
            Input(
                {'type': 'option-btn', 'strategy': ALL, 'condition': ALL, 'index': ALL, 'field_type': ALL, 'value': ALL,
                 'label': ALL, "raw": ALL}, 'n_clicks'),
            Input({'type': 'comparison_operator', 'strategy': ALL, 'condition': ALL, 'index': ALL}, 'value'),
            Input({'type': 'column_or_custom_dropdown', 'strategy': ALL, 'condition': ALL, 'index': ALL}, 'value'),
            Input({'type': 'custom_input', 'strategy': ALL, 'condition': ALL, 'index': ALL}, 'value'),
            Input({'type': 'modify_condition', 'strategy': ALL, 'action': ALL, 'condition': ALL}, 'n_clicks'),
            Input({'type': 'clear_all_conditions', 'strategy': ALL}, 'n_clicks'),
            Input({'type': 'clear_strategy', 'strategy': ALL}, 'n_clicks'),
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
            clear_strategy_clicks,
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
            return handle_clear_all()

        # --- CLEAR STRATEGY ---
        if isinstance(trig, dict) and trig.get('type') == 'clear_strategy':
            return handle_clear_strategy(stored_data, trig)

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

    # Сохраняем кол-во стратегий и кол-во условий в стратегиях
    @app.callback(
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
            for i, strategy in enumerate(updated):
                if i < len(names) and names[i] is not None:
                    strategy["name"] = names[i]
            if len(updated) > 1:
                style = {"display": "block"}
            return updated, style

        # fallback
        if len(strategies) > 1:
            style = {"display": "block"}
        return strategies, style

    # Сохраняем Кол-во инстансов у индикаторов и введенные значения параметров индикаторов
    @app.callback(
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
