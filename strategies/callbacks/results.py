from dash import html, dcc, Input, Output, State
import plotly.graph_objects as go
from calculate import Coin, Indicator
from strategies.strategies_helpful_functions import (
    group_params,
    _fmt_pct,
    _color_scale_number,
    replace_ids_with_names,
)
from strategies.strategies_constants import (
    dict_ops,
    submit_clicks,
)
import itertools
import plotly.colors as pc


def register_callbacks(app):

    # Отрисовываем результаты стратегий: таблица сравнения, графики - стратегий, монеты, индикаторов
    @app.callback(
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
        # print("CHART-----------------------")
        # print("conditions_store_inputs", conditions_store_inputs)
        # print("stored_inputs", stored_inputs)
        if clicks == submit_clicks["click"]:
            return [], [], [], [], {"display": "none"}
        submit_clicks["click"] = clicks
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
