"""Dashboard page: Technical Pattern Scanner."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from mcp_servers.pattern_scanner_server import get_signal_summary, scan_patterns

DEFAULT_SYMBOLS = "AAPL,MSFT,GOOGL,NVDA,TSLA,AMZN,JPM,XOM,LMT,JNJ"

BIAS_COLOR = {
    "bullish": "#00d4aa",
    "bearish": "#ff4444",
    "neutral":  "#aaaaaa",
}

SIGNAL_LABELS: dict[str, tuple[str, bool]] = {
    "golden_cross":       ("Golden Cross — SMA50 crossed above SMA200 (recent)", True),
    "death_cross":        ("Death Cross — SMA50 crossed below SMA200 (recent)", False),
    "sma50_above_sma200": ("SMA50 Above SMA200 — sustained uptrend", True),
    "rsi_oversold":       ("RSI Oversold (<30) — potential reversal up", True),
    "rsi_overbought":     ("RSI Overbought (>70) — potential reversal down", False),
    "macd_bullish_cross": ("MACD Bullish Crossover — momentum turning up", True),
    "macd_bearish_cross": ("MACD Bearish Crossover — momentum turning down", False),
    "bb_lower_break":     ("Price Below Bollinger Lower Band — oversold zone", True),
    "bb_upper_break":     ("Price Above Bollinger Upper Band — overbought zone", False),
}


def render(agent, engine, autopilot=None):
    st.header("Technical Pattern Scanner")
    st.markdown(
        "*Sweep multiple stocks for active technical signals — SMA crossovers, RSI, MACD, "
        "and Bollinger Bands — and get an instant bullish/bearish/neutral verdict for each.*"
    )

    # ── Input row ─────────────────────────────────────────────────────────────
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        symbols_input = st.text_input(
            "Symbols to scan (comma-separated)",
            value=DEFAULT_SYMBOLS,
            placeholder="AAPL,MSFT,NVDA",
            label_visibility="collapsed",
        )
    with col_btn:
        run_scan = st.button("Scan", type="primary", use_container_width=True)

    if run_scan or "scanner_results" not in st.session_state:
        with st.spinner(
            f"Fetching 6 months of daily data for {len(symbols_input.split(','))} stocks and computing signals..."
        ):
            raw = json.loads(scan_patterns(symbols_input))
            st.session_state["scanner_results"] = raw
            st.session_state["scanner_input"] = symbols_input

    data = st.session_state.get("scanner_results", {})

    if data.get("status") == "error":
        st.error(data.get("message"))
        return

    results = data.get("results", [])
    if not results:
        st.info("No results yet. Enter tickers above and click Scan.")
        return

    # ── Summary badges ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks Scanned", data.get("scanned", 0))
    c2.metric("Bullish", data.get("bullish_count", 0))
    c3.metric("Bearish", data.get("bearish_count", 0))
    c4.metric("Neutral", data.get("neutral_count", 0))

    st.divider()

    # ── Results table ─────────────────────────────────────────────────────────
    st.subheader("Signal Overview")
    st.caption("Sorted by signal score — most bullish first. Score = bullish signals − bearish signals.")

    rows = []
    for r in results:
        if r.get("error"):
            rows.append({
                "Symbol": r["symbol"], "Price": "—", "Bias": "Error",
                "Score": 0, "RSI": "—", "MACD Diff": "—",
                "Golden X": "", "Death X": "", "RSI O/S": "", "RSI O/B": "",
                "MACD ↑": "", "BB Break": "",
            })
        else:
            sig = r.get("signals", {})
            rows.append({
                "Symbol":    r["symbol"],
                "Price":     f"${r.get('current_price', 0):,.2f}",
                "Bias":      r.get("bias", "neutral").capitalize(),
                "Score":     r.get("signal_score", 0),
                "RSI":       f"{r.get('rsi', 0):.1f}",
                "MACD Diff": f"{r.get('macd_diff', 0):.4f}",
                "Golden X":  "✓" if sig.get("golden_cross") else "",
                "Death X":   "✓" if sig.get("death_cross") else "",
                "RSI O/S":   "✓" if sig.get("rsi_oversold") else "",
                "RSI O/B":   "✓" if sig.get("rsi_overbought") else "",
                "MACD ↑":    "✓" if sig.get("macd_bullish_cross") else "",
                "BB Break":  "↓" if sig.get("bb_lower_break") else ("↑" if sig.get("bb_upper_break") else ""),
            })

    df = pd.DataFrame(rows)

    def _color_bias(val: str) -> str:
        v = val.lower()
        if v == "bullish":
            return "color: #00d4aa; font-weight: bold"
        if v == "bearish":
            return "color: #ff4444; font-weight: bold"
        if v == "error":
            return "color: #ff8c00"
        return "color: #aaaaaa"

    def _color_score(val) -> str:
        try:
            v = int(val)
            if v > 0:
                return "color: #00d4aa; font-weight: bold"
            if v < 0:
                return "color: #ff4444; font-weight: bold"
        except (TypeError, ValueError):
            pass
        return ""

    styled = df.style.map(_color_bias, subset=["Bias"]).map(_color_score, subset=["Score"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()

    # ── Per-stock deep-dive ───────────────────────────────────────────────────
    st.subheader("Stock Deep-Dive")

    valid_symbols = [r["symbol"] for r in results if not r.get("error")]
    if not valid_symbols:
        st.info("No valid symbols to drill into.")
        return

    selected_sym = st.selectbox("Select a stock for full signal breakdown", options=valid_symbols)

    if selected_sym:
        with st.spinner(f"Loading signal details for {selected_sym}..."):
            detail = json.loads(get_signal_summary(selected_sym))

        if detail.get("status") == "error":
            st.error(detail.get("message"))
            return

        bias = detail.get("bias", "neutral")
        score = detail.get("signal_score", 0)
        color = BIAS_COLOR.get(bias, "#aaaaaa")

        st.markdown(
            f"**{selected_sym}** &nbsp;—&nbsp; "
            f'<span style="color:{color}; font-weight:bold; font-size:1.15em;">'
            f"{bias.upper()}</span> &nbsp; "
            f'<span style="color:#888;">(signal score: {score:+d})</span>',
            unsafe_allow_html=True,
        )

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Current Price",  f"${detail.get('current_price', 0):,.2f}")
        mc2.metric("RSI (14)",       f"{detail.get('rsi', 0):.1f}")
        mc3.metric("MACD Diff",      f"{detail.get('macd_diff', 0):.4f}")
        mc4.metric("SMA 50",         f"${detail.get('sma_50', 0):,.2f}")

        bc1, bc2 = st.columns(2)
        bc1.metric("Bollinger Upper", f"${detail.get('bb_upper', 0):,.2f}")
        bc2.metric("Bollinger Lower", f"${detail.get('bb_lower', 0):,.2f}")

        st.markdown("**Active Signals:**")
        sigs = detail.get("signals", {})
        active_any = False
        for key, (label, is_bullish) in SIGNAL_LABELS.items():
            if sigs.get(key):
                icon = "🟢" if is_bullish else "🔴"
                st.write(f"{icon} {label}")
                active_any = True
        if not active_any:
            st.write("No strong signals detected at this time.")
