from __future__ import annotations
import operator
import pandas as pd
from collections import defaultdict
from typing import Any, Dict, List, Optional
from dash import ctx
from dash.exceptions import PreventUpdate
import os
from dash import html
# from pages_apps.strategies_generate_blocks_functions import generate_conditions_block_group, OHLCV_COLUMNS, tooltip_styles
from dash import dcc, html
# import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import re
from typing import List, Dict, Optional, Union
from dash_iconify import DashIconify
from functools import lru_cache
import json
# from pages_apps.strategies_helpful_functions import _select_with_tooltip
from pages_apps.strategies_constants import (
    OHLCV_COLUMNS,
    OHLCV_DESCRIPTIONS,
    COMPARISON_OPERATORS,
    tooltip_styles,
    df_input_parameters,
    Key,
    Store,
    StrategyList,
)


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


def handle_clear_all() -> Store:
    """Полная очистка ввода условий."""
    return {"1_buy_0": {}, "1_sell_0": {}}


def handle_clear_strategy(stored_data: Store, trig: dict) -> Store:
    """Очистка выбранной стратегии."""
    if not ctx.triggered or not ctx.triggered[0].get("value"):
        raise PreventUpdate

    new_store = dict(stored_data or {})
    sid = str(trig.get("strategy"))
    for k in list(new_store.keys()):
        if k.startswith(sid):
            if k.endswith("_0"):
                new_store[k] = {}
            else:
                new_store.pop(k, None)
    return new_store


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
                    new_store[k] = {}
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
            new_store[_make_key(sid, cond, 1)] = {}
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
    raw = trig.get("raw")

    key = _make_key(sid, cond, idx)
    _ensure_bucket(new_store, key)

    # ВАЖНО: сохраняем те же названия полей, что и в текущем коде
    if ftype == "column_dropdown":
        new_store[key]["column"] = value
        new_store[key]["column_label"] = label
        new_store[key]["column_raw"] = raw or value
    elif ftype == "column_or_custom_dropdown":
        new_store[key]["column_or_custom"] = value
        new_store[key]["column_or_custom_label"] = label
        new_store[key]["column_or_custom_raw"] = raw or value
    elif ftype == "comparison_operator":
        new_store[key]["comparison_operator"] = value
        new_store[key]["comparison_operator_label"] = label
        new_store[key]["comparison_operator_raw"] = raw or value
    else:
        # fallback — на случай новых типов
        new_store[key]["value"] = value
        new_store[key]["label"] = label
        new_store[key]["raw"] = raw or value
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
                        id={"type": "clear_strategy", "strategy": sid},
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


def transform_option(opt: dict, param_source) -> dict:
    """
    Преобразует одну опцию:
    {'label': 'BBANDS_BB_UPPER',
     'raw': 'BBANDS__1__BB_UPPER'}
    -> {'label': 'BBANDS 1 instance BB_UPPER', ...}
    """
    raw = opt.get("raw", "")
    label = opt.get("label", "")
    value = opt.get("value", label)

    # проверяем формат RAW: NAME__instance__COL
    m = re.match(r"([A-Za-z0-9]+)__([0-9]+)__(.+)", raw)
    if m:
        name, inst, col = m.groups()
        pretty = f"{name} {inst} {col}"
        tooltip = _build_params_tooltip(name, inst, param_source)
        return {
            "label": pretty,
            "value": value,
            "raw": raw,
            "tooltip": tooltip,
        }

    # для OHLCV и Custom оставляем как есть
    tooltip = opt.get("tooltip")
    return {
        "label": label,
        "value": value,
        "raw": raw,
        "tooltip": tooltip,
    }


def _build_params_tooltip(ind_name: str, inst: str, src: dict | None) -> str | None:
    """
    Собирает текст tooltip из param_source.
    Если параметры пусты – просто имя индикатора.
    """
    if not src:
        return ind_name
    prefix = f"{ind_name}__{inst}__"
    params = []
    for key, val in src.items():
        if key.startswith(prefix) and val not in ("", None):
            # берем только часть после префикса
            pname = key[len(prefix):]
            params.append(f"{pname}={val}")
    if not params:
        return ind_name
    return f"{ind_name} ({', '.join(params)})"


def _build_tooltip(ind_name: str, inst: str, src: dict) -> str:
    prefix = f"{ind_name}__{inst}__"
    params = []
    for k, v in src.items():
        if k.startswith(prefix) and v not in ("", None):
            pname = k[len(prefix):]
            params.append(f"{pname}={v}")
    return f"{ind_name} ({', '.join(params)})" if params else ind_name


def _select_with_tooltip(
    component_id: dict,
    data: List[Dict],
    placeholder: str,
    selected_label: Optional[str],
    style: Optional[dict],
    param_source: Optional[Dict],
):
    """
    Преобразует data так, чтобы:
      - В списке опций label = '<NAME> <instance> instance <COLUMN>'
      - На кнопке после выбора показывается '<NAME> <instance> <COLUMN>' (без слова 'instance')
      - tooltip = 'NAME(param1=val1, ...)' или просто 'NAME'
    OHLCV и Custom оставляем без изменений.
    """
    transformed: list[dict] = []
    for opt in (data or []):
        raw = opt.get("raw", "")
        label = opt.get("label", "")
        value = opt.get("value", label)

        m = re.match(r"([A-Za-z0-9]+)__([0-9]+)__(.+)", raw)
        if m:
            name, inst, col = m.groups()
            # label для списка опций (со словом instance)
            label = f"{name} {inst} {col}"
            # тултип всегда "ИНДИКАТОР(param=val, ...)"
            tooltip = _build_tooltip(name, inst, param_source)

            transformed.append({
                "label": label,   # показываем в списке
                "value": value,
                "raw": raw,
                "tooltip": tooltip,
            })
        else:
            # OHLCV / Custom — без изменений
            transformed.append({
                "label": label,
                "value": value,
                "raw": raw,
                "tooltip": opt.get("tooltip"),
            })
    # Определяем текст кнопки
    button_text = selected_label or placeholder
    tooltip_for_selected = None

    if selected_label:
        for opt in transformed:
            if opt["label"] == selected_label:  # сравниваем с label из опций
                button_text = opt.get("label", selected_label)
                tooltip_for_selected = opt.get("tooltip")
                break

    # Кнопка
    button_component = dmc.Button(
        button_text,
        id={**component_id, "role": "input"},
        n_clicks=0,
        fullWidth=True,
        variant="outline",
        style=style,
    )
    # Если есть тултип для выбранного — оборачиваем кнопку
    if tooltip_for_selected:
        button_component = dmc.Tooltip(
            label=tooltip_for_selected,
            withArrow=True,
            position="top",
            children=button_component,
            styles=tooltip_styles,
        )

    # Popover с поиском и опциями
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
                    style={"display": "flex",
                           "flexDirection": "column",
                           "rowGap": "6px"},
                ),
                dcc.Store(
                    id={**component_id, "role": "options-src"},
                    data={
                        "data": transformed,
                        "param_source": param_source,
                    },
                ),
            ]),
        ],
    )



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


def _freeze(obj):
    """Превращает dict/list в JSON-строку для кэширования"""
    if obj is None:
        return None
    if isinstance(obj, (dict, list)):
        return json.dumps(obj, sort_keys=True)
    return obj


@lru_cache(maxsize=256)
def _build_options_template_cached(raw_options_json: str, param_source_json: str) -> List[Dict]:
    raw_options: List[Dict] = json.loads(raw_options_json) if raw_options_json else []
    param_source: Dict = json.loads(param_source_json) if param_source_json else {}
    options: List[Dict] = []
    for opt in raw_options:
        raw = opt.get("raw", "")
        value = opt.get("value") or raw
        old_label = opt.get("label", value)

        m = re.match(r"([A-Za-z0-9]+)__([0-9]+)__(.+)", raw)
        if m:
            name, inst, col = m.groups()
            label = f"{name} {inst} {col}"
            tooltip = _build_tooltip(name, inst, param_source)
        else:
            # OHLCV / Custom — как есть
            label = old_label
            tooltip = opt.get("tooltip")

        options.append({
            "label": label,
            "value": value,
            "raw": raw,
            "tooltip": tooltip,
        })

    return options


def build_options_template(
    raw_options: List[Dict],
    param_source: dict | None = None
) -> List[Dict]:
    """
    Публичная: принимает список опций и словарь параметров, возвращает
    преобразованные опции с красивыми label и tooltip.
    Внутри дергает кэшируемую версию на JSON-строках.
    """
    data_str = json.dumps(raw_options or [], sort_keys=True, ensure_ascii=False)
    param_str = json.dumps(param_source or {}, sort_keys=True, ensure_ascii=False)
    return _build_options_template_cached(data_str, param_str)


def build_options_src(component_id: dict, data: list, param_source: dict):
    """
    Берёт "шаблонные" опции и добавляет уникальный parent для конкретного dropdown.
    """
    base_options = build_options_template(
        raw_options=data or [],
        param_source=param_source or {},
    )

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
    ohlcv_data = [{'label': k, 'value': k, 'tooltip': v} for k, v in OHLCV_DESCRIPTIONS.items()]

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

