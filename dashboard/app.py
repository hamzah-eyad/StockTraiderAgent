"""
Main Streamlit Dashboard Application.
Run with: streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import streamlit as st

st.set_page_config(
    page_title="AI Stock Trading Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from simulator.paper_trading import PaperTradingEngine
from mcp_servers.trade_server import set_engine
from agent.trading_agent import TradingAgent
from agent.autopilot import Autopilot


@st.cache_resource
def get_engine():
    engine = PaperTradingEngine()
    set_engine(engine)
    return engine


@st.cache_resource
def get_agent():
    return TradingAgent()


@st.cache_resource
def get_autopilot():
    return Autopilot(agent=get_agent())


engine = get_engine()
agent = get_agent()
autopilot = get_autopilot()

# Sidebar navigation
st.sidebar.title("AI Stock Trading Agent")
st.sidebar.markdown("*MCP-Powered Geopolitical Risk Analysis*")
st.sidebar.divider()

pages = {
    "Overview": "overview",
    "AI Assistant": "chatbot",
    "My Portfolio": "portfolio",
    "Manual Trade": "manual_trade",
    "Stock Analysis": "stock_analysis",
    "Geopolitical Risk": "geopolitical_risk",
    "Trade History": "trade_history",
    "Backtesting": "backtesting_page",
    "Banking (Open Banking)": "banking",
    "Price Alerts": "price_alerts",
    "Watchlist": "watchlist",
    "Pattern Scanner": "pattern_scanner",
    "Risk Metrics": "risk_metrics",
    "Settings": "settings",
}

selected = st.sidebar.radio("Navigation", list(pages.keys()), key="nav")

st.sidebar.divider()

# Sidebar quick info
try:
    balance = engine.get_account_balance()
    from mcp_servers.banking_server import get_bank_accounts
    bank_data = json.loads(get_bank_accounts())
    bank_cash = sum(a["balance"] for a in bank_data.get("accounts", []))
    net_worth = balance['total_value'] + bank_cash
    
    st.sidebar.metric("Total Net Worth", f"${net_worth:,.2f}")
    st.sidebar.metric("Portfolio Value", f"${balance['total_value']:,.2f}")
    st.sidebar.metric("Cash (Brokerage)", f"${balance['cash']:,.2f}")
    st.sidebar.metric("Return", f"{balance['total_return_pct']:+.2f}%")
except Exception:
    st.sidebar.text("Portfolio loading...")

st.sidebar.divider()

# Sidebar autopilot status
st.sidebar.subheader("Autopilot")
if autopilot.is_running:
    st.sidebar.markdown(
        '<span style="background:#00d4aa;color:black;padding:3px 10px;'
        'border-radius:10px;font-weight:bold;">● RUNNING</span>',
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        '<span style="background:#555;color:white;padding:3px 10px;'
        'border-radius:10px;font-weight:bold;">○ STOPPED</span>',
        unsafe_allow_html=True,
    )

if autopilot.current_risk > 0:
    risk_color = (
        "#00d4aa" if autopilot.current_risk < 30
        else "#ffa500" if autopilot.current_risk < 70
        else "#ff4444"
    )
    st.sidebar.markdown(
        f'<span style="font-size:0.85em;color:#aaa;">Risk Score: </span>'
        f'<span style="color:{risk_color};font-weight:bold;">'
        f'{autopilot.current_risk:.0f}</span>',
        unsafe_allow_html=True,
    )

if autopilot.last_action_time:
    st.sidebar.caption(
        f"Last action: {autopilot.last_action_time.strftime('%H:%M:%S UTC')}"
    )

st.sidebar.divider()

# AI Chat in sidebar
st.sidebar.subheader("Quick AI Chat")
st.sidebar.caption("For multi-turn chat, open the **AI Assistant** page.")
user_input = st.sidebar.text_input("Ask the AI agent anything...", key="sidebar_chat")
if user_input:
    with st.sidebar:
        with st.spinner("Thinking..."):
            try:
                response = agent.chat(user_input)
                st.markdown(response)
            except Exception as e:
                st.error(f"Error: {e}")

# Render selected page
page_module = pages[selected]

import importlib

view = importlib.import_module(f"dashboard.views.{page_module}")
view.render(agent, engine, autopilot)
