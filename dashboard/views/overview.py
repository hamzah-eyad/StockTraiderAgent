"""Dashboard page: Portfolio Overview."""
from __future__ import annotations

import json
import streamlit as st
from dashboard.components.charts import create_risk_gauge, create_portfolio_value_chart
from dashboard.components.widgets import metric_card, risk_badge, position_table, term_label
from dashboard.styles import page_header, section_header


# Kind → display label, background colour, text colour
_LOG_STYLE: dict[str, tuple[str, str, str]] = {
    "monitoring": ("MONITORING", "#334", "white"),
    "routine":    ("ROUTINE",   "#1a4a3a", "#00d4aa"),
    "reactive":   ("REACTIVE",  "#4a2a00", "#ffa500"),
    "error":      ("ERROR",     "#4a0000", "#ff4444"),
}


def _autopilot_badge(kind: str) -> str:
    label, bg, fg = _LOG_STYLE.get(kind, ("INFO", "#333", "white"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:8px;font-size:0.75em;font-weight:bold;">{label}</span>'
    )


def render(agent, engine, autopilot=None):
    page_header("Portfolio Overview", "Real-time account summary, positions, and AI autopilot controls")

    # ── Account summary ───────────────────────────────────────────────
    try:
        balance = engine.get_account_balance()
    except Exception:
        balance = {
            "cash": 100000, "positions_value": 0, "total_value": 100000,
            "total_return": 0, "total_return_pct": 0, "initial_balance": 100000,
        }

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card(
            "Total Value",
            f"${balance['total_value']:,.2f}",
            f"${balance['total_return']:+,.2f}",
        )
    with col2:
        metric_card("Cash Available", f"${balance['cash']:,.2f}")
    with col3:
        metric_card("Positions Value", f"${balance['positions_value']:,.2f}")
    with col4:
        metric_card("Total Return", f"{balance['total_return_pct']:+.2f}%")

    st.divider()

    # ── Risk gauge + positions ────────────────────────────────────────
    left, right = st.columns([1, 1])

    with left:
        section_header("Geopolitical Risk")
        st.markdown(
            f"<div style='margin-bottom:8px;'>{term_label('Geopolitical Risk Score')}</div>",
            unsafe_allow_html=True,
        )
        if st.button("Refresh Risk Score", key="refresh_risk"):
            with st.spinner("Analyzing geopolitical conditions..."):
                try:
                    from mcp_servers.geopolitical_server import get_geopolitical_risk_score
                    risk_data = json.loads(get_geopolitical_risk_score())
                    st.session_state["risk_data"] = risk_data
                except Exception as e:
                    st.error(f"Failed to fetch risk score: {e}")

        risk_data = st.session_state.get(
            "risk_data", {"composite_score": 0, "risk_level": "unknown"}
        )
        fig = create_risk_gauge(risk_data.get("composite_score", 0))
        st.plotly_chart(fig, use_container_width=True)
        risk_badge(risk_data.get("risk_level", "unknown"))
        if risk_data.get("advice"):
            st.info(risk_data["advice"])

    with right:
        section_header("Current Positions")
        try:
            portfolio = engine.get_portfolio()
            position_table(portfolio.get("positions", {}))
        except Exception:
            st.info("No positions yet. Run the AI agent to start trading.")

    st.divider()

    # ── Portfolio history ─────────────────────────────────────────────
    section_header("Portfolio History")
    history = engine.portfolio.portfolio_history if hasattr(engine, "portfolio") else []
    if history:
        chart_data = [
            {"date": s.timestamp.isoformat(), "value": s.total_value}
            for s in history
        ]
        fig = create_portfolio_value_chart(chart_data)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Portfolio history will appear here after trading cycles run.")

    st.divider()

    # ── Manual AI Agent controls ──────────────────────────────────────
    section_header("Manual AI Trade Cycle")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Run AI Analysis Cycle", type="primary", key="run_agent"):
            with st.spinner("AI agent is analyzing markets and making decisions..."):
                try:
                    result = agent.run_analysis()
                    st.session_state["last_analysis"] = result
                    st.success("Analysis complete!")
                except Exception as e:
                    st.error(f"Agent error: {e}")
    with col_b:
        if st.button("Refresh Positions", key="refresh_pos"):
            engine.refresh_positions()
            st.rerun()

    # Compact agent actions summary
    live_actions = agent.get_live_actions() if hasattr(agent, "get_live_actions") else []
    if live_actions:
        buys = [a for a in live_actions if a["action"] == "buy_stock"]
        sells = [a for a in live_actions if a["action"] == "sell_stock"]
        filled = [a for a in live_actions if a.get("status") == "filled"]

        st.markdown(
            f"**Agent completed: {len(live_actions)} decision(s)** "
            f"— {len(buys)} buy, {len(sells)} sell, {len(filled)} filled",
        )

        rows_html = []
        for a in live_actions:
            is_buy = a["action"] == "buy_stock"
            color = "#00d4aa" if is_buy else "#ff4444"
            label = "BUY " if is_buy else "SELL"
            sym = a.get("symbol", "?")
            qty = a.get("quantity", 0)
            price = a.get("price")
            price_str = f"@ ${price:.2f}" if price else ""
            short_reason = (a.get("reasoning", "") or "")[:80]
            status = a.get("status", "")
            status_icon = "✓" if status == "filled" else "✗" if status == "rejected" else "⏳"

            rows_html.append(
                f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #131d30;">'
                f'<span style="color:{color};font-weight:700;font-family:monospace;font-size:0.82rem;min-width:36px;">{label}</span>'
                f'<span style="color:#e8eaf0;font-weight:600;">{sym}</span>'
                f'<span style="color:#8b9db8;font-size:0.85rem;">&times;{qty} {price_str}</span>'
                f'<span style="color:#4a5a73;font-size:0.8rem;margin-left:auto;">{status_icon} {short_reason}</span>'
                f'</div>'
            )

        st.markdown(
            '<div style="background:#0d1421;border:1px solid #1e2d45;border-radius:12px;padding:12px 16px;margin:8px 0;">'
            + "".join(rows_html)
            + '<div style="color:#3d4f68;font-size:0.75rem;margin-top:10px;padding-top:6px;">'
            '  Full reasoning in <strong style="color:#4a5a73;">My Portfolio → Last Agent Cycle</strong></div>'
            + "</div>",
            unsafe_allow_html=True,
        )

    if "last_analysis" in st.session_state:
        analysis = st.session_state["last_analysis"]
        with st.expander("Full Agent Reasoning", expanded=False):
            st.text(f"Timestamp : {analysis.get('timestamp', '')}")
            st.text(f"Risk Score: {analysis.get('risk_score', 'N/A')}")
            st.text(f"Iterations: {analysis.get('iterations', 0)}")
            st.markdown("**Agent Reasoning:**")
            st.markdown(analysis.get("reasoning", "No reasoning provided."))

    st.divider()

    # ── Autopilot ─────────────────────────────────────────────────────
    if autopilot is None:
        return

    section_header("Autopilot — Autonomous Trading")
    st.markdown(
        '<p style="color:#8b9db8;font-size:0.88rem;margin:-4px 0 12px 0;">'
        "Continuously monitors geopolitical risk and triggers the AI agent "
        "to trade automatically when conditions change."
        "</p>",
        unsafe_allow_html=True,
    )

    # Status badge
    if autopilot.is_running:
        st.markdown('<span class="pill pill-green">● AUTOPILOT RUNNING</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="pill pill-gray">○ AUTOPILOT STOPPED</span>', unsafe_allow_html=True)

    st.write("")

    # Start / Stop buttons
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])
    with btn_col1:
        if st.button(
            "Start Autopilot",
            type="primary",
            disabled=autopilot.is_running,
            key="ap_start",
        ):
            autopilot.start()
            st.rerun()
    with btn_col2:
        if st.button(
            "Stop Autopilot",
            disabled=not autopilot.is_running,
            key="ap_stop",
        ):
            autopilot.stop()
            st.rerun()

    st.write("")

    # Configuration sliders (hot-update settings while running)
    with st.expander("Autopilot Settings", expanded=False):
        cfg1, cfg2, cfg3 = st.columns(3)
        with cfg1:
            new_poll = st.slider(
                "Poll interval (seconds)",
                min_value=30,
                max_value=300,
                value=autopilot.poll_interval,
                step=10,
                key="ap_poll",
                help="How often the autopilot checks the geopolitical risk score.",
            )
        with cfg2:
            new_routine = st.slider(
                "Routine analysis (seconds)",
                min_value=60,
                max_value=900,
                value=autopilot.routine_interval,
                step=30,
                key="ap_routine",
                help="How often a full AI analysis cycle runs even when risk is stable.",
            )
        with cfg3:
            new_threshold = st.slider(
                "Risk change threshold (points)",
                min_value=1,
                max_value=30,
                value=int(autopilot.risk_change_threshold),
                step=1,
                key="ap_threshold",
                help=(
                    "Minimum point change in risk score required to trigger "
                    "an immediate reactive trade cycle."
                ),
            )

        if st.button("Apply Settings", key="ap_apply"):
            autopilot.update_settings(
                poll_interval=new_poll,
                routine_interval=new_routine,
                risk_threshold=float(new_threshold),
            )
            st.success("Settings applied.")

    st.write("")

    # Live activity log
    section_header("Live Activity Log")
    col_log, col_refresh = st.columns([5, 1])
    with col_refresh:
        if st.button("Refresh", key="ap_log_refresh"):
            st.rerun()

    log_entries = autopilot.get_activity_log(limit=20)

    if not log_entries:
        st.info("No activity yet. Start the autopilot to begin monitoring.")
    else:
        log_html = []
        for entry in log_entries:
            ts = entry["timestamp"][:19].replace("T", " ")
            kind = entry.get("kind", "monitoring")
            badge = _autopilot_badge(kind)
            msg = entry.get("message", "")
            risk = entry.get("risk_score")
            trades = entry.get("trades_made", 0)

            risk_str = (
                f'<span style="color:#aaa;font-size:0.8em;"> | Risk: {risk:.0f}</span>'
                if risk is not None else ""
            )
            trades_str = (
                f'<span style="color:#00d4aa;font-size:0.8em;"> | {trades} trade(s)</span>'
                if trades > 0 else ""
            )

            log_html.append(
                f'<div class="log-entry">'
                f'<div style="display:flex;align-items:center;gap:8px;">'
                f'<span class="log-ts">{ts} UTC</span>{badge}{risk_str}{trades_str}'
                f'</div>'
                f'<span class="log-msg">{msg}</span>'
                f'</div>'
            )

        st.markdown(
            f'<div style="background:#0d1421;border:1px solid #1e2d45;border-radius:12px;'
            f'padding:12px 16px;max-height:380px;overflow-y:auto;">'
            + "".join(log_html)
            + "</div>",
            unsafe_allow_html=True,
        )

    # Auto-refresh while autopilot is running
    if autopilot.is_running:
        st.caption("Page auto-refreshes every 15 seconds while autopilot is active.")
        import time
        time.sleep(15)
        st.rerun()
