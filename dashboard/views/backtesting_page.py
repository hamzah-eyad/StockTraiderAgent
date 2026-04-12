"""Dashboard page: Backtesting."""
from __future__ import annotations

import json
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from simulator.backtesting import BacktestEngine
from agent.strategies import momentum_strategy, mean_reversion_strategy, defensive_strategy
from dashboard.components.charts import create_backtest_chart
from dashboard.components.widgets import metric_card, term_label
from dashboard.components.glossary import tip


def render(agent, engine, autopilot=None):
    st.header("Backtesting")

    st.markdown(
        "Test trading strategies against historical data. "
        "The simulator replays market data day-by-day and evaluates performance."
    )

    # Configuration
    with st.form("backtest_config"):
        st.subheader("Configuration")

        col1, col2 = st.columns(2)
        with col1:
            symbols_input = st.text_input(
                "Symbols (comma separated)",
                value="AAPL, MSFT, GOOGL, NVDA, TSLA",
                key="bt_symbols",
            )
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=365),
                key="bt_start",
            )
            initial_balance = st.number_input(
                "Initial Balance ($)",
                value=100000,
                min_value=1000,
                step=10000,
                key="bt_balance",
            )

        with col2:
            strategy = st.selectbox(
                "Strategy",
                ["Momentum", "Mean Reversion", "Defensive"],
                key="bt_strategy",
                help=(
                    "Momentum: buys stocks trending up, sells when trend reverses. "
                    "Mean Reversion: buys when price drops below average, sells when it rises above. "
                    "Defensive: sells risky stocks and buys safe-haven assets during high geopolitical risk."
                ),
            )
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                key="bt_end",
            )
            risk_score = st.slider(
                "Simulated Risk Score",
                min_value=0,
                max_value=100,
                value=50,
                key="bt_risk",
                help=tip("Geopolitical Risk Score"),
            )

        submitted = st.form_submit_button("Run Backtest", type="primary")

    if submitted:
        symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]
        if not symbols:
            st.error("Please enter at least one symbol.")
            return

        price_history: dict[str, list[float]] = {s: [] for s in symbols}

        def strategy_fn(prices, portfolio, current_date):
            for sym, price in prices.items():
                if sym in price_history:
                    price_history[sym].append(price)

            if strategy == "Momentum":
                return momentum_strategy(
                    prices, portfolio, current_date,
                    lookback_prices=price_history, risk_score=risk_score,
                )
            elif strategy == "Mean Reversion":
                return mean_reversion_strategy(
                    prices, portfolio, current_date,
                    lookback_prices=price_history, risk_score=risk_score,
                )
            else:
                return defensive_strategy(
                    prices, portfolio, current_date, risk_score=risk_score,
                )

        bt_engine = BacktestEngine(
            initial_balance=initial_balance,
            commission_rate=0.001,
        )

        with st.spinner("Running backtest... This may take a moment."):
            result = bt_engine.run(
                symbols=symbols,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                strategy_fn=strategy_fn,
            )
            st.session_state["backtest_result"] = result

    # Display results
    result = st.session_state.get("backtest_result")
    if result:
        st.divider()
        st.subheader("Results")

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            ret = result.total_return_pct
            color = "normal" if ret >= 0 else "inverse"
            metric_card("Strategy Return", f"{ret:+.2f}%", color=color)
        with col_b:
            metric_card("Benchmark (SPY)", f"{result.benchmark_return_pct:+.2f}%")
        with col_c:
            metric_card("Sharpe Ratio", f"{result.sharpe_ratio:.4f}")
        with col_d:
            metric_card("Max Drawdown", f"-{result.max_drawdown_pct:.2f}%")

        col_e, col_f, col_g, col_h = st.columns(4)
        with col_e:
            metric_card("Total Trades", str(result.total_trades))
        with col_f:
            metric_card("Win Rate", f"{result.win_rate:.1f}%")
        with col_g:
            st.metric("Winning", str(result.winning_trades))
        with col_h:
            st.metric("Losing", str(result.losing_trades))

        st.divider()

        # Performance chart
        fig = create_backtest_chart(result.portfolio_values)
        st.plotly_chart(fig, use_container_width=True)

        # Trade log
        if result.trades:
            st.divider()
            st.subheader("Trade Log")
            df = pd.DataFrame(result.trades)
            display_cols = ["timestamp", "symbol", "side", "quantity", "price", "reasoning"]
            available_cols = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available_cols], use_container_width=True, height=400)
