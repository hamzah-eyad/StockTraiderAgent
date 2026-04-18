"""Dashboard page: Price Alerts."""
from __future__ import annotations

import json
import streamlit as st
import pandas as pd
from datetime import datetime

from mcp_servers.price_alert_server import set_price_alert, list_alerts, delete_alert, check_alerts
from dashboard.components.widgets import metric_card

def render(agent, engine, autopilot=None):
    st.header("Price Alerts")
    st.markdown("*Set thresholds to be notified when stocks move past specific prices.*")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Create New Alert")
        with st.form("new_alert_form"):
            ticker = st.text_input("Ticker Symbol", value="AAPL")
            condition = st.selectbox("Condition", options=["above", "below"])
            target_price = st.number_input("Target Price", min_value=1.0, value=150.0, step=1.0)
            note = st.text_input("Note (optional)")
            
            submitted = st.form_submit_button("Set Alert")
            if submitted:
                if not ticker:
                    st.error("Ticker symbol is required.")
                else:
                    with st.spinner(f"Setting alert for {ticker}..."):
                        res = json.loads(set_price_alert(ticker.upper(), target_price, condition, note))
                        if res.get("status") == "success":
                            st.success(res.get("message"))
                        else:
                            st.error(res.get("message"))

        st.subheader("Manual Check")
        st.info("The AI Agent typically checks alerts automatically, but you can force a check now.")
        if st.button("Check Triggered Alerts"):
            with st.spinner("Checking live prices against active alerts..."):
                res = json.loads(check_alerts())
                if res.get("status") == "success":
                    if res.get("triggered_count", 0) > 0:
                        st.warning(res.get("message"))
                        for trigger in res.get("triggered", []):
                            st.toast(trigger.get("message", "Alert triggered!"), icon="🔔")
                    else:
                        st.success(res.get("message"))
                else:
                    st.error(res.get("message"))
                    
    with col2:
        st.subheader("Your Alerts")
        status_filter = st.selectbox("Filter by Status", options=["active", "triggered", "deleted", "all"], index=0)
        
        try:
            alerts_data = json.loads(list_alerts(status_filter=status_filter))
            alerts_list = alerts_data.get("alerts", [])
        except Exception as e:
            st.error(f"Failed to fetch alerts: {e}")
            alerts_list = []
            
        if not alerts_list:
            st.info(f"No {status_filter} alerts found.")
        else:
            # Display nicely in a table
            df = pd.DataFrame(alerts_list)
            # Reorder and format columns
            df["time"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
            display_df = df[["alert_id", "ticker", "condition", "target_price", "status", "note", "time"]]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Delete functionality
            if status_filter in ["active", "all"]:
                st.markdown("### Cancel Alert")
                del_id = st.number_input("Enter Alert ID to cancel", min_value=1, step=1)
                if st.button("Delete Alert"):
                    res = json.loads(delete_alert(int(del_id)))
                    if res.get("status") == "success":
                        st.success(res.get("message"))
                        st.rerun()
                    else:
                        st.error(res.get("message"))
