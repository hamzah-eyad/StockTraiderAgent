"""Dashboard page: Banking — Plaid Sandbox Demo + Real Bank Linking."""
from __future__ import annotations

import json
import streamlit as st
from datetime import datetime

# ── Banking server tools ───────────────────────────────────────────────────────
from mcp_servers.banking_server import (
    get_bank_accounts,
    get_bank_transactions,
    get_real_bank_accounts,
    get_real_bank_transactions,
    get_linked_real_banks,
    create_plaid_link_token,
    remove_linked_bank,
    initiate_brokerage_transfer,
    refresh_plaid_connection,
    get_plaid_connection_status,
)
from dashboard.components.widgets import metric_card

# ── Plaid Link callback server (started lazily) ────────────────────────────────
from dashboard.plaid_link_server import start_callback_server, link_page_url, CALLBACK_PORT

import webbrowser


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _source_badge(source: str):
    if source == "plaid_sandbox":
        st.markdown(
            '<span style="background:#00d4aa22;color:#00d4aa;padding:4px 12px;'
            'border-radius:20px;font-size:0.75em;border:1px solid #00d4aa55;">'
            '🏦 Plaid Sandbox · First Platypus Bank</span>',
            unsafe_allow_html=True,
        )
    elif source == "plaid_real":
        st.markdown(
            '<span style="background:#4f8ef722;color:#4f8ef7;padding:4px 12px;'
            'border-radius:20px;font-size:0.75em;border:1px solid #4f8ef755;">'
            '🏦 Plaid · Live Bank Data</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span style="background:#ff990022;color:#ff9900;padding:4px 12px;'
            'border-radius:20px;font-size:0.75em;border:1px solid #ff990055;">'
            '⚠️ Simulation Mode</span>',
            unsafe_allow_html=True,
        )


def _account_card(acc: dict, engine, show_transfer: bool = True):
    mask = acc.get("mask", "****")
    subtype = acc.get("subtype", acc.get("type", "account"))
    available = acc.get("available", acc.get("balance", 0))
    institution = acc.get("institution", "")

    st.markdown(
        f'<div style="background:#111;padding:16px;border-radius:12px;'
        f'margin-bottom:12px;border-left:5px solid #00d4aa;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div>'
        f'<h4 style="margin:0;">{acc["name"]}</h4>'
        f'<p style="color:#888;margin:4px 0 0;font-size:0.82em;">'
        f'{institution} · {subtype.capitalize()} · ···{mask}</p>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<h2 style="margin:0;color:#00d4aa;">${acc["balance"]:,.2f}</h2>'
        f'<p style="color:#555;margin:0;font-size:0.78em;">Available: ${available:,.2f}</p>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if show_transfer and engine:
        with st.expander(f"💸 Transfer to Brokerage from {acc['name']}"):
            max_val = float(available) if available >= 100 else float(acc["balance"])
            if max_val < 100:
                st.warning("Minimum transfer is $100.")
            else:
                amount = st.number_input(
                    "Amount ($)", min_value=100.0, max_value=max_val,
                    value=min(500.0, max_val), step=100.0, key=f"xfr_{acc['id']}")
                if st.button("Confirm Transfer", key=f"btn_{acc['id']}"):
                    with st.spinner("Processing…"):
                        res = json.loads(initiate_brokerage_transfer(amount, acc["id"]))
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        engine.portfolio.cash += amount
                        note = res.get("note", "")
                        st.success(f"✅ Transferred **${amount:,.2f}** to brokerage." + (f"\n\n_{note}_" if note else ""))
                        st.rerun()


def _tx_feed(transactions: list[dict]):
    if not transactions:
        st.info("No transactions found.")
        return
    for tx in transactions:
        is_income = tx["amount"] > 0
        color = "#00d4aa" if is_income else "#ff6b6b"
        sign = "+" if is_income else ""
        try:
            raw = tx.get("date", "")
            date_str = datetime.fromisoformat(str(raw)).strftime("%b %d, %H:%M") if "T" in str(raw) else str(raw)
        except Exception:
            date_str = str(tx.get("date", ""))
        merchant = tx.get("merchant") or tx.get("description", "")
        category = tx.get("category", "Uncategorized")
        institution = tx.get("institution", "")
        pending = ' <span style="font-size:0.72em;color:#ff9900">⏳</span>' if tx.get("pending") else ""
        inst_tag = f' · {institution}' if institution else ""
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:10px 0;border-bottom:1px solid #1e1e1e;">'
            f'<div style="flex:1;min-width:0;">'
            f'<strong style="font-size:0.9em;">{merchant}</strong>{pending}<br>'
            f'<span style="color:#555;font-size:0.78em;">{date_str} · {category}{inst_tag}</span>'
            f'</div>'
            f'<div style="color:{color};font-weight:700;margin-left:12px;white-space:nowrap;">'
            f'{sign}${abs(tx["amount"]):,.2f}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )



# ─────────────────────────────────────────────────────────────────────────────

# Main render function
# ─────────────────────────────────────────────────────────────────────────────
def render(agent, engine, autopilot=None):
    # Start the Plaid Link callback server (daemon thread, safe to call multiple times)
    start_callback_server()

    st.header("Open Banking Integration")

    # ── Global status ──────────────────────────────────────────────────────
    try:
        status = json.loads(get_plaid_connection_status())
        is_configured = status.get("configured", False)
        real_banks = status.get("real_banks_linked", 0)
    except Exception:
        is_configured = False
        real_banks = 0

    if not is_configured:
        st.warning(
            "⚠️ **Plaid not configured.** Add `PLAID_CLIENT_ID` and `PLAID_SECRET` to `.env` "
            "to enable real open banking. Using simulated data until then.",
            icon="⚠️",
        )

    # ── Mode tabs ──────────────────────────────────────────────────────────
    tab_sandbox, tab_real = st.tabs([
        "🏖️  Sandbox Demo (First Platypus Bank)",
        f"🏦  Link Your Real Bank {'✅' if real_banks > 0 else ''}",
    ])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — SANDBOX DEMO
    # ══════════════════════════════════════════════════════════════════════
    with tab_sandbox:
        st.subheader("Plaid Sandbox — First Platypus Bank")
        st.markdown(
            "This connects to Plaid's **official test bank** with pre-built virtual accounts. "
            "No real money — perfect for demoing the full open banking flow."
        )

        col_badge, col_refresh = st.columns([4, 1])
        with col_badge:
            _source_badge("plaid_sandbox" if is_configured else "simulation")
        with col_refresh:
            if st.button("🔄 Reset Token", help="Delete cached sandbox token and create a fresh one"):
                with st.spinner("Refreshing…"):
                    r = json.loads(refresh_plaid_connection())
                    (st.success if r.get("status") == "success" else st.warning)(r.get("message", "Done"))
                st.rerun()

        st.divider()

        # Accounts
        try:
            accts_raw = json.loads(get_bank_accounts())
            accounts = accts_raw.get("accounts", [])
            source = accts_raw.get("source", "simulation")
            if accts_raw.get("warning"):
                st.info(accts_raw["warning"])
        except Exception as e:
            st.error(f"Failed to load accounts: {e}")
            accounts, source = [], "simulation"

        if accounts:
            # Summary metrics
            total_bank = sum(a["balance"] for a in accounts)
            col1, col2, col3 = st.columns(3)
            with col1:
                metric_card("Total Bank Balance", f"${total_bank:,.2f}")
            with col2:
                try:
                    b = engine.get_account_balance()
                    metric_card("Brokerage Cash", f"${b['cash']:,.2f}")
                except Exception:
                    b = {"cash": 0, "total_value": 0}
                    st.text("Brokerage loading…")
            with col3:
                try:
                    metric_card("Total Net Worth", f"${total_bank + b.get('total_value', 0):,.2f}")
                except Exception:
                    st.text("Net worth loading…")

            st.divider()
            left, right = st.columns(2)

            with left:
                st.subheader("Accounts")
                for acc in accounts:
                    _account_card(acc, engine)

            with right:
                st.subheader("Recent Transactions")
                st.caption("Plaid sandbox transactions — realistic merchant data")
                try:
                    tx_raw = json.loads(get_bank_transactions(limit=20))
                    _tx_feed(tx_raw.get("transactions", []))
                except Exception as e:
                    st.error(f"Error loading transactions: {e}")
        else:
            st.info("No sandbox accounts found. Click **Reset Token** to create a fresh connection.")

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — REAL BANK LINKING
    # ══════════════════════════════════════════════════════════════════════
    with tab_real:
        st.subheader("Link Your Own Bank Account")
        st.markdown(
            "Connect any of **12,000+ real banks** through Plaid's secure flow. "
            "Your bank credentials are entered directly on Plaid's servers — "
            "**this app never sees your password.**"
        )

        if not is_configured:
            st.error(
                "Plaid is not configured. "
                "Set `PLAID_CLIENT_ID` and `PLAID_SECRET` in `.env` first.",
                icon="🔐",
            )
            st.stop()

        # ── Currently linked banks ─────────────────────────────────────
        try:
            linked = json.loads(get_linked_real_banks()).get("banks", [])
        except Exception:
            linked = []

        if linked:
            st.success(f"✅ {len(linked)} bank(s) linked", icon="✅")
            for bank in linked:
                bc1, bc2 = st.columns([5, 1])
                with bc1:
                    linked_at = bank.get("linked_at", "")[:10]
                    st.markdown(
                        f'<div style="background:#111;padding:12px 16px;border-radius:10px;'
                        f'border-left:4px solid #4f8ef7;margin-bottom:8px;">'
                        f'<strong>{bank["institution_name"]}</strong>'
                        f'<span style="color:#555;font-size:0.8em;margin-left:10px;">linked {linked_at}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with bc2:
                    if st.button("Unlink", key=f"unlink_{bank['item_id']}"):
                        res = json.loads(remove_linked_bank(bank["item_id"]))
                        st.success(res.get("message", "Removed")) if res.get("status") == "success" else st.error(res.get("error"))
                        st.rerun()
            st.divider()

        # ── Link new bank ─────────────────────────────────────────────
        st.subheader("➕ Connect a New Bank")

        # Session state: hold the link token between reruns
        if "plaid_link_token" not in st.session_state:
            st.session_state.plaid_link_token = None

        col_gen, col_ref = st.columns([3, 1])
        with col_gen:
            if st.button("🔑 Generate Plaid Link Session", type="primary",
                         help="Creates a one-time session token to open the bank-linking page"):
                with st.spinner("Generating secure link session…"):
                    result = json.loads(create_plaid_link_token())
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state.plaid_link_token = result["link_token"]
                    st.session_state.plaid_link_expiry = result.get("expiration", "")
                    # Auto-open the Plaid Link page in a new browser tab
                    url = link_page_url(result["link_token"])
                    webbrowser.open(url)
                    st.success("✅ A new browser tab has opened with the Plaid Link flow!")

        with col_ref:
            if st.button("🔄 Refresh Linked Banks"):
                st.session_state.plaid_link_token = None
                st.rerun()

        # ── Plaid Link instructions & manual link ──────────────────────
        if st.session_state.get("plaid_link_token"):
            expiry = st.session_state.get("plaid_link_expiry", "")
            if expiry:
                st.caption(f"Session expires: {expiry[:19].replace('T', ' ')} UTC")

            url = link_page_url(st.session_state.plaid_link_token)

            st.info(
                "**A new tab should have opened automatically.**  \n"
                f"If it didn't, click here 👉 [Open Plaid Bank Linking Page]({url})\n\n"
                "After linking, come back here and click **🔄 Refresh Linked Banks**.",
                icon="ℹ️",
            )

            # ── Sandbox credentials notice ─────────────────────────────
            st.warning(
                "**🏖️ You are in Plaid Sandbox mode.**\n\n"
                "You can search and select **any bank** (Wise, Chase, HSBC…) in the "
                "Plaid Link popup, but Plaid Sandbox always shows a **mock login page** "
                "called \"First Platypus Bank\" regardless of which bank you picked. "
                "This is normal — it's how Plaid's test environment works.\n\n"
                "**Use these test credentials to complete the linking:**\n\n"
                "| Step | Field | Value |\n"
                "|---|---|---|\n"
                "| Login | Username | `user_good` |\n"
                "| Login | Password | `pass_good` |\n"
                "| MFA / Verification code | Any prompt | `1234` |\n\n"
                "To link a **real Wise / bank account**, you need Plaid Production access "
                "(apply at dashboard.plaid.com, then set `PLAID_ENV=production` in `.env`). "
                "All the code here is already production-ready — only the API secret changes.",
                icon="⚠️",
            )

            st.caption(
                "🔒 In production, your real bank credentials go directly to Plaid's servers. "
                "This app only ever receives a secure token — never your password."
            )

        else:
            st.markdown(
                '<div style="background:#111;padding:20px;border-radius:12px;text-align:center;'
                'border:2px dashed #333;color:#555;">'
                '🏦 Click <strong>Generate Plaid Link Session</strong> above to start'
                '</div>',
                unsafe_allow_html=True,
            )

        # ── Real bank accounts & transactions ─────────────────────────
        if linked:
            st.divider()
            st.subheader("Your Linked Account Data")

            try:
                rb_accts = json.loads(get_real_bank_accounts()).get("accounts", [])
            except Exception as e:
                rb_accts = []
                st.error(f"Error loading accounts: {e}")

            try:
                rb_txs = json.loads(get_real_bank_transactions(limit=25)).get("transactions", [])
            except Exception as e:
                rb_txs = []
                st.error(f"Error loading transactions: {e}")

            if rb_accts:
                total = sum(a["balance"] for a in rb_accts)
                col1, col2, col3 = st.columns(3)
                with col1:
                    metric_card("Real Bank Total", f"${total:,.2f}")
                with col2:
                    try:
                        b = engine.get_account_balance()
                        metric_card("Brokerage Cash", f"${b['cash']:,.2f}")
                    except Exception:
                        b = {"cash": 0, "total_value": 0}
                with col3:
                    try:
                        metric_card("Total Net Worth", f"${total + b.get('total_value', 0):,.2f}")
                    except Exception:
                        pass

                st.divider()
                _source_badge("plaid_real")
                st.write("")

                left2, right2 = st.columns(2)
                with left2:
                    st.subheader("Accounts")
                    for acc in rb_accts:
                        _account_card(acc, engine)
                with right2:
                    st.subheader("Recent Transactions")
                    st.caption("Live data from your linked bank")
                    _tx_feed(rb_txs)
            else:
                st.info("Accounts loading — try clicking **Refresh Linked Banks** after linking.")

    st.divider()
    st.subheader("🤖 AI Agent Awareness")
    total_real = real_banks
    if is_configured:
        msg = (
            f"The AI agent has access to your **Plaid Sandbox** (demo) accounts"
            + (f" and **{total_real} real linked bank(s)**" if total_real > 0 else "")
            + ". It uses this to compare brokerage cash vs bank cash and may suggest funding transfers."
        )
        st.success(msg)
    else:
        st.info("Connect Plaid to give the AI agent awareness of your real financial position.")
