"""Dashboard page: Watchlist."""
from __future__ import annotations

import json
import streamlit as st
import pandas as pd

from mcp_servers.watchlist_server import add_to_watchlist, remove_from_watchlist, get_watchlist_snapshot, clear_watchlist
from dashboard.styles import page_header, section_header


def render(agent, engine, autopilot=None):
    page_header("My Watchlist", "Live prices and performance for stocks you're tracking")

    # ── Snapshot ───────────────────────────────────────────────────
    section_header("Live Snapshot")

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
        st.info("Your watchlist is currently empty. Add stocks below.")
    else:
        cols = st.columns(4)
        cards_html = []
        for item in snapshot:
            if item.get("status") == "error":
                continue
            ticker = item.get("ticker", "UNKNOWN")
            current = item.get("current_price", 0.0)
            daily_change = item.get("daily_change_pct", 0.0)
            total_change = item.get("change_since_added_pct", 0.0)
            note = item.get("note", "")
            d_color = "ticker-delta-pos" if daily_change >= 0 else "ticker-delta-neg"
            t_color = "ticker-delta-pos" if total_change >= 0 else "ticker-delta-neg"
            note_html = f'<div class="ticker-note">{note}</div>' if note else ""
            cards_html.append(
                f'<div class="ticker-card">'
                f'<div class="ticker-sym">{ticker}</div>'
                f'<div class="ticker-price">${current:,.2f}</div>'
                f'<div class="{d_color}">{daily_change:+.2f}% today</div>'
                f'<div class="{t_color}" style="margin-top:2px;">{total_change:+.2f}% since added</div>'
                f'{note_html}'
                f'</div>'
            )

        cols = st.columns(min(4, len(cards_html)))
        for i, html in enumerate(cards_html):
            with cols[i % len(cols)]:
                st.markdown(html, unsafe_allow_html=True)

    st.divider()

    # ── Management ─────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        section_header("Add Stock")
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
        section_header("Remove Stock")
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
