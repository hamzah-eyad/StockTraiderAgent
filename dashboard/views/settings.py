"""Dashboard page: Settings."""
from __future__ import annotations

import streamlit as st
from dashboard.styles import page_header, section_header


def render(agent, engine, autopilot=None):
    page_header("Settings", "API keys, trading parameters, and AI configuration")

    with st.form("settings_form"):
        section_header("API Keys")
        gemini_key = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("gemini_key", ""),
            type="password",
            key="input_gemini_key",
        )
        news_key = st.text_input(
            "NewsAPI Key",
            value=st.session_state.get("news_key", ""),
            type="password",
            key="input_news_key",
        )

        st.divider()
        section_header("Trading Parameters")

        initial_balance = st.number_input(
            "Initial Balance ($)",
            value=st.session_state.get("initial_balance", 100000.0),
            min_value=1000.0,
            step=10000.0,
            key="input_balance",
        )
        commission_rate = st.number_input(
            "Commission Rate",
            value=st.session_state.get("commission_rate", 0.001),
            min_value=0.0,
            max_value=0.1,
            step=0.0005,
            format="%.4f",
            key="input_commission",
        )

        st.divider()
        section_header("AI Agent Configuration")

        watchlist_input = st.text_area(
            "Watchlist (one symbol per line)",
            value=st.session_state.get(
                "watchlist_text",
                "AAPL\nMSFT\nGOOGL\nNVDA\nTSLA\nAMZN\nJPM\nXOM\nLMT\nJNJ",
            ),
            height=150,
            key="input_watchlist",
        )

        model = st.selectbox(
            "Gemini Model",
            ["gemini-2.0-flash-exp", "gemini-2.0-flash", "gemini-2.5-flash"],
            index=0,
            key="input_model",
        )

        submitted = st.form_submit_button("Save Settings", type="primary")

    if submitted:
        st.session_state["gemini_key"] = gemini_key
        st.session_state["news_key"] = news_key
        st.session_state["initial_balance"] = initial_balance
        st.session_state["commission_rate"] = commission_rate
        st.session_state["watchlist_text"] = watchlist_input
        st.session_state["model"] = model

        watchlist = [s.strip().upper() for s in watchlist_input.split("\n") if s.strip()]
        agent.watchlist = watchlist

        if gemini_key:
            from google import genai
            agent._client = genai.Client(api_key=gemini_key)
            agent._api_key = gemini_key
        if model:
            agent._model = model

        if news_key:
            import config
            config.NEWS_API_KEY = news_key

        st.success("Settings saved!")

    st.divider()
    section_header("System Actions")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Reset Portfolio", key="reset_portfolio"):
            engine.portfolio.reset()
            st.success("Portfolio reset to initial balance.")
    with col2:
        if st.button("Clear Analysis History", key="clear_history"):
            agent._analysis_history.clear()
            st.success("Analysis history cleared.")
    with col3:
        if st.button("Clear Cache", key="clear_cache"):
            engine._price_cache.clear()
            st.success("Price cache cleared.")

    st.divider()
    section_header("About")
    st.markdown(
        '<div style="background:#0d1421;border:1px solid #1e2d45;border-radius:12px;padding:18px 20px;">'
        '<div style="color:#e8eaf0;font-weight:600;margin-bottom:10px;">AI Stock Trading Agent</div>'
        '<div style="color:#8b9db8;font-size:0.87rem;line-height:1.7;">'
        'Built on <strong>MCP (Model Context Protocol)</strong> · '
        '<strong>Google Gemini</strong> for analysis · '
        '<strong>yfinance</strong> for market data · '
        '<strong>NewsAPI + VADER</strong> for sentiment · '
        'Paper trading simulation with geopolitical risk awareness.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
