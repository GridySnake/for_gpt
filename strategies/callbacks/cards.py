from dash import html, dcc, Input, Output, State
from strategies.strategies_helpful_functions import (
    generate_all_strategy_cards,
    build_options_template,
)
from strategies.strategies_constants import (
    df_input_parameters,
)
import dash_mantine_components as dmc


def register_callbacks(app):

    # Генерирует карточки стратегий
    @app.callback(
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
        raw_options = (tab_parameters or {}).get("output_options", [])
        param_source_raw = stored_inputs_params or {}
        param_source = param_source_raw if isinstance(param_source_raw, dict) else {}
        output_options = build_options_template(
            raw_options=raw_options,
            param_source=param_source
        )

        if not output_options:
            return []

        return generate_all_strategy_cards(
            strategies_store=strategies,
            conditions_store_inputs=conditions_inputs,
            output_options=output_options,
            param_source=param_source,
        )

    # Генерирует карточки индикаторов
    @app.callback(
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
                    variant="light",
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
