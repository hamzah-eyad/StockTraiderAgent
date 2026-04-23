"""Central design system for the AI Stock Trader dashboard."""
from __future__ import annotations
import streamlit as st

_CSS = """
<style>
/* ── Hide Streamlit chrome ──────────────────────────────────────────── */
#MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }

/* ── Design tokens ──────────────────────────────────────────────────── */
:root {
    --bg-base:     #080d18;
    --bg-card:     #0d1421;
    --bg-card2:    #111827;
    --bg-hover:    #131d2e;
    --border:      #1e2d45;
    --border-dim:  #131d30;
    --accent:      #00d4aa;
    --accent-glow: rgba(0, 212, 170, 0.18);
    --accent-dim:  rgba(0, 212, 170, 0.08);
    --red:         #f44336;
    --red-dim:     rgba(244, 67, 54, 0.1);
    --orange:      #ff9800;
    --blue:        #3b82f6;
    --text-pri:    #e8eaf0;
    --text-sec:    #8b9db8;
    --text-dim:    #3d4f68;
    --radius:      12px;
    --radius-sm:   8px;
}

/* ── App background ─────────────────────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main {
    background-color: var(--bg-base) !important;
}
[data-testid="block-container"] {
    padding-top: 24px !important;
    padding-bottom: 40px !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #060b14 !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stMarkdown p { color: var(--text-sec) !important; font-size: 0.85em; }
[data-testid="stSidebar"] .stMetric {
    background: rgba(255,255,255,0.025);
    border: 1px solid var(--border-dim);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    margin-bottom: 6px;
}
[data-testid="stSidebar"] [data-testid="metric-container"] {
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid var(--border-dim) !important;
    border-radius: var(--radius-sm) !important;
    padding: 10px 12px !important;
    margin-bottom: 6px !important;
}
[data-testid="stSidebar"] [data-testid="metric-container"] label { font-size: 0.72rem !important; }
[data-testid="stSidebar"] [data-testid="stMetricValue"] { font-size: 1.05rem !important; }
[data-testid="stSidebar"] hr { border-color: var(--border-dim) !important; margin: 14px 0 !important; }

/* ── Typography ─────────────────────────────────────────────────────── */
h1 { font-size: 1.7rem !important; font-weight: 700 !important; color: #fff !important;
     letter-spacing: -0.5px !important; line-height: 1.2 !important; }
h2 { font-size: 1.15rem !important; font-weight: 600 !important; color: var(--text-pri) !important;
     letter-spacing: -0.2px !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; color: var(--text-pri) !important; }
h4 { font-size: 0.9rem !important; font-weight: 600 !important; color: var(--text-sec) !important;
     text-transform: uppercase; letter-spacing: 0.5px; }
p  { color: var(--text-sec) !important; line-height: 1.6; }
strong, b { color: var(--text-pri) !important; }
em { color: var(--text-sec) !important; }
code {
    background: var(--accent-dim) !important;
    color: var(--accent) !important;
    border-radius: 4px !important;
    padding: 2px 6px !important;
    font-size: 0.88em !important;
}

/* ── Metric cards ───────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 16px 18px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
[data-testid="metric-container"]:hover {
    border-color: #2a3f60 !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
}
[data-testid="metric-container"] label {
    color: var(--text-sec) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    margin-bottom: 4px !important;
}
[data-testid="stMetricValue"] {
    color: var(--text-pri) !important;
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; font-weight: 500 !important; }
[data-testid="stMetricDelta"] svg { width: 14px !important; height: 14px !important; }

/* ── Dividers ───────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 24px 0 !important;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
.stButton > button {
    border-radius: var(--radius-sm) !important;
    font-weight: 600 !important;
    font-size: 0.87rem !important;
    letter-spacing: 0.2px !important;
    padding: 9px 18px !important;
    min-height: 42px !important;
    transition: all 0.15s ease !important;
}
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: #000 !important;
    border: none !important;
    box-shadow: 0 2px 12px var(--accent-glow) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #00ebb8 !important;
    box-shadow: 0 4px 20px var(--accent-glow) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-sec) !important;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button:not([kind]):hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background: var(--accent-dim) !important;
}
[data-testid="stFormSubmitButton"] > button {
    background: var(--accent) !important;
    color: #000 !important;
    border: none !important;
    font-weight: 600 !important;
    min-height: 42px !important;
    border-radius: var(--radius-sm) !important;
}

/* ── Input fields ───────────────────────────────────────────────────── */
[data-baseweb="input"] > div,
[data-baseweb="base-input"] {
    background-color: var(--bg-card2) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius-sm) !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
    color: var(--text-pri) !important;
    background: transparent !important;
    font-size: 0.9rem !important;
}
[data-baseweb="input"]:focus-within > div,
[data-baseweb="textarea"]:focus-within > div {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent-dim) !important;
}
[data-baseweb="select"] > div {
    background-color: var(--bg-card2) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-pri) !important;
}
label { color: var(--text-sec) !important; font-size: 0.83rem !important; font-weight: 500 !important; }
[data-testid="stNumberInput"] input { color: var(--text-pri) !important; }

/* ── Slider ─────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
}

/* ── Expanders ──────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    color: var(--text-pri) !important;
    font-weight: 500 !important;
    padding: 12px 16px !important;
}
[data-testid="stExpander"] summary:hover { color: var(--accent) !important; }

/* ── Dataframes ─────────────────────────────────────────────────────── */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] > div {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    overflow: hidden !important;
    background: var(--bg-card) !important;
}

/* ── Alert / info / warning / error ────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--radius) !important;
    border-left-width: 3px !important;
    font-size: 0.88rem !important;
}

/* ── Chat messages ──────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    margin-bottom: 8px !important;
}
[data-testid="stChatInput"] textarea {
    background: var(--bg-card2) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text-pri) !important;
    font-size: 0.9rem !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px var(--accent-dim) !important;
}

/* ── Spinner ────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div {
    border-top-color: var(--accent) !important;
}

/* ── Sidebar radio nav ──────────────────────────────────────────────── */
[data-testid="stSidebar"] .stRadio > label {
    font-weight: 700 !important;
    color: var(--text-pri) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    border-radius: 6px !important;
    padding: 7px 10px !important;
    margin: 1px 0 !important;
    cursor: pointer !important;
    color: var(--text-sec) !important;
    font-size: 0.88rem !important;
    transition: color 0.12s !important;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover {
    color: var(--accent) !important;
}

/* ── Caption ─────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p {
    color: var(--text-dim) !important;
    font-size: 0.78rem !important;
}

/* ── Page & section header helpers ─────────────────────────────────── */
.pg-header {
    padding: 0 0 20px 0;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
}
.pg-title {
    font-size: 1.65rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.5px;
    margin: 0 0 4px 0;
}
.pg-sub {
    font-size: 0.85rem;
    color: var(--text-sec);
    margin: 0;
}
.sec-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 22px 0 12px 0;
}
.sec-title {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.sec-line {
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* ── Status pills ───────────────────────────────────────────────────── */
.pill {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.3px;
}
.pill-green  { background: rgba(0,212,170,0.15); color: #00d4aa; border: 1px solid rgba(0,212,170,0.3); }
.pill-red    { background: rgba(244,67,54,0.12); color: #f44336; border: 1px solid rgba(244,67,54,0.25); }
.pill-orange { background: rgba(255,152,0,0.12); color: #ff9800; border: 1px solid rgba(255,152,0,0.25); }
.pill-gray   { background: rgba(139,157,184,0.1); color: #8b9db8; border: 1px solid rgba(139,157,184,0.2); }

/* ── Trade / action card ────────────────────────────────────────────── */
.trade-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 16px;
    margin: 8px 0;
    transition: border-color 0.15s;
}
.trade-card:hover { border-color: #2a3f60; }
.trade-card-buy  { border-left: 3px solid var(--accent) !important; }
.trade-card-sell { border-left: 3px solid var(--red) !important; }

/* ── Log entry ──────────────────────────────────────────────────────── */
.log-entry {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-dim);
    font-size: 0.87rem;
}
.log-ts { color: var(--text-dim); font-size: 0.75rem; font-family: monospace; }
.log-msg { color: var(--text-sec); }

/* ── Watchlist ticker card ──────────────────────────────────────────── */
.ticker-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px;
    text-align: center;
    transition: border-color 0.15s, transform 0.15s;
}
.ticker-card:hover { border-color: #2a3f60; transform: translateY(-1px); }
.ticker-sym  { font-size: 1rem; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
.ticker-price { font-size: 1.3rem; font-weight: 700; color: var(--text-pri); margin: 4px 0; }
.ticker-delta-pos { font-size: 0.78rem; font-weight: 600; color: var(--accent); }
.ticker-delta-neg { font-size: 0.78rem; font-weight: 600; color: var(--red); }
.ticker-note { font-size: 0.72rem; color: var(--text-dim); margin-top: 4px; }

/* ── Signal badge ───────────────────────────────────────────────────── */
.signal-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: var(--bg-card);
    border: 1px solid var(--border-dim);
    border-radius: 8px;
    margin: 4px 0;
    font-size: 0.87rem;
    color: var(--text-sec);
}
.signal-dot-bull { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
.signal-dot-bear { width: 8px; height: 8px; border-radius: 50%; background: var(--red); flex-shrink: 0; }

/* ── Settings section cards ─────────────────────────────────────────── */
.settings-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
}

/* ── Mobile responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
    [data-testid="block-container"] { padding: 12px 8px 32px 8px !important; }
    h1 { font-size: 1.3rem !important; }
    .pg-title { font-size: 1.3rem; }
    [data-testid="stMetricValue"] { font-size: 1.15rem !important; }
    [data-testid="metric-container"] { padding: 12px 14px !important; margin-bottom: 8px !important; }
    .stButton > button { min-height: 48px !important; font-size: 0.93rem !important; width: 100%; }
    [data-baseweb="input"] input { font-size: 16px !important; }
    [data-baseweb="textarea"] textarea { font-size: 16px !important; }
    .ticker-card { padding: 10px; }
    .ticker-price { font-size: 1.1rem; }
    .trade-card { padding: 12px; }
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f'<p class="pg-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="pg-header"><div class="pg-title">{title}</div>{sub}</div>',
        unsafe_allow_html=True,
    )


def section_header(title: str) -> None:
    st.markdown(
        f'<div class="sec-header">'
        f'<span class="sec-title">{title}</span>'
        f'<div class="sec-line"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
