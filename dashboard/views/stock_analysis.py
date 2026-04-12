"""Dashboard page: Individual Stock Analysis."""
from __future__ import annotations

import json
import streamlit as st
from dashboard.components.charts import create_candlestick_chart
from dashboard.components.widgets import metric_card, term_label
from dashboard.components.glossary import tip


def render(agent, engine, autopilot=None):
    st.header("Stock Analysis")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbol = st.text_input("Stock Symbol", value="AAPL", key="stock_symbol").upper()
    with col2:
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=1, key="stock_period")
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("Analyze", type="primary", key="analyze_stock")

    if analyze_btn or st.session_state.get("analyzed_symbol") == symbol:
        st.session_state["analyzed_symbol"] = symbol

        with st.spinner(f"Fetching data for {symbol}..."):
            try:
                from mcp_servers.financial_data_server import (
                    get_stock_price, get_stock_history, get_technical_indicators,
                )

                price_data = json.loads(get_stock_price(symbol))
                history_data = json.loads(get_stock_history(symbol, period=period))
                tech_data = json.loads(get_technical_indicators(symbol, period=period))
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                return

        if "error" in price_data:
            st.error(f"Could not fetch data for {symbol}: {price_data['error']}")
            return

        # Price metrics
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            metric_card(
                "Price",
                f"${price_data.get('price', 0):.2f}",
                f"{price_data.get('change_pct', 0):+.2f}%",
            )
        with col_b:
            metric_card("Day High", f"${price_data.get('day_high', 0):.2f}")
        with col_c:
            metric_card("Day Low", f"${price_data.get('day_low', 0):.2f}")
        with col_d:
            metric_card(
                "Volume",
                f"{price_data.get('volume', 0):,.0f}",
            )

        st.divider()

        # Candlestick chart
        if history_data.get("data"):
            fig = create_candlestick_chart(history_data["data"], symbol)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Technical indicators
        if "error" not in tech_data:
            st.subheader("Technical Indicators")

            t1, t2, t3 = st.columns(3)
            with t1:
                rsi = tech_data.get("rsi_14", 0)
                signal = tech_data.get("rsi_signal", "neutral")
                signal_color = "#00d4aa" if signal == "oversold" else "#ff4444" if signal == "overbought" else "#ffa500"
                signal_label = term_label(signal.title())
                st.markdown(
                    f"{term_label('RSI (14)')}: "
                    f"<span style='color:{signal_color}'>{rsi:.1f} ({signal_label})</span>",
                    unsafe_allow_html=True,
                )

            with t2:
                macd_type = tech_data.get("macd_signal_type", "neutral")
                macd_color = "#00d4aa" if macd_type == "bullish" else "#ff4444"
                macd_label = term_label(macd_type.title())
                st.markdown(
                    f"{term_label('MACD Signal')}: "
                    f"<span style='color:{macd_color}'>{macd_label}</span>",
                    unsafe_allow_html=True,
                )

            with t3:
                st.markdown(
                    f"{term_label('SMA 20')}: ${tech_data.get('sma_20', 0):.2f}",
                    unsafe_allow_html=True,
                )
                if tech_data.get("sma_50"):
                    st.markdown(
                        f"{term_label('SMA 50')}: ${tech_data['sma_50']:.2f}",
                        unsafe_allow_html=True,
                    )

            st.write("")
            with st.expander("All Indicators"):
                indicator_labels = {
                    "price": "Price",
                    "rsi_14": "RSI (14)",
                    "macd": "MACD",
                    "macd_signal": "MACD Signal",
                    "macd_histogram": "MACD Histogram",
                    "bollinger_upper": "Bollinger Upper",
                    "bollinger_middle": "Bollinger Middle",
                    "bollinger_lower": "Bollinger Lower",
                    "sma_20": "SMA 20",
                    "sma_50": "SMA 50",
                    "ema_12": "EMA 12",
                }
                for key, value in tech_data.items():
                    if key in ("symbol", "rsi_signal", "macd_signal_type") or value is None:
                        continue
                    label = indicator_labels.get(key, key)
                    glossary_def = tip(label)
                    if glossary_def:
                        st.markdown(
                            f"{term_label(label)}: {value}",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.text(f"{key}: {value}")

        st.divider()

        # AI analysis for this stock
        st.subheader("AI Analysis")
        if st.button(f"Ask AI about {symbol}", key="ai_stock_analysis"):
            with st.spinner("AI is analyzing this stock..."):
                try:
                    response = agent.chat(
                        f"Analyze {symbol} stock. Look at the current price, technical indicators, "
                        f"and any relevant geopolitical risks. Should I buy, sell, or hold? Explain your reasoning."
                    )
                    st.markdown(response)
                except Exception as e:
                    st.error(f"AI analysis failed: {e}")

        # Quick trade
        st.subheader("Quick Trade")
        tc1, tc2, tc3, tc4 = st.columns(4)
        with tc1:
            qty = st.number_input("Quantity", min_value=1, value=10, key="trade_qty")
        with tc2:
            if st.button(f"Buy {symbol}", type="primary", key="quick_buy"):
                result = engine.buy(symbol, qty, reasoning="Manual buy from dashboard")
                if result.get("status") == "filled":
                    st.success(f"Bought {qty} shares of {symbol} @ ${result.get('price', 0):.2f}")
                else:
                    st.error(f"Order {result.get('status')}: {result.get('reason', '')}")
        with tc3:
            if st.button(f"Sell {symbol}", key="quick_sell"):
                result = engine.sell(symbol, qty, reasoning="Manual sell from dashboard")
                if result.get("status") == "filled":
                    st.success(f"Sold {qty} shares of {symbol} @ ${result.get('price', 0):.2f}")
                else:
                    st.error(f"Order {result.get('status')}: {result.get('reason', '')}")
        with tc4:
            pass
