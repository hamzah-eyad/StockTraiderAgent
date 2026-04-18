"""Dashboard page: Watchlist."""
from __future__ import annotations

import json
import streamlit as st
import pandas as pd

from mcp_servers.watchlist_server import add_to_watchlist, remove_from_watchlist, get_watchlist_snapshot, clear_watchlist

def render(agent, engine, autopilot=None):
    st.header("My Watchlist")
    st.markdown("*Track live prices for specific stocks of interest.*")
    
    # ── Snapshot ───────────────────────────────────────────────────
    st.subheader("Live Snapshot")
    
    try:
        snapshot_data = json.loads(get_watchlist_snapshot())
        if snapshot_data.get("status") == "error":
            st.error(snapshot_data.get("message"))
            snapshot = []
        else:
            snapshot = snapshot_data.get("snapshot", [])
    except Exception as e:
        st.error(f"Failed to fetch watchlist snapshot: {e}")
        snapshot = []
        
    if not snapshot:
        st.info("Your watchlist is currently empty.")
    else:
        # Display as a clean grid of metrics
        cols = st.columns(4)
        for i, item in enumerate(snapshot):
            if item.get("status") == "error":
                continue # Skip errored items
                
            ticker = item.get("ticker", "UNKNOWN")
            current = item.get("current_price", 0.0)
            daily_change = item.get("daily_change_pct", 0.0)
            added_price = item.get("added_price", 0.0)
            total_change = item.get("change_since_added_pct", 0.0)
            
            with cols[i % 4]:
                st.metric(
                    label=ticker, 
                    value=f"${current:,.2f}", 
                    delta=f"{daily_change:+.2f}% Daily | {total_change:+.2f}% Total"
                )
                if item.get("note"):
                    st.caption(f"📝 {item.get('note')}")
                
    st.divider()

    # ── Management ─────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Add Stock")
        with st.form("add_watchlist_form"):
            new_ticker = st.text_input("Ticker Symbol", value="")
            new_note = st.text_input("Note (optional)")
            submitted = st.form_submit_button("Add to Watchlist")
            
            if submitted:
                if not new_ticker:
                    st.error("Ticker symbol is required.")
                else:
                    with st.spinner(f"Adding {new_ticker}..."):
                        res = json.loads(add_to_watchlist(new_ticker.upper(), new_note))
                        if res.get("status") == "success":
                            st.success(res.get("message"))
                            st.rerun()
                        else:
                            st.error(res.get("message"))
                            
    with col2:
        st.subheader("Remove Stock")
        with st.form("remove_watchlist_form"):
            # Provide a dropdown of current tickers
            current_tickers = [item.get("ticker") for item in snapshot if "ticker" in item]
            rem_ticker = st.selectbox("Select Ticker", options=[""] + current_tickers)
            removed = st.form_submit_button("Remove")
            
            if removed:
                if not rem_ticker:
                    st.warning("Please select a ticker to remove.")
                else:
                    res = json.loads(remove_from_watchlist(rem_ticker))
                    if res.get("status") == "success":
                        st.success(res.get("message"))
                        st.rerun()
                    else:
                        st.error(res.get("message"))

        # Clear All
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear Entire Watchlist", type="primary"):
            res = json.loads(clear_watchlist())
            if res.get("status") == "success":
                st.success(res.get("message"))
                st.rerun()
            else:
                st.error(res.get("message"))
