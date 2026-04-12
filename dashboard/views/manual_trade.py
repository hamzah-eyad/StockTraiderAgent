"""Dashboard page: Manual Trade — place buy/sell orders yourself."""
from __future__ import annotations

import json
import streamlit as st

from config import COMMISSION_RATE
from dashboard.components.widgets import metric_card, term_label
from dashboard.components.glossary import tip


# ── Popular stocks for the quick-pick bar ─────────────────────────────────────
POPULAR = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "AMZN", "JPM", "XOM", "LMT", "JNJ"]


def render(agent, engine, autopilot=None):
    st.header("Manual Trade")
    st.caption(
        "This is **paper trading** — orders are simulated using live Yahoo Finance prices. "
        "No real money is involved."
    )

    # ── Account strip ──────────────────────────────────────────────────────────
    try:
        balance = engine.get_account_balance()
        portfolio = engine.get_portfolio()
    except Exception:
        balance = {"cash": 0, "positions_value": 0, "total_value": 0,
                   "total_return": 0, "total_return_pct": 0}
        portfolio = {"positions": {}}

    positions = portfolio.get("positions", {})

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Cash Available", f"${balance['cash']:,.2f}")
    with c2:
        metric_card("Invested Value", f"${balance['positions_value']:,.2f}",
                    help_term="Positions Value")
    with c3:
        metric_card("Total Value", f"${balance['total_value']:,.2f}")
    with c4:
        metric_card("Total Return", f"{balance['total_return_pct']:+.2f}%")

    st.divider()

    # ── Quote panel ────────────────────────────────────────────────────────────
    st.subheader("Get a Live Quote")

    # Quick-pick buttons for popular tickers
    st.caption("Quick pick:")
    pick_cols = st.columns(len(POPULAR))
    for i, sym in enumerate(POPULAR):
        with pick_cols[i]:
            if st.button(sym, key=f"pick_{sym}"):
                st.session_state["mt_symbol"] = sym

    q1, q2 = st.columns([3, 1])
    with q1:
        symbol = st.text_input(
            "Ticker symbol",
            value=st.session_state.get("mt_symbol", "AAPL"),
            key="mt_symbol_input",
            placeholder="e.g. AAPL",
        ).upper().strip()
    with q2:
        st.write("")
        st.write("")
        quote_btn = st.button("Get Quote", key="mt_quote", type="primary")

    # Store symbol in session so order form pre-fills
    if symbol:
        st.session_state["mt_symbol"] = symbol

    # Fetch and display quote
    live_price: float | None = None
    if quote_btn or st.session_state.get("mt_quoted_symbol") == symbol:
        with st.spinner(f"Fetching quote for {symbol}…"):
            try:
                from mcp_servers.financial_data_server import get_stock_price
                data = json.loads(get_stock_price(symbol))
                if "error" in data:
                    st.error(f"Could not fetch quote: {data['error']}")
                else:
                    st.session_state["mt_quote_data"] = data
                    st.session_state["mt_quoted_symbol"] = symbol
            except Exception as e:
                st.error(f"Quote error: {e}")

    quote_data = st.session_state.get("mt_quote_data")
    if quote_data and st.session_state.get("mt_quoted_symbol") == symbol:
        live_price = quote_data.get("price")
        change = quote_data.get("change", 0)
        change_pct = quote_data.get("change_pct", 0)
        change_color = "#00d4aa" if change >= 0 else "#ff4444"
        arrow = "▲" if change >= 0 else "▼"

        qa, qb, qc, qd = st.columns(4)
        with qa:
            st.markdown(
                f"<div style='font-size:2em;font-weight:bold'>${live_price:,.2f}</div>"
                f"<div style='color:{change_color}'>{arrow} ${change:+.2f} ({change_pct:+.2f}%)</div>",
                unsafe_allow_html=True,
            )
        with qb:
            st.metric("Day High", f"${quote_data.get('day_high', 0):,.2f}",
                      help=tip("Day High"))
        with qc:
            st.metric("Day Low", f"${quote_data.get('day_low', 0):,.2f}",
                      help=tip("Day Low"))
        with qd:
            vol = quote_data.get("volume", 0)
            st.metric("Volume", f"{vol:,.0f}", help=tip("Volume"))

        # Show how many shares you already own
        owned = positions.get(symbol, {})
        if owned:
            own_qty = owned.get("quantity", 0)
            own_avg = owned.get("avg_cost", 0)
            own_pnl = owned.get("unrealized_pnl", 0)
            own_pnl_pct = owned.get("unrealized_pnl_pct", 0)
            pnl_color = "#00d4aa" if own_pnl >= 0 else "#ff4444"
            st.markdown(
                f'You currently own **{own_qty:,.0f} shares** of {symbol} '
                f'(avg cost ${own_avg:.2f}) — '
                f'<span style="color:{pnl_color}">${own_pnl:+.2f} ({own_pnl_pct:+.1f}%)</span>',
                unsafe_allow_html=True,
            )
    else:
        live_price = engine.get_live_price(symbol) if symbol else None

    st.divider()

    # ── Order form ─────────────────────────────────────────────────────────────
    st.subheader("Place an Order")

    left_col, right_col = st.columns([1, 1])

    with left_col:
        side = st.radio(
            "Side",
            ["Buy", "Sell"],
            horizontal=True,
            key="mt_side",
            help="Buy = acquire shares. Sell = dispose of shares you own.",
        )

        quantity = st.number_input(
            "Quantity (shares)",
            min_value=1,
            value=10,
            step=1,
            key="mt_qty",
            help=tip("Buy Order") if side == "Buy" else tip("Sell Order"),
        )

        order_type = st.radio(
            "Order type",
            ["Market", "Limit"],
            horizontal=True,
            key="mt_order_type",
            help=(
                f"{tip('Market Order')} | {tip('Limit Order')}"
            ),
        )

        limit_price: float | None = None
        if order_type == "Limit":
            suggested = round(live_price * 0.99, 2) if (live_price and side == "Buy") else (
                round(live_price * 1.01, 2) if live_price else 0.0
            )
            limit_price = st.number_input(
                "Limit price ($)",
                min_value=0.01,
                value=float(suggested),
                step=0.01,
                format="%.2f",
                key="mt_limit_price",
                help=tip("Limit Order"),
            )

    with right_col:
        st.markdown("#### Order Preview")

        ref_price = limit_price if order_type == "Limit" else live_price
        if ref_price and quantity:
            gross = ref_price * quantity
            commission = gross * COMMISSION_RATE
            net = gross + commission if side == "Buy" else gross - commission

            if side == "Buy":
                st.markdown(f"Shares to buy: **{quantity:,.0f}**")
                st.markdown(f"Reference price: **${ref_price:,.2f}**")
                st.markdown(f"Gross cost: **${gross:,.2f}**")
                st.markdown(
                    f"{term_label('Commission')} ({COMMISSION_RATE*100:.1f}%): "
                    f"**${commission:,.2f}**",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Total deducted from cash: ${net:,.2f}**")

                if balance["cash"] < net:
                    st.warning(
                        f"Insufficient cash. You need ${net:,.2f} but only have "
                        f"${balance['cash']:,.2f}."
                    )
                else:
                    remaining = balance["cash"] - net
                    st.success(f"Cash remaining after order: ${remaining:,.2f}")
            else:
                owned_qty = positions.get(symbol, {}).get("quantity", 0)
                st.markdown(f"Shares to sell: **{quantity:,.0f}**")
                st.markdown(f"You own: **{owned_qty:,.0f} shares**")
                st.markdown(f"Reference price: **${ref_price:,.2f}**")
                st.markdown(f"Gross proceeds: **${gross:,.2f}**")
                st.markdown(
                    f"{term_label('Commission')} ({COMMISSION_RATE*100:.1f}%): "
                    f"**${commission:,.2f}**",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Net received: ${net:,.2f}**")

                if owned_qty < quantity:
                    st.warning(
                        f"You only own {owned_qty:,.0f} shares of {symbol}. "
                        f"Reduce quantity or choose a different stock."
                    )
        else:
            st.info("Get a quote above to see an order preview.")

    st.write("")

    # ── Place Order button ─────────────────────────────────────────────────────
    order_label = f"Place {side.upper()} Order — {quantity} × {symbol}"
    if order_type == "Limit" and limit_price:
        order_label += f" @ ${limit_price:.2f}"

    if st.button(order_label, type="primary", key="mt_submit"):
        if not symbol:
            st.error("Please enter a ticker symbol.")
        elif order_type == "Market" and live_price is None:
            st.error("Could not fetch live price. Click 'Get Quote' first.")
        else:
            with st.spinner("Submitting order…"):
                try:
                    kwargs = dict(
                        symbol=symbol,
                        quantity=float(quantity),
                        order_type=order_type.lower(),
                        limit_price=limit_price,
                        reasoning="Manual trade placed from the Manual Trade page.",
                    )
                    if side == "Buy":
                        result = engine.buy(**kwargs)
                    else:
                        result = engine.sell(**kwargs)

                    status = result.get("status", "unknown")
                    if status == "filled":
                        filled_price = result.get("price", 0)
                        st.success(
                            f"Order filled! {side.upper()} {quantity} shares of "
                            f"{symbol} @ ${filled_price:.2f}."
                        )
                        # Clear quote cache so refresh shows new state
                        st.session_state.pop("mt_quote_data", None)
                        st.rerun()
                    elif status == "pending":
                        st.info(
                            f"Limit order placed (ID: `{result.get('order_id', '')}`)."
                            " It will fill when the market reaches your limit price. "
                            "Check **Trade History** to see open orders."
                        )
                    elif status == "rejected":
                        reason = result.get("reason", "No reason provided.")
                        st.error(f"Order rejected: {reason}")
                    else:
                        st.warning(f"Unexpected status: {status}. Details: {result}")
                except Exception as e:
                    st.error(f"Order failed: {e}")

    st.divider()
    st.caption(
        "For charts, technical indicators, and AI analysis, visit **Stock Analysis**. "
        "All trades appear in **Trade History** and **My Portfolio**."
    )
