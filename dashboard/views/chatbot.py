"""Dashboard page: AI Assistant — multi-turn chatbot powered by Gemini 2.5 Flash."""
from __future__ import annotations

import streamlit as st

from agent.chat_session import ChatSession
from config import GEMINI_MODEL


STARTER_PROMPTS = [
    "How much money do I have?",
    "What stocks do I own?",
    "Analyze NVDA today",
    "What's the geopolitical risk right now?",
    "How do I run a backtest?",
]


def _get_session() -> ChatSession:
    if "chat_session" not in st.session_state:
        st.session_state["chat_session"] = ChatSession()
    return st.session_state["chat_session"]


def _ensure_state():
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []
    if "pending_trade" not in st.session_state:
        st.session_state["pending_trade"] = None
    if "pending_prompt" not in st.session_state:
        st.session_state["pending_prompt"] = None


def _reset_chat():
    _get_session().reset()
    st.session_state["chat_messages"] = []
    st.session_state["pending_trade"] = None
    st.session_state["pending_prompt"] = None


def _send_message(user_text: str, engine):
    """Append the user turn, call the session, store the assistant turn."""
    session = _get_session()
    st.session_state["chat_messages"].append({"role": "user", "text": user_text})

    try:
        result = session.send(user_text)
    except Exception as e:
        st.session_state["chat_messages"].append({
            "role": "assistant",
            "text": f"Sorry, something went wrong: `{e}`",
            "tool_calls": [],
        })
        return

    st.session_state["chat_messages"].append({
        "role": "assistant",
        "text": result["text"],
        "tool_calls": result.get("tool_calls", []),
        "has_trade": result.get("pending_trade") is not None,
    })
    st.session_state["pending_trade"] = result.get("pending_trade")


def render(agent, engine, autopilot=None):
    _ensure_state()

    # ── Header ────────────────────────────────────────────────────────────────
    top_l, top_r = st.columns([5, 1])
    with top_l:
        st.header("AI Assistant")
        st.caption(
            f"Powered by Google `{GEMINI_MODEL}`. Ask about your money, analyze stocks, "
            "or get guidance on how to use the dashboard. Trades require your confirmation."
        )
    with top_r:
        st.write("")
        if st.button("Clear", help="Reset conversation", use_container_width=True):
            _reset_chat()
            st.rerun()

    # ── Welcome / starter prompts (when empty) ────────────────────────────────
    if not st.session_state["chat_messages"]:
        st.info(
            "Try one of these to get started, or type your own question below. "
            "I can look up live prices, your portfolio, geopolitical risk, and "
            "propose trades that you confirm before they execute."
        )
        chip_cols = st.columns(len(STARTER_PROMPTS))
        for i, prompt in enumerate(STARTER_PROMPTS):
            with chip_cols[i]:
                if st.button(prompt, key=f"starter_{i}", use_container_width=True):
                    st.session_state["pending_prompt"] = prompt
                    st.rerun()

    # ── Handle starter prompt click (set during previous run) ─────────────────
    if st.session_state.get("pending_prompt"):
        prompt = st.session_state.pop("pending_prompt")
        with st.spinner("Thinking..."):
            _send_message(prompt, engine)
        st.rerun()

    # ── Render conversation ───────────────────────────────────────────────────
    for i, msg in enumerate(st.session_state["chat_messages"]):
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                unique = list(dict.fromkeys(tool_calls))
                st.caption(f"_Looked up: {', '.join(f'`{t}`' for t in unique)}_")

            # If the latest assistant message proposed a trade and it's still pending,
            # render the confirmation card inline.
            is_last_assistant = (
                msg["role"] == "assistant"
                and i == len(st.session_state["chat_messages"]) - 1
            )
            if (
                is_last_assistant
                and msg.get("has_trade")
                and st.session_state.get("pending_trade")
            ):
                _render_trade_card(st.session_state["pending_trade"], engine)

    # ── Chat input ────────────────────────────────────────────────────────────
    has_pending = st.session_state.get("pending_trade") is not None
    if has_pending:
        st.warning(
            "Please **Confirm** or **Cancel** the pending trade above before sending "
            "another message."
        )

    user_input = st.chat_input(
        "Ask me about stocks, your portfolio, or how to use the app...",
        disabled=has_pending,
    )
    if user_input:
        with st.spinner("Thinking..."):
            _send_message(user_input, engine)
        st.rerun()


def _render_trade_card(pending: dict, engine):
    """Render the Confirm/Cancel card for a pending trade proposal."""
    side = pending.get("side", "buy").upper()
    symbol = pending.get("symbol", "")
    qty = pending.get("quantity", 0)
    order_type = pending.get("order_type", "market").upper()
    limit_price = pending.get("limit_price")
    reasoning = pending.get("reasoning", "")

    badge_color = "#00d4aa" if side == "BUY" else "#ff8c42"

    detail_lines = [
        f"**Action:** <span style='color:{badge_color};font-weight:bold'>{side}</span>",
        f"**Symbol:** `{symbol}`",
        f"**Quantity:** {qty:g} shares",
        f"**Order type:** {order_type}",
    ]
    if order_type == "LIMIT" and limit_price:
        detail_lines.append(f"**Limit price:** ${float(limit_price):,.2f}")
    if reasoning:
        detail_lines.append(f"**Why:** {reasoning}")

    with st.container(border=True):
        st.markdown("#### Trade proposal — needs your confirmation")
        st.markdown("  \n".join(detail_lines), unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                f"Confirm {side}",
                type="primary",
                key=f"confirm_trade_{symbol}_{side}_{qty}",
                use_container_width=True,
            ):
                session = _get_session()
                with st.spinner("Submitting order..."):
                    result = session.confirm_trade(pending, engine)
                status = result.get("status", "unknown")
                if status == "filled":
                    summary = (
                        f"**Trade filled.** {side} {qty:g} {symbol} "
                        f"@ ${float(result.get('price', 0)):,.2f}."
                    )
                elif status == "pending":
                    summary = (
                        f"**Limit order placed** (ID `{result.get('order_id','')}`). "
                        "See **Trade History** for open orders."
                    )
                elif status == "rejected":
                    summary = f"**Order rejected:** {result.get('reason','no reason')}"
                else:
                    summary = f"**Order status:** {status}. Details: {result}"

                st.session_state["chat_messages"].append({
                    "role": "assistant",
                    "text": summary,
                    "tool_calls": [],
                })
                st.session_state["pending_trade"] = None
                st.rerun()

        with c2:
            if st.button(
                "Cancel",
                key=f"cancel_trade_{symbol}_{side}_{qty}",
                use_container_width=True,
            ):
                session = _get_session()
                session.cancel_trade(pending)
                st.session_state["chat_messages"].append({
                    "role": "assistant",
                    "text": "Trade cancelled. Let me know what you'd like to do next.",
                    "tool_calls": [],
                })
                st.session_state["pending_trade"] = None
                st.rerun()
