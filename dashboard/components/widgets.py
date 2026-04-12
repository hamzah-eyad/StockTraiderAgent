"""Reusable UI widgets for the Streamlit dashboard."""
from __future__ import annotations

import streamlit as st
from dashboard.components.glossary import TERMS, tip


def metric_card(
    label: str,
    value: str,
    delta: str | None = None,
    color: str = "normal",
    help_term: str | None = None,
):
    """Display a styled metric with an optional hover tooltip from the glossary."""
    delta_color = color if color in ("normal", "inverse", "off") else "normal"
    help_text = tip(help_term or label)
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text or None,
    )


def term_label(term: str, extra: str = "") -> str:
    """
    Render a financial term as bold text with a dotted-underline hover tooltip.
    Returns an HTML string for use with st.markdown(unsafe_allow_html=True).
    """
    definition = tip(term)
    if not definition:
        return f"**{term}**{extra}"

    safe_def = definition.replace('"', "&quot;").replace("'", "&#39;")
    return (
        f'<span title="{safe_def}" style="border-bottom: 1px dotted #888; cursor: help; '
        f'font-weight: 600;">{term}</span>{extra}'
    )


def risk_badge(level: str):
    """Display a colored risk level badge."""
    colors = {
        "low": "background-color: #00d4aa; color: black;",
        "medium": "background-color: #ffa500; color: black;",
        "high": "background-color: #ff4444; color: white;",
        "unknown": "background-color: #888; color: white;",
    }
    style = colors.get(level.lower(), colors["unknown"])
    st.markdown(
        f'<span style="padding: 4px 12px; border-radius: 12px; font-weight: bold; {style}">'
        f'{level.upper()} RISK</span>',
        unsafe_allow_html=True,
    )


def trade_card(trade: dict):
    """Display a trade as a compact card."""
    side = trade.get("side", "")
    symbol = trade.get("symbol", "")
    price = trade.get("price", 0)
    qty = trade.get("quantity", 0)
    reasoning = trade.get("reasoning", "")
    ts = trade.get("timestamp", "")

    side_color = "#00d4aa" if side == "buy" else "#ff4444"
    side_icon = "BUY" if side == "buy"  else "SELL"

    buy_tip = tip("Buy Order").replace('"', "&quot;")
    sell_tip = tip("Sell Order").replace('"', "&quot;")
    comm_tip = tip("Commission").replace('"', "&quot;")
    side_tip = buy_tip if side == "buy" else sell_tip
    commission = trade.get("commission", 0)

    st.markdown(
        f"""
        <div style="border: 1px solid #333; border-radius: 8px; padding: 12px; margin: 6px 0;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span title="{side_tip}" style="color: {side_color}; font-weight: bold;
                    font-size: 1.1em; cursor: help;">
                    {side_icon} {symbol}
                </span>
                <span style="color: #aaa; font-size: 0.85em;">{ts[:19]}</span>
            </div>
            <div style="margin-top: 6px;">
                <span>{qty} shares @ ${price:.2f}</span>
                <span title="{comm_tip}" style="color: #aaa; margin-left: 10px;
                    border-bottom: 1px dotted #666; cursor: help; font-size: 0.85em;">
                    fee: ${commission:.2f}
                </span>
            </div>
            <div style="color: #aaa; font-size: 0.85em; margin-top: 4px;">
                {reasoning[:200]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def position_table(positions: dict):
    """Display positions as a formatted table."""
    if not positions:
        st.info("No open positions.")
        return

    hdr1, hdr2, hdr3, hdr4 = st.columns(4)
    with hdr1:
        st.markdown("**Symbol**")
    with hdr2:
        st.markdown("**Shares**")
    with hdr3:
        st.markdown(term_label("Avg Cost"), unsafe_allow_html=True)
    with hdr4:
        st.markdown(term_label("Unrealized P&L"), unsafe_allow_html=True)

    for sym, pos in positions.items():
        pnl = pos.get("unrealized_pnl", 0)
        pnl_pct = pos.get("unrealized_pnl_pct", 0)
        pnl_color = "#00d4aa" if pnl >= 0 else "#ff4444"

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"**{sym}**")
        with col2:
            st.text(f"{pos.get('quantity', 0)} shares")
        with col3:
            st.text(f"${pos.get('current_price', 0):.2f}")
        with col4:
            st.markdown(
                f'<span style="color: {pnl_color}">${pnl:.2f} ({pnl_pct:+.1f}%)</span>',
                unsafe_allow_html=True,
            )
