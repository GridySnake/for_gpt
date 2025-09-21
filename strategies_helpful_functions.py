from __future__ import annotations
import operator
import pandas as pd
from collections import defaultdict
from typing import Any, Dict, List, Optional
from dash import ctx
from dash.exceptions import PreventUpdate
import os
from dash import html
import dash_mantine_components as dmc
from pages_apps.strategies_generate_blocks_functions import generate_conditions_block_group, OHLCV_COLUMNS

try:
    from strategies_generate_blocks_functions import build_options_template as _build_options_template  # noqa
except Exception:
    _build_options_template = None

try:
    from strategies_generate_blocks_functions import build_param_source as _build_param_source  # noqa
except Exception:
    _build_param_source = None

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


def group_params(params_dict):
    tmp = defaultdict(lambda: defaultdict(dict))

    for k, v in params_dict.items():
        # ожидаем ключи вида IND__INST__PARAM
        try:
            ind, inst, param = k.split('__', 2)
        except ValueError:
            continue  # пропускаем некорректные ключи

        # игнорируем "пустые" значения: '', None, строки из пробелов
        if v is None or (isinstance(v, str) and v.strip() == ''):
            # при этом фиксируем наличие параметра, чтобы получить []
            _ = tmp[ind][param]
            continue

        tmp[ind][param][int(inst)] = v  # храним по инстансу (для упорядочивания)

    # финализация: сортируем по номеру инстанса и собираем списки значений
    grouped = {
        ind: {
            param: [vals[i] for i in sorted(vals)]
            for param, vals in params_by_param.items()
        }
        for ind, params_by_param in tmp.items()
    }
    return grouped


# Вспомогательная: максимальный индекс карточек в UI для заданных strategy/condition
def _max_ui_index_for(sid: str, cond: str) -> int:
    indices = []
    # первые 4 группы — соответствуют dropdown/input полям
    for group in ctx.inputs_list[:4]:
        for input_info in group:
            comp_id = input_info['id']
            if isinstance(comp_id, dict) \
               and str(comp_id.get('strategy')) == sid \
               and comp_id.get('condition') == cond:
                try:
                    indices.append(int(comp_id.get('index')))
                except (TypeError, ValueError):
                    pass
    return max(indices) if indices else 0  # если на UI осталась только первая карточка -> индекс 0


def remove_(condition_dict):
    condition_dict = {
        k: {j: v[j].split('_', 1)[1] if j in ['column', 'column_or_custom'] and '_' in v[j] else val
            for j, val in v.items()}
        for k, v in condition_dict.items()
    }
    return condition_dict


def get_params_for_indicator(indicator):
    df_sel = df_input_parameters[
        (df_input_parameters['indicator'] == indicator) &
        (df_input_parameters['input_name'] != 'no_parameters')
    ]
    return df_sel[['input_name', 'input_type', 'description']].to_dict('records')


def delete_instance_keys(stored: dict, indicator: str, inst_num: int) -> dict:
    if not stored:
        return {}
    pref = f"{indicator}__{inst_num}__"
    return {k: v for k, v in stored.items() if not k.startswith(pref)}

def delete_indicator_keys(stored: dict, indicator: str) -> dict:
    if not stored:
        return {}
    pref = f"{indicator}__"
    return {k: v for k, v in stored.items() if not k.startswith(pref)}

def as_selected_set(val):
    if val is None:
        return set()
    if isinstance(val, (list, tuple, set)):
        return set(val)
    return {val}

def filter_to_selected_indicators(stored: dict, selected: set) -> dict:
    """Оставить только ключи для выбранных индикаторов."""
    if not stored:
        return {}
    out = {}
    for k, v in stored.items():
        try:
            ind, inst, param = k.split("__", 2)
        except ValueError:
            # Некорректный ключ — пропускаем
            continue
        if ind in selected:
            out[k] = v
    return out


def _fmt_pct(x, digits=2):
    try:
        return f"{x*100:.{digits}f}%"
    except Exception:
        return "—"


def _color_scale_number(x, good_high=True, thr_good=None, thr_ok=None):
    """
    Возвращает цвет фона ячейки под метрику:
    - good_high=True: больше — лучше (Sharpe, Sortino, Return, CAGR)
    - good_high=False: меньше (по модулю) — лучше (MaxDD — более высокий отрицательный хуже)
    Пороговые уровни можно задать. Если не заданы — используются разумные дефолты.
    """
    if thr_good is None and thr_ok is None:
        if good_high:
            thr_good, thr_ok = 1.5, 0.5  # для Sharpe/Sortino
        else:
            thr_good, thr_ok = -0.15, -0.30  # для MaxDD (порог по убыванию)
    # нормировка логики
    if good_high:
        if x is None:
            return "#f2f2f2"
        return "#d4f7d0" if x >= thr_good else ("#fff5cc" if x >= thr_ok else "#ffd6d6")
    else:
        if x is None:
            return "#f2f2f2"
        return "#d4f7d0" if x >= thr_good else ("#fff5cc" if x >= thr_ok else "#ffd6d6")


def extract_indicator_params(tp: dict) -> dict:
    tp = tp or {}
    # самые частые варианты ключей
    for k in ('indicator_params', 'indicators', 'indicators_params', 'params_map'):
        v = tp.get(k)
        if isinstance(v, dict):
            return v
    # иногда приходит списком вида [{'name': 'CCI', 'params': {...}}, ...]
    ind_list = tp.get('indicators')
    if isinstance(ind_list, list):
        out = {}
        for item in ind_list:
            name = (item or {}).get('name') or item.get('key') or item.get('id')
            params = (item or {}).get('params') or item.get('values')
            if name and isinstance(params, dict):
                out[name] = params
        if out:
            return out
    return {}


def replace_ids_with_names(conditions_store_inputs, strategies):
    """
    Заменяет id стратегий на их name только в conditions_store_inputs.
    stored_inputs оставляем как есть (для group_params).
    """
    # строим маппинг id -> name
    id_to_name = {str(s['id']): s.get('name', str(s['id'])) for s in strategies}

    # обновляем conditions_store_inputs
    new_conditions = {}
    for key, val in conditions_store_inputs.items():
        parts = key.split("_", 1)  # разделяем только первый "_"
        if parts[0] in id_to_name:
            new_key = id_to_name[parts[0]] + "_" + parts[1]
        else:
            new_key = key
        new_conditions[new_key] = val

    return new_conditions


def _make_key(sid: str | int, cond: str, idx: str | int) -> str:
    """Единый формат ключа, используемый в проекте."""
    return f"{sid}_{cond}_{idx}"


def _ensure_bucket(store: Store, key: Key) -> None:
    """Создаёт пустой словарь под ключом, если его ещё нет (in-place)."""
    store.setdefault(key, {})


def build_output_options(indicators_data: dict | None) -> list[dict]:
    """
    Генерирует список опций для дропдаунов Column/Value.

    indicators_data – словарь из стора с выбранными индикаторами
    (ключ = имя индикатора, значение = список/словарь параметров).
    Если стор пустой, возвращаются только стандартные OHLCV-колонки.

    Возвращает список словарей вида {"label": "...", "value": "..."}.
    """
    options: list[dict] = []

    # Базовые OHLCV
    for col in OHLCV_COLUMNS:
        options.append({"label": col.upper(), "value": col})

    if not indicators_data:
        return options

    # Добавляем индикаторы и их параметры
    for ind_name, ind_cfg in indicators_data.items():
        # Если индикатор без параметров
        if isinstance(ind_cfg, (str, int)) or ind_cfg is None:
            options.append({"label": f"{ind_name}", "value": ind_name})
            continue

        # Если индикатор содержит несколько инстансов/параметров
        if isinstance(ind_cfg, dict):
            for inst, params in ind_cfg.items():
                label = f"{ind_name} ({inst})" if inst else ind_name
                options.append({"label": label, "value": f"{ind_name}_{inst}"})
        elif isinstance(ind_cfg, list):
            for inst in ind_cfg:
                label = f"{ind_name} ({inst})"
                options.append({"label": label, "value": f"{ind_name}_{inst}"})

    return options


def is_noop_trigger() -> bool:
    """
    True, если текущее событие не несёт полезного значения:
    - None, '' или 0 (повторяет существующую «защиту»).
    """
    trig = getattr(ctx, "triggered", None)
    if not trig:
        return True
    val = trig[0].get("value", None)
    return val in (None, "", 0)


def handle_clear_all(stored_data: Store) -> Store:
    """Полная очистка ввода условий."""
    return {"1_buy_0": {}, "1_sell_0": {}}


def handle_modify_condition(stored_data: dict, trig: dict) -> dict:
    """
    {'type': 'modify_condition', 'action': 'clear'|'remove'|'add', 'strategy': sid, 'condition': cond}
    - clear: удалить все записи по префиксу sid_cond_
    - remove: удалить запись с максимальным UI-индексом
    - add:    добавить пустую запись с индексом (max+1) или 0, если ничего нет
    """
    if not ctx.triggered or not ctx.triggered[0].get("value"):
        raise PreventUpdate

    new_store = dict(stored_data or {})
    sid = str(trig.get("strategy"))
    cond = trig.get("condition")
    action = trig.get("action")

    if action == "clear":
        prefix = f"{sid}_{cond}_"
        for k in list(new_store.keys()):
            if isinstance(k, str) and k.startswith(prefix):
                if k.endswith("_0"):
                    continue
                new_store.pop(k, None)
        return new_store

    if action == "remove":
        last_idx = _max_index_in_store(new_store, sid, cond)
        if last_idx is not None:
            new_store.pop(_make_key(sid, cond, last_idx), None)
        return new_store

    if action == "add":
        last_idx = _max_index_in_store(new_store, sid, cond)
        if last_idx is None:
            # первый раз: создаём 0 и placeholder 1
            new_store[_make_key(sid, cond, 0)] = {}
        else:
            new_store[_make_key(sid, cond, last_idx + 1)] = {}
        return new_store

    return new_store


def handle_option_button_click(stored_data: Store, trig: dict) -> Store:
    """
    Клик по элементу-опции popover:
    id = {
      "type": "option-btn",
      "strategy": sid, "condition": cond, "index": idx,
      "field_type": "column_dropdown" | "column_or_custom_dropdown" | "comparison_operator" | ...
      "value": any, "label": str
    }
    """
    new_store: Store = dict(stored_data or {})

    sid = str(trig.get("strategy"))
    cond = trig.get("condition")
    idx = trig.get("index")
    ftype = trig.get("field_type")
    value = trig.get("value")
    label = trig.get("label")

    key = _make_key(sid, cond, idx)
    _ensure_bucket(new_store, key)

    # ВАЖНО: сохраняем те же названия полей, что и в текущем коде
    if ftype == "column_dropdown":
        new_store[key]["column"] = value
        new_store[key]["column_label"] = label
    elif ftype == "column_or_custom_dropdown":
        new_store[key]["column_or_custom"] = value
        new_store[key]["column_or_custom_label"] = label
    elif ftype == "comparison_operator":
        new_store[key]["comparison_operator"] = value
        new_store[key]["comparison_operator_label"] = label
    else:
        # fallback — на случай новых типов
        new_store[key]["value"] = value
        new_store[key]["label"] = label

    return new_store


def handle_input_groups(
    stored_data: Store,
    operator_values: List[Any],
    right_values: List[Any],
    custom_values: List[Any],
) -> Store:
    """
    Обработка обычных контролов (не popover-кнопок).
    В исходнике берётся ctx.inputs_list[1:4] — следуем ему для совместимости:
        1: comparison_operator values
        2: column_or_custom_dropdown values
        3: custom_input values
    """
    new_store: Store = dict(stored_data or {})

    # ctx.inputs_list — список групп инпутов c их id
    # Берём 1..3 элементы, как сделано в оригинале
    input_groups_meta = ctx.inputs_list[1:4]
    values_groups = [operator_values, right_values, custom_values]

    for group_meta, values in zip(input_groups_meta, values_groups):
        for input_info, value in zip(group_meta, values):
            comp_id = input_info.get("id")
            if not isinstance(comp_id, dict):
                continue

            sid = str(comp_id.get("strategy"))
            condition = comp_id.get("condition")
            index = comp_id.get("index")
            typ = comp_id.get("type")

            key = _make_key(sid, condition, index)
            _ensure_bucket(new_store, key)

            # ИМЕННО ТАК ЖЕ, как в исходном коде:
            if typ == "comparison_operator":
                new_store[key]["operator"] = value
            elif typ == "column_or_custom_dropdown":
                new_store[key]["column_or_custom"] = value
            elif typ == "custom_input":
                new_store[key]["custom"] = value

    return new_store


def prune_by_alive_strategies(stored_data: Store, strategies: StrategyList | None) -> Store:
    """
    Фильтрует значения по «живым» стратегиям:
      оставляем только те ключи, чей префикс sid_ принадлежит списку strategies.
    Совпадает с текущей логикой.
    """
    if not strategies:
        return stored_data or {}

    alive_ids = {str(s.get("id")) for s in (strategies or [])}
    filtered: Store = {
        k: v for k, v in (stored_data or {}).items() if k.split("_", 1)[0] in alive_ids
    }
    return filtered


def _coerce_sid(sid: str) -> int | str:
    """Пытаемся превратить sid в int, если это число; иначе возвращаем как есть."""
    try:
        return int(sid)
    except Exception:
        return sid


def _max_index_in_store(
    stored_data: Dict[str, Dict[str, Any]] | None, sid: str, side: str
) -> Optional[int]:
    if not stored_data:
        return None
    prefix = f"{sid}_{side}_"
    max_idx: Optional[int] = None
    for k in stored_data.keys():
        if isinstance(k, str) and k.startswith(prefix):
            try:
                idx = int(k.rsplit("_", 1)[-1])
            except ValueError:
                continue
            if max_idx is None or idx > max_idx:
                max_idx = idx
    return max_idx


def _row_count_for_side(stored_data: dict | None, sid: str, side: str, min_rows: int = 1) -> int:
    if not stored_data:
        return min_rows

    prefix = f"{sid}_{side}_"
    # ищем максимальный индекс среди ВСЕХ ключей, даже если значение пустое
    idxs = []
    for k in stored_data.keys():
        if isinstance(k, str) and k.startswith(prefix):
            try:
                idxs.append(int(k.rsplit("_", 1)[-1]))
            except ValueError:
                continue
    if not idxs:
        return min_rows

    return max(max(idxs) + 1, min_rows)


def _strategy_header(s: Dict[str, Any]) -> html.Div:
    sid = str(s.get("id"))
    strategy_name = s.get("name") if s.get("name") != sid and sid != '1' else f"Strategy {sid}"
    return dmc.Group(
        [
            dmc.TextInput(
                id={'type': 'strategy_name_input', 'strategy': sid},
                value=strategy_name,
                placeholder=f"Strategy name",
                size="sm",
                style={'width': '200px', 'display': 'inline-block'}
            ),
            dmc.Group(
                [
                    dmc.Button(
                        f"Clear strategy",
                        id={"type": "clear_all_conditions", "strategy": sid},
                        color="gray",
                        variant="light",
                        size="xs"
                    ),
                    # Если есть обработчик удаления стратегии — раскомментируй:
                    # dmc.Button(
                    #     "Удалить стратегию",
                    #     id={"type": "remove_strategy", "strategy": sid},
                    #     variant="light",
                    #     color="red",
                    #     size="xs",
                    # ),
                ],
                gap="xs",
            ),
        ],
        justify="space-between",
    )


# def _side_header_actions(sid: str, side: str) -> html.Div:
#     return dmc.Group(
#         [
#             dmc.Button(
#                 "Remove",
#                 id={"type": "modify_condition", "strategy": sid, "action": "remove", "condition": side},
#                 color="red",
#                 variant="light",
#                 size="xs",
#             ),
#             # dmc.Button(
#             #     "Очистить эту секцию",
#             #     id={"type": "modify_condition", "strategy": sid, "action": "clear", "condition": side},
#             #     color="orange",
#             #     variant="light",
#             #     size="xs",
#             # ),
#         ],
#         gap="xs",
#     )


def _fallback_row_placeholder(sid: str, side: str, idx: int) -> html.Div:
    return dmc.Paper(
        dmc.Group([dmc.Text("Выберите индикатор и оператор…", c="dimmed", size="sm")], gap="xs"),
        withBorder=True,
        radius="sm",
        p="xs",
        shadow="xs",
        id={"type": "condition_row_placeholder", "strategy": sid, "condition": side, "index": idx},
    )


def _build_side_section(
    sid: str,
    side: str,  # 'buy' | 'sell'
    stored_data: dict[str, dict] | None,
    *,
    section_title: str | None = None,
    output_options: list[dict] | None = None,
    param_source
) -> html.Div:
    title = section_title or ("Buy conditions" if side == "buy" else "Sell conditions")
    conditions_count = _row_count_for_side(stored_data, sid, side, min_rows=1)

    rows_blocks = generate_conditions_block_group(
        strategy_id=sid,
        condition_type=side,
        output_options=output_options or [],
        conditions_count=conditions_count,
        selected_values=stored_data or {},
        param_source=param_source,
    )

    if not rows_blocks:
        rows_blocks = [_fallback_row_placeholder(sid, side, 0)]

    # Плоская разметка без дополнительных Stack'ов
    return html.Div(
        children=[
            html.Div(
                children=[
                    dmc.Text(title, fw=600, size="sm"),
                    # _side_header_actions(sid, side),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
            ),
            html.Div(children=rows_blocks),
        ]
    )


def _build_strategy_card(
    s: dict[str, any],
    stored_data: dict[str, dict] | None,
    *,
    output_options: list[dict] | None = None,
    param_source
) -> html.Div:
    sid = str(s.get("id"))

    return dmc.Card(
        children=[
            _strategy_header(s),
            dmc.Divider(variant="dashed", my=0),
            _build_side_section(sid, "buy", stored_data, output_options=output_options, param_source=param_source),
            dmc.Divider(my=0),
            _build_side_section(sid, "sell", stored_data, output_options=output_options, param_source=param_source),
        ],
        withBorder=True,
        radius="md",
        shadow="sm",
        p="md",
        className="strategy-card",  # оставляем старый класс, чтобы сработал ваш style.css
        id={"type": "strategy_card", "strategy": sid},
    )


def generate_all_strategy_cards(
    strategies_store: list[dict] | None,
    conditions_store_inputs: dict[str, dict] | None,
    *,
    output_options: list[dict] | None = None,
    param_source
) -> list:
    strategies = strategies_store or []
    stored_data = conditions_store_inputs or {}

    def _sid_key(x: dict) -> int:
        try:
            return int(x.get("id"))
        except Exception:
            return 0

    return [
        _build_strategy_card(s, stored_data, output_options=output_options, param_source=param_source)
        for s in sorted(strategies, key=_sid_key)
    ]


def build_strategy_render_context(
    tab_parameters: dict | None,
    stored_inputs: dict | None,
) -> tuple[list[dict], dict]:
    """
    Готовит данные для генерации карточек стратегий:
      - output_options: список опций для дропдаунов
      - param_source: источник данных для тултипов/лейблов

    tab_parameters   – данные из tab-parameters-store
    stored_inputs    – данные из stored_inputs (введённые параметры)
    """
    tab_parameters = tab_parameters or {}
    stored_inputs = stored_inputs or {}

    output_options = tab_parameters.get("output_options", [])
    param_source: dict[str, Any] = dict(stored_inputs)

    # Попробуем извлечь карту параметров индикаторов, если есть функция
    try:
        from strategies_generate_blocks_functions import extract_indicator_params
        if tab_parameters:
            indicator_params_map = extract_indicator_params(tab_parameters)
            if indicator_params_map:
                param_source["indicator_params"] = indicator_params_map
    except ImportError:
        pass  # если функции нет, просто пропускаем

    return output_options, param_source