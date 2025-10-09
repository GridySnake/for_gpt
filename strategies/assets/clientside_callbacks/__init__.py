from dash import ClientsideFunction, Input, Output, State, ALL, MATCH


def register_clientside_callbacks(app):
    """Регистрирует все client-side колбеки для Strategies app"""

    # === Мгновенное открытие/закрытие popover ===
    app.clientside_callback(
        ClientsideFunction(namespace="ui", function_name="popoverOpenCloseLabel"),
        [
            Output({"type": MATCH, "strategy": MATCH, "condition": MATCH, "index": MATCH, "role": "popover"}, "opened"),
            Output({"type": MATCH, "strategy": MATCH, "condition": MATCH, "index": MATCH, "role": "input"}, "children"),
        ],
        [
            Input({"type": MATCH, "strategy": MATCH, "condition": MATCH, "index": MATCH, "role": "input"}, "n_clicks"),
            Input({"type": "option-btn", "strategy": MATCH, "condition": MATCH, "index": MATCH, "value": ALL, "label": ALL, "raw": ALL}, "n_clicks"),
            Input("conditions_store_inputs", "data"),
        ],
        [
            State({"type": MATCH, "strategy": MATCH, "condition": MATCH, "index": MATCH, "role": "input"}, "id"),
            State({"type": MATCH, "strategy": MATCH, "condition": MATCH, "index": MATCH, "role": "input"}, "children"),
        ],
    )

    # === Защита от раннего отображения ===
    app.clientside_callback(
        ClientsideFunction(namespace="ui", function_name="preventShow"),
        Output("column_2", "style"),
        [
            Input("indicator_inputs_ready", "data"),
            Input("input_parameters_for_indicators", "children"),
        ],
    )

    # === Показ колонок при выборе индикаторов ===
    app.clientside_callback(
        ClientsideFunction(namespace="ui", function_name="showIndStrategy"),
        Output("column_3", "style"),
        Input("dropdown_indicators", "value"),
    )

    # === Очистка параметров первой колонки ===
    app.clientside_callback(
        ClientsideFunction(namespace="data", function_name="clearColumn1"),
        [
            Output("dropdown_coin", "value"),
            Output("date_picker", "start_date"),
            Output("date_picker", "end_date"),
            Output("dropdown_interval", "value"),
            Output("dropdown_indicators", "value"),
        ],
        Input("clear_all_strategy_parameters", "n_clicks"),
        prevent_initial_call=True,
    )
