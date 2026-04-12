"""Dashboard page: My Portfolio — full holdings view + agent activity feed."""
from __future__ import annotations

import yfinance as yf
import streamlit as st

from dashboard.components.charts import create_allocation_pie
from dashboard.components.widgets import metric_card, term_label
from dashboard.components.glossary import tip


# ── Helpers ───────────────────────────────────────────────────────────────────

def _company_name(symbol: str) -> str:
    try:
        info = yf.Ticker(symbol).fast_info
        return getattr(info, "display_name", symbol) or symbol
    except Exception:
        return symbol


def _pnl_bar(pnl_pct: float, width_px: int = 80) -> str:
    """Return a small HTML progress bar coloured green/red."""
    clamped = max(min(abs(pnl_pct), 50), 0)
    fill_pct = int(clamped / 50 * 100)
    color = "#00d4aa" if pnl_pct >= 0 else "#ff4444"
    return (
        f'<div style="background:#222;border-radius:4px;width:{width_px}px;height:8px;display:inline-block;">'
        f'<div style="background:{color};width:{fill_pct}%;height:100%;border-radius:4px;"></div>'
        f'</div>'
    )


def _action_card(action: dict) -> str:
    """Render a single agent trade decision as an HTML card."""
    is_buy = action["action"] == "buy_stock"
    side_color = "#00d4aa" if is_buy else "#ff4444"
    side_label = "BUY" if is_buy else "SELL"
    symbol = action.get("symbol", "?")
    qty = action.get("quantity", 0)
    price = action.get("price")
    price_str = f"@ ${price:.2f}" if price else "(price pending)"
    status = action.get("status", "unknown")
    status_icon = "✓" if status == "filled" else "✗" if status == "rejected" else "⏳"
    status_color = "#00d4aa" if status == "filled" else "#ff4444" if status == "rejected" else "#aaa"
    reasoning = action.get("reasoning", "No reasoning provided.")
    risk = action.get("risk_score", 0)
    ts = action.get("timestamp", "")[:19].replace("T", " ")

    return (
        f'<div style="border:1px solid #333;border-radius:10px;padding:14px;margin:8px 0;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'  <span style="color:{side_color};font-weight:bold;font-size:1.15em;">'
        f'    [{side_label}] {symbol} &times;{qty} shares {price_str}'
        f'  </span>'
        f'  <span style="color:{status_color};font-weight:bold;">{status_icon} {status.upper()}</span>'
        f'</div>'
        f'<div style="color:#888;font-size:0.8em;margin-top:4px;">'
        f'  Risk score: {risk:.0f} &nbsp;|&nbsp; {ts} UTC'
        f'</div>'
        f'<div style="color:#ccc;font-size:0.9em;margin-top:8px;'
        f'  border-left:3px solid {side_color};padding-left:10px;">'
        f'  {reasoning}'
        f'</div>'
        f'</div>'
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render(agent, engine, autopilot=None):
    st.header("My Portfolio")

    # ── Section A: Account summary ────────────────────────────────────
    try:
        balance = engine.get_account_balance()
    except Exception:
        balance = {
            "cash": 100000, "positions_value": 0, "total_value": 100000,
            "total_return": 0, "total_return_pct": 0, "initial_balance": 100000,
        }

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card(
            "Total Value",
            f"${balance['total_value']:,.2f}",
            f"${balance['total_return']:+,.2f}",
        )
    with c2:
        metric_card("Cash Available", f"${balance['cash']:,.2f}")
    with c3:
        metric_card("Invested Value", f"${balance['positions_value']:,.2f}",
                    help_term="Positions Value")
    with c4:
        metric_card("Total Return", f"{balance['total_return_pct']:+.2f}%")

    st.divider()

    # ── Section B: Holdings table ─────────────────────────────────────
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.subheader("Current Holdings")
    with col_btn:
        st.write("")
        if st.button("Refresh Prices", key="port_refresh"):
            engine.refresh_positions()
            st.rerun()

    try:
        portfolio = engine.get_portfolio()
        positions = portfolio.get("positions", {})
    except Exception:
        positions = {}

    if not positions:
        st.info(
            "You don't own any stocks yet. "
            "Run an AI analysis cycle or use the Stock Analysis page to make your first trade."
        )
    else:
        # Header row
        h1, h2, h3, h4, h5, h6, h7 = st.columns([1.5, 2.5, 1, 1, 1.2, 1.5, 2])
        with h1:
            st.markdown("**Symbol**")
        with h2:
            st.markdown("**Company**")
        with h3:
            st.markdown(term_label("Avg Cost"), unsafe_allow_html=True)
        with h4:
            st.markdown("**Current Price**")
        with h5:
            st.markdown("**Shares**")
        with h6:
            st.markdown("**Market Value**", help=tip("Positions Value"))
        with h7:
            st.markdown(term_label("Unrealized P&L"), unsafe_allow_html=True)

        st.markdown('<hr style="margin:4px 0;border-color:#333;">', unsafe_allow_html=True)

        for sym, pos in positions.items():
            avg_cost = pos.get("avg_cost", 0)
            cur_price = pos.get("current_price", 0)
            qty = pos.get("quantity", 0)
            mkt_val = pos.get("market_value", 0)
            pnl = pos.get("unrealized_pnl", 0)
            pnl_pct = pos.get("unrealized_pnl_pct", 0)

            pnl_color = "#00d4aa" if pnl >= 0 else "#ff4444"
            price_color = "#00d4aa" if cur_price >= avg_cost else "#ff4444"

            c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 2.5, 1, 1, 1.2, 1.5, 2])
            with c1:
                st.markdown(f"**{sym}**")
            with c2:
                name = _company_name(sym)
                st.markdown(
                    f'<span style="color:#aaa;font-size:0.9em;">{name}</span>',
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(f"${avg_cost:.2f}")
            with c4:
                st.markdown(
                    f'<span style="color:{price_color};font-weight:bold;">${cur_price:.2f}</span>',
                    unsafe_allow_html=True,
                )
            with c5:
                st.markdown(f"{qty:,.0f}")
            with c6:
                st.markdown(f"${mkt_val:,.2f}")
            with c7:
                bar = _pnl_bar(pnl_pct)
                st.markdown(
                    f'<span style="color:{pnl_color};font-weight:bold;">'
                    f'${pnl:+,.2f} ({pnl_pct:+.1f}%)'
                    f'</span> &nbsp;{bar}',
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Section C: Allocation pie chart ──────────────────────────────
    st.subheader("Portfolio Allocation")
    if positions:
        fig = create_allocation_pie(positions, balance["cash"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Allocation chart will appear once you own stocks.")

    st.divider()

    # ── Section D: Last Agent Cycle Actions ───────────────────────────
    st.subheader("Last Agent Cycle — What the AI Did")

    live_actions = agent.get_live_actions() if hasattr(agent, "get_live_actions") else []

    if not live_actions:
        st.info(
            "No agent decisions yet. Go to **Overview** and click "
            "**Run AI Analysis Cycle** to see what the agent buys and sells."
        )
    else:
        trades_made = len(live_actions)
        buys = [a for a in live_actions if a["action"] == "buy_stock"]
        sells = [a for a in live_actions if a["action"] == "sell_stock"]
        filled = [a for a in live_actions if a.get("status") == "filled"]
        rejected = [a for a in live_actions if a.get("status") == "rejected"]

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Decisions", trades_made)
        with m2:
            st.metric("Buy Orders", len(buys))
        with m3:
            st.metric("Sell Orders", len(sells))
        with m4:
            filled_count = len(filled)
            rejected_count = len(rejected)
            label = f"{filled_count} filled"
            if rejected_count:
                label += f", {rejected_count} rejected"
            st.metric("Outcome", label)

        st.write("")
        st.markdown("#### Decision Feed")

        cards_html = "".join(_action_card(a) for a in live_actions)
        st.markdown(
            f'<div style="max-height:600px;overflow-y:auto;">{cards_html}</div>',
            unsafe_allow_html=True,
        )
