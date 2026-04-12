"""Dashboard page: Trade History."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from dashboard.components.charts import create_trades_timeline
from dashboard.components.widgets import trade_card, term_label
from dashboard.components.glossary import tip


def render(agent, engine, autopilot=None):
    st.header("Trade History")

    trades = engine.get_trade_history(limit=100)

    if not trades:
        st.info("No trades yet. Run the AI agent or execute manual trades to see history.")
        return

    # Summary metrics
    total_trades = len(trades)
    buy_trades = [t for t in trades if t["side"] == "buy"]
    sell_trades = [t for t in trades if t["side"] == "sell"]
    total_commission = sum(t.get("commission", 0) for t in trades)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Trades", total_trades)
    with col2:
        st.metric("Buy Orders", len(buy_trades), help=tip("Buy Order"))
    with col3:
        st.metric("Sell Orders", len(sell_trades), help=tip("Sell Order"))
    with col4:
        st.metric("Total Commission", f"${total_commission:,.2f}", help=tip("Commission"))

    st.divider()

    # Timeline chart
    fig = create_trades_timeline(trades)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Filter controls
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        side_filter = st.selectbox("Filter by Side", ["All", "Buy", "Sell"], key="trade_side_filter")
    with col_f2:
        symbols = sorted(set(t["symbol"] for t in trades))
        symbol_filter = st.selectbox("Filter by Symbol", ["All"] + symbols, key="trade_symbol_filter")
    with col_f3:
        view_mode = st.radio("View", ["Cards", "Table"], horizontal=True, key="trade_view")

    # Apply filters
    filtered = trades
    if side_filter != "All":
        filtered = [t for t in filtered if t["side"] == side_filter.lower()]
    if symbol_filter != "All":
        filtered = [t for t in filtered if t["symbol"] == symbol_filter]

    st.write(f"Showing {len(filtered)} trades")

    if view_mode == "Cards":
        for trade in filtered:
            trade_card(trade)
    else:
        df = pd.DataFrame(filtered)
        display_cols = ["timestamp", "symbol", "side", "quantity", "price", "commission", "total_cost", "reasoning"]
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available_cols], use_container_width=True, height=500)

    # Open orders
    st.divider()
    st.markdown(
        f"### {term_label('Open Orders')}",
        unsafe_allow_html=True,
    )
    open_orders = engine.get_open_orders()
    if open_orders:
        for order in open_orders:
            col_o1, col_o2, col_o3 = st.columns([3, 1, 1])
            with col_o1:
                order_tip = tip("Limit Order").replace('"', "&quot;")
                st.markdown(
                    f'<span title="{order_tip}" style="cursor:help">'
                    f"{order['side'].upper()} {order['quantity']} {order['symbol']} @ ${order['limit_price']:.2f}"
                    f"</span>",
                    unsafe_allow_html=True,
                )
            with col_o2:
                st.text(order["created_at"][:19])
            with col_o3:
                if st.button("Cancel", key=f"cancel_{order['order_id']}"):
                    engine.cancel_order(order["order_id"])
                    st.rerun()
    else:
        st.info("No open orders.")
