"""Dashboard page: Settings."""
from __future__ import annotations

import streamlit as st


def render(agent, engine, autopilot=None):
    st.header("Settings")

    with st.form("settings_form"):
        st.subheader("API Keys")
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
        st.subheader("Trading Parameters")

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
        st.subheader("AI Agent Configuration")

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
            ["gemini-3.0-flash", "gemini-2.0-flash", "gemini-2.5-flash"],
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
    st.subheader("System Actions")

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
    st.subheader("About")
    st.markdown("""
    **AI Stock Trading Agent** with MCP Integration
    
    This system uses:
    - **MCP (Model Context Protocol)** to connect the AI to financial data, geopolitical intelligence, and trade execution
    - **Google Gemini** as the LLM brain for analysis and decision-making
    - **yfinance** for real-time and historical stock data
    - **NewsAPI** for global news and sentiment analysis
    - **VADER Sentiment** for news sentiment scoring
    
    The AI agent analyzes both technical indicators and geopolitical risk to make 
    informed trading decisions in a simulated paper trading environment.
    """)
