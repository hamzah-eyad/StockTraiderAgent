"""Dashboard page: Portfolio Risk Metrics."""
from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mcp_servers.risk_metrics_server import get_portfolio_risk_metrics, get_stock_risk_profile


def _sharpe_label_color(sharpe: float | None) -> tuple[str, str]:
    """Return (label, hex-color) based on Sharpe ratio quality."""
    if sharpe is None:
        return "N/A", "#aaaaaa"
    if sharpe >= 1.0:
        return "Excellent", "#00d4aa"
    if sharpe >= 0.5:
        return "Adequate", "#ffa500"
    return "Poor", "#ff4444"


def render(agent, engine, autopilot=None):
    st.header("Portfolio Risk Metrics")
    st.markdown(
        "*Quantitative risk analysis using 1 year of daily return data: "
        "Value at Risk, Sharpe & Sortino ratios, portfolio beta, sector exposure, and max drawdown.*"
    )

    # ── Compute portfolio-level metrics ───────────────────────────────────────
    with st.spinner("Computing portfolio risk metrics..."):
        raw = json.loads(get_portfolio_risk_metrics())

    if raw.get("status") == "error":
        st.error(f"Could not compute risk metrics: {raw.get('message')}")
        return

    if raw.get("positions_count", 0) == 0:
        st.info(
            raw.get(
                "message",
                "No open positions found. Make some trades first to see portfolio risk metrics.",
            )
        )
        return

    # ── Key metric cards (row 1) ──────────────────────────────────────────────
    st.subheader("Portfolio Risk Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Portfolio Value",      f"${raw['portfolio_value']:,.2f}")
    c2.metric("Annualized Volatility", f"{raw['annualized_volatility_pct']:.2f}%")
    beta = raw.get("portfolio_beta")
    c3.metric("Beta vs S&P 500",      f"{beta:.2f}" if beta is not None else "N/A")
    c4.metric("Max Drawdown",         f"{raw['max_drawdown_pct']:.2f}%",
              delta=None, help="Largest peak-to-trough decline over the lookback period.")

    # ── Key metric cards (row 2) ──────────────────────────────────────────────
    c5, c6, c7, c8 = st.columns(4)
    sharpe  = raw.get("sharpe_ratio")
    sortino = raw.get("sortino_ratio")
    var95   = raw.get("var_95")
    var99   = raw.get("var_99")

    c5.metric("Sharpe Ratio",  f"{sharpe:.3f}" if sharpe is not None else "N/A")
    c6.metric("Sortino Ratio", f"{sortino:.3f}" if sortino is not None else "N/A")
    c7.metric(
        "VaR 95% (1-day)",
        f"${var95:,.2f}" if var95 is not None else "N/A",
        help="Worst expected 1-day portfolio loss at 95% confidence (historical simulation).",
    )
    c8.metric(
        "VaR 99% (1-day)",
        f"${var99:,.2f}" if var99 is not None else "N/A",
        help="Worst expected 1-day portfolio loss at 99% confidence (historical simulation).",
    )

    sharpe_label, sharpe_color = _sharpe_label_color(sharpe)
    st.markdown(
        f"Sharpe assessment: "
        f'<span style="color:{sharpe_color}; font-weight:bold;">{sharpe_label}</span>'
        f" &nbsp;*(>1.0 = excellent, 0.5–1.0 = adequate, <0.5 = poor risk-adjusted return)*",
        unsafe_allow_html=True,
    )

    st.caption(
        f"Based on **{raw.get('data_points', 0)} trading days** of return data "
        f"({raw.get('lookback_period', '1y')} lookback, 5% risk-free rate assumed). "
        f"Portfolio holds **{raw.get('positions_count', 0)} position(s)**."
    )

    st.divider()

    # ── Sector concentration ──────────────────────────────────────────────────
    sector_weights = raw.get("sector_weights", {})
    if sector_weights:
        st.subheader("Sector Concentration")

        col_pie, col_table = st.columns([1, 1])

        with col_pie:
            fig = go.Figure(go.Pie(
                labels=list(sector_weights.keys()),
                values=list(sector_weights.values()),
                hole=0.42,
                textinfo="label+percent",
                hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
            ))
            fig.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=280,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_table:
            sector_df = pd.DataFrame([
                {"Sector": k, "Weight %": f"{v:.1f}%"}
                for k, v in sector_weights.items()
            ])
            st.dataframe(sector_df, use_container_width=True, hide_index=True)

            top_sector = next(iter(sector_weights))
            top_pct = sector_weights[top_sector]
            if top_pct > 50:
                st.warning(
                    f"High concentration: {top_sector} makes up {top_pct:.1f}% of the portfolio. "
                    "Consider diversifying to reduce sector-specific risk."
                )

    st.divider()

    # ── Per-stock risk profiles ───────────────────────────────────────────────
    st.subheader("Individual Stock Risk Profiles")

    portfolio = engine.get_portfolio()
    positions = portfolio.get("positions", {})

    if not positions:
        st.info("No positions to profile.")
        return

    period_choice = st.selectbox(
        "Lookback period",
        options=["1y", "6mo", "3mo", "2y"],
        index=0,
        key="risk_period",
    )

    if st.button("Load Per-Stock Risk Profiles", type="secondary"):
        profiles = []
        with st.spinner(f"Fetching {period_choice} return data for {len(positions)} position(s)..."):
            for sym in positions:
                prof = json.loads(get_stock_risk_profile(sym, period_choice))
                if prof.get("status") == "success":
                    profiles.append({
                        "Symbol":      sym,
                        "Company":     prof.get("company_name", sym),
                        "Sector":      prof.get("sector", "—"),
                        "Ann. Vol %":  prof.get("annualized_volatility_pct"),
                        "Beta":        prof.get("beta_vs_spy"),
                        "Max DD %":    prof.get("max_drawdown_pct"),
                        "Sharpe":      prof.get("sharpe_ratio"),
                        "Avg Daily %": prof.get("avg_daily_return_pct"),
                    })

        if profiles:
            prof_df = pd.DataFrame(profiles)

            def _color_sharpe(val) -> str:
                try:
                    v = float(val)
                    if v >= 1.0:
                        return "color: #00d4aa"
                    if v >= 0.5:
                        return "color: #ffa500"
                    return "color: #ff4444"
                except (TypeError, ValueError):
                    return ""

            def _color_drawdown(val) -> str:
                try:
                    v = float(val)
                    if v < -20:
                        return "color: #ff4444"
                    if v < -10:
                        return "color: #ffa500"
                except (TypeError, ValueError):
                    pass
                return ""

            styled = (
                prof_df.style
                .map(_color_sharpe, subset=["Sharpe"])
                .map(_color_drawdown, subset=["Max DD %"])
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.warning("Could not load risk profiles for any held position.")
