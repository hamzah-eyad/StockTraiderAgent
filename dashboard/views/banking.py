"""Dashboard page: Banking & Open Banking Simulation."""
from __future__ import annotations

import json
import streamlit as st
from datetime import datetime
from mcp_servers.banking_server import get_bank_accounts, get_bank_transactions, initiate_brokerage_transfer
from dashboard.components.widgets import metric_card

def render(agent, engine, autopilot=None):
    st.header("Open Banking Integration")
    st.markdown("*Simulated multi-bank account management and fund transfers*")
    
    # ── Bank Summary ──────────────────────────────────────────────────
    try:
        accounts_data = json.loads(get_bank_accounts())
        accounts = accounts_data.get("accounts", [])
    except Exception as e:
        st.error(f"Failed to fetch bank accounts: {e}")
        accounts = []

    if not accounts:
        st.warning("No bank accounts linked.")
        if st.button("Link New Bank Account (Simulated)"):
            st.info("Linking flow initiated... (This is a simulation)")
        return

    # Aggregate Metrics
    total_bank_cash = sum(a["balance"] for a in accounts)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Total Bank Balance", f"${total_bank_cash:,.2f}")
    with col2:
        try:
            brokerage_balance = engine.get_account_balance()
            metric_card("Brokerage Cash", f"${brokerage_balance['cash']:,.2f}")
        except:
            st.text("Brokerage loading...")
    with col3:
        try:
            net_worth = total_bank_cash + brokerage_balance['total_value']
            metric_card("Total Net Worth", f"${net_worth:,.2f}", delta=None)
        except:
            st.text("Net worth loading...")

    st.divider()

    # ── Account Details ───────────────────────────────────────────────
    left, right = st.columns([1, 1])
    
    with left:
        st.subheader("Linked Accounts")
        for acc in accounts:
            with st.container():
                st.markdown(
                    f'<div style="background:#111;padding:15px;border-radius:10px;margin-bottom:10px;border-left:5px solid #00d4aa;">'
                    f'<h4 style="margin:0;">{acc["name"]}</h4>'
                    f'<p style="color:#888;margin:0;">{acc["type"].capitalize()} • {acc["id"]}</p>'
                    f'<h2 style="margin:10px 0;">${acc["balance"]:,.2f}</h2>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                # Transfer Action
                with st.expander(f"Transfer to Brokerage from {acc['name']}"):
                    amount = st.number_input(f"Amount", min_value=100.0, max_value=acc["balance"], value=1000.0, key=f"amt_{acc['id']}")
                    if st.button(f"Confirm Transfer", key=f"btn_{acc['id']}"):
                        with st.spinner("Processing bank transfer..."):
                            result = json.loads(initiate_brokerage_transfer(amount, acc["id"]))
                            if "error" in result:
                                st.error(result["error"])
                            else:
                                # Update brokerage cash
                                engine.portfolio.cash += amount
                                st.success(f"Successfully transferred ${amount:,.2f} to your brokerage account.")
                                st.rerun()

    with right:
        st.subheader("Recent Banking Transactions")
        try:
            tx_data = json.loads(get_bank_transactions(limit=15))
            transactions = tx_data.get("transactions", [])
            
            if not transactions:
                st.info("No recent transactions found.")
            else:
                for tx in transactions:
                    is_income = tx["amount"] > 0
                    color = "#00d4aa" if is_income else "#ff4444"
                    sign = "+" if is_income else ""
                    date_str = datetime.fromisoformat(tx["date"]).strftime("%b %d, %H:%M")
                    
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #222;">'
                        f'<div>'
                        f'<strong>{tx["description"]}</strong><br>'
                        f'<span style="color:#555;font-size:0.8em;">{date_str} • {tx["category"]}</span>'
                        f'</div>'
                        f'<div style="color:{color};font-weight:bold;">{sign}${abs(tx["amount"]):,.2f}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        except Exception as e:
            st.error(f"Failed to fetch transactions: {e}")

    st.divider()
    st.subheader("AI Agent Awareness")
    st.info("The AI Trading Agent is now aware of your bank balances. During market analysis, "
            "it may suggest funding your brokerage account if it detects high-conviction "
            "opportunities that exceed your current brokerage cash.")
