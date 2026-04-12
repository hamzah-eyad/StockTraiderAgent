"""
Pre-built trading strategies for backtesting.
These are rule-based strategies that the AI agent can also learn from.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from simulator.portfolio_manager import PortfolioManager


def momentum_strategy(
    prices: dict[str, float],
    portfolio: PortfolioManager,
    current_date: datetime,
    lookback_prices: dict[str, list[float]] | None = None,
    risk_score: float = 50.0,
) -> list[dict]:
    """
    Simple momentum strategy:
    - Buy when price is above 5-day average
    - Sell when price is below 5-day average
    - Adjust position sizes based on risk score
    """
    trades = []
    if lookback_prices is None:
        return trades

    risk_factor = _risk_position_factor(risk_score)
    balance = portfolio.get_account_balance()
    available_cash = balance["cash"]

    for symbol, price in prices.items():
        if symbol.startswith("^"):
            continue

        history = lookback_prices.get(symbol, [])
        if len(history) < 5:
            continue

        avg_5 = sum(history[-5:]) / 5
        position = portfolio.positions.get(symbol)

        if price > avg_5 * 1.02 and position is None:
            max_invest = available_cash * 0.15 * risk_factor
            qty = int(max_invest / price)
            if qty > 0:
                trades.append({
                    "symbol": symbol,
                    "side": "buy",
                    "quantity": qty,
                    "reasoning": f"Momentum buy: price ${price:.2f} above 5-day avg ${avg_5:.2f}. Risk factor: {risk_factor:.1f}",
                })
                available_cash -= qty * price

        elif price < avg_5 * 0.98 and position is not None:
            trades.append({
                "symbol": symbol,
                "side": "sell",
                "quantity": position.quantity,
                "reasoning": f"Momentum sell: price ${price:.2f} below 5-day avg ${avg_5:.2f}",
            })

    return trades


def mean_reversion_strategy(
    prices: dict[str, float],
    portfolio: PortfolioManager,
    current_date: datetime,
    lookback_prices: dict[str, list[float]] | None = None,
    risk_score: float = 50.0,
) -> list[dict]:
    """
    Mean reversion strategy:
    - Buy when price drops significantly below 20-day average
    - Sell when price rises significantly above 20-day average
    """
    trades = []
    if lookback_prices is None:
        return trades

    risk_factor = _risk_position_factor(risk_score)
    balance = portfolio.get_account_balance()
    available_cash = balance["cash"]

    for symbol, price in prices.items():
        if symbol.startswith("^"):
            continue

        history = lookback_prices.get(symbol, [])
        if len(history) < 20:
            continue

        avg_20 = sum(history[-20:]) / 20
        deviation = (price - avg_20) / avg_20
        position = portfolio.positions.get(symbol)

        if deviation < -0.05 and position is None:
            max_invest = available_cash * 0.12 * risk_factor
            qty = int(max_invest / price)
            if qty > 0:
                trades.append({
                    "symbol": symbol,
                    "side": "buy",
                    "quantity": qty,
                    "reasoning": f"Mean reversion buy: price {deviation*100:.1f}% below 20-day avg. Expecting rebound.",
                })
                available_cash -= qty * price

        elif deviation > 0.05 and position is not None:
            trades.append({
                "symbol": symbol,
                "side": "sell",
                "quantity": position.quantity,
                "reasoning": f"Mean reversion sell: price {deviation*100:.1f}% above 20-day avg. Taking profit.",
            })

    return trades


def defensive_strategy(
    prices: dict[str, float],
    portfolio: PortfolioManager,
    current_date: datetime,
    risk_score: float = 50.0,
) -> list[dict]:
    """
    Defensive strategy for high-risk environments:
    - Sell growth/volatile positions
    - Rotate into defensive sectors
    """
    trades = []

    if risk_score < 60:
        return trades

    growth_stocks = {"TSLA", "NVDA", "AMD", "NFLX", "META"}
    defensive_stocks = {"JNJ", "PG", "WMT", "LMT", "XOM"}

    for symbol, position in list(portfolio.positions.items()):
        if symbol in growth_stocks:
            trades.append({
                "symbol": symbol,
                "side": "sell",
                "quantity": position.quantity,
                "reasoning": f"Defensive rotation: selling growth stock {symbol} due to high risk score ({risk_score:.0f})",
            })

    balance = portfolio.get_account_balance()
    available = balance["cash"]
    for symbol in defensive_stocks:
        price = prices.get(symbol)
        if price and symbol not in portfolio.positions:
            qty = int((available * 0.1) / price)
            if qty > 0:
                trades.append({
                    "symbol": symbol,
                    "side": "buy",
                    "quantity": qty,
                    "reasoning": f"Defensive buy: adding safe-haven {symbol} during high risk ({risk_score:.0f})",
                })
                available -= qty * price

    return trades


def _risk_position_factor(risk_score: float) -> float:
    """Scale position sizes inversely with risk."""
    if risk_score < 30:
        return 1.0
    elif risk_score < 50:
        return 0.8
    elif risk_score < 70:
        return 0.6
    else:
        return 0.3
