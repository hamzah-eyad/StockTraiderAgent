"""Reusable Plotly chart builders for the dashboard."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def create_candlestick_chart(data: list[dict], symbol: str) -> go.Figure:
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"], utc=True)

    fig = go.Figure(data=[
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol,
        )
    ])
    fig.update_layout(
        title=f"{symbol} Price Chart",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        template="plotly_dark",
        height=500,
        xaxis_rangeslider_visible=False,
    )
    return fig


def create_portfolio_value_chart(history: list[dict]) -> go.Figure:
    if not history:
        fig = go.Figure()
        fig.update_layout(title="No portfolio history yet", template="plotly_dark")
        return fig

    df = pd.DataFrame(history)
    df["date"] = pd.to_datetime(df["date"], utc=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["value"],
        mode="lines+markers",
        name="Portfolio Value",
        line=dict(color="#00d4aa", width=2),
        fill="tozeroy",
        fillcolor="rgba(0, 212, 170, 0.1)",
    ))
    fig.update_layout(
        title="Portfolio Value Over Time",
        xaxis_title="Date",
        yaxis_title="Value ($)",
        template="plotly_dark",
        height=400,
    )
    return fig


def create_risk_gauge(score: float) -> go.Figure:
    if score < 30:
        color = "#00d4aa"
    elif score < 70:
        color = "#ffa500"
    else:
        color = "#ff4444"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Geopolitical Risk Score", "font": {"size": 20}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 30], "color": "rgba(0, 212, 170, 0.2)"},
                {"range": [30, 70], "color": "rgba(255, 165, 0, 0.2)"},
                {"range": [70, 100], "color": "rgba(255, 68, 68, 0.2)"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 2},
                "thickness": 0.75,
                "value": score,
            },
        },
    ))
    fig.update_layout(
        template="plotly_dark",
        height=300,
    )
    return fig


def create_sector_impact_chart(impacts: dict) -> go.Figure:
    sectors = list(impacts.keys())
    scores = [impacts[s].get("impact_score", 0) for s in sectors]
    colors = ["#ff4444" if s > 60 else "#ffa500" if s > 30 else "#00d4aa" for s in scores]

    fig = go.Figure(go.Bar(
        x=sectors,
        y=scores,
        marker_color=colors,
        text=[f"{s:.0f}" for s in scores],
        textposition="auto",
    ))
    fig.update_layout(
        title="Geopolitical Impact by Sector",
        xaxis_title="Sector",
        yaxis_title="Impact Score",
        template="plotly_dark",
        height=350,
    )
    return fig


def create_conflict_heatmap(conflicts: list[dict]) -> go.Figure:
    names = [c["conflict"] for c in conflicts]
    scores = [c["risk_score"] for c in conflicts]
    activities = [c["activity_level"] for c in conflicts]

    colors = []
    for s in scores:
        if s < 25:
            colors.append("#00d4aa")
        elif s < 50:
            colors.append("#ffa500")
        elif s < 75:
            colors.append("#ff6600")
        else:
            colors.append("#ff4444")

    fig = go.Figure(go.Bar(
        x=names,
        y=scores,
        marker_color=colors,
        text=[f"{a}<br>{s:.0f}" for a, s in zip(activities, scores)],
        textposition="auto",
    ))
    fig.update_layout(
        title="Active Conflicts Risk Monitor",
        xaxis_title="Conflict",
        yaxis_title="Risk Score",
        template="plotly_dark",
        height=350,
    )
    return fig


def create_backtest_chart(
    portfolio_values: list[dict],
    benchmark_values: list[dict] | None = None,
) -> go.Figure:
    fig = go.Figure()

    if portfolio_values:
        df = pd.DataFrame(portfolio_values)
        df["date"] = pd.to_datetime(df["date"], utc=True)
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["value"],
            mode="lines",
            name="Strategy",
            line=dict(color="#00d4aa", width=2),
        ))

    if benchmark_values:
        bdf = pd.DataFrame(benchmark_values)
        bdf["date"] = pd.to_datetime(bdf["date"], utc=True)
        fig.add_trace(go.Scatter(
            x=bdf["date"],
            y=bdf["value"],
            mode="lines",
            name="Benchmark (SPY)",
            line=dict(color="#888888", width=1, dash="dash"),
        ))

    fig.update_layout(
        title="Backtest Performance",
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        template="plotly_dark",
        height=450,
    )
    return fig


def create_trades_timeline(trades: list[dict]) -> go.Figure:
    if not trades:
        fig = go.Figure()
        fig.update_layout(title="No trades yet", template="plotly_dark")
        return fig

    df = pd.DataFrame(trades)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    buys = df[df["side"] == "buy"]
    sells = df[df["side"] == "sell"]

    fig = go.Figure()
    if not buys.empty:
        fig.add_trace(go.Scatter(
            x=buys["timestamp"],
            y=buys["price"],
            mode="markers",
            name="Buy",
            marker=dict(color="#00d4aa", size=10, symbol="triangle-up"),
            text=buys["symbol"],
        ))
    if not sells.empty:
        fig.add_trace(go.Scatter(
            x=sells["timestamp"],
            y=sells["price"],
            mode="markers",
            name="Sell",
            marker=dict(color="#ff4444", size=10, symbol="triangle-down"),
            text=sells["symbol"],
        ))

    fig.update_layout(
        title="Trade Timeline",
        xaxis_title="Time",
        yaxis_title="Price ($)",
        template="plotly_dark",
        height=350,
    )
    return fig


def create_allocation_pie(positions: dict, cash: float) -> go.Figure:
    """
    Donut chart showing portfolio allocation.
    positions: dict of symbol -> position dict (with market_value key).
    cash: remaining cash balance.
    """
    labels = []
    values = []

    for sym, pos in positions.items():
        mv = pos.get("market_value", 0)
        if mv > 0:
            labels.append(sym)
            values.append(mv)

    if cash > 0:
        labels.append("Cash")
        values.append(cash)

    if not values:
        fig = go.Figure()
        fig.update_layout(
            title="No holdings to display",
            template="plotly_dark",
            height=350,
        )
        return fig

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        title="Portfolio Allocation",
        template="plotly_dark",
        height=380,
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5),
    )
    return fig
