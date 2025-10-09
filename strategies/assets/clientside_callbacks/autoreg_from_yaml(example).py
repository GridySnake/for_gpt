import yaml
from dash import ClientsideFunction, Input, Output, State


def register_clientside_callbacks1(app, yaml_path="callbacks_clientside.yaml"):
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    for cb in data.get("clientside_callbacks", []):
        func = ClientsideFunction(namespace=cb["namespace"], function_name=cb["id"])
        outputs = [Output(**o) for o in cb["outputs"]] if isinstance(cb["outputs"], list) else [Output(**cb["outputs"])]
        inputs = [Input(**i) for i in cb["inputs"]] if isinstance(cb["inputs"], list) else [Input(**cb["inputs"])]
        states = [State(**s) for s in cb.get("states", [])]

        app.clientside_callback(
            func,
            outputs,
            inputs,
            states if states else None,
            prevent_initial_call=cb.get("prevent_initial_call", False),
        )