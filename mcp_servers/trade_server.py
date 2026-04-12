"""
MCP Server 3: Trade Execution Server
Interfaces with the simulator engine to execute and manage trades.
"""
from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP
from simulator.paper_trading import PaperTradingEngine
from config import INITIAL_BALANCE, COMMISSION_RATE

logger = logging.getLogger(__name__)

mcp = FastMCP("Trade Execution Server")

_engine: PaperTradingEngine | None = None


def _get_engine() -> PaperTradingEngine:
    global _engine
    if _engine is None:
        _engine = PaperTradingEngine(
            initial_balance=INITIAL_BALANCE,
            commission_rate=COMMISSION_RATE,
        )
    return _engine


def set_engine(engine: PaperTradingEngine):
    """Allow external code to inject a specific engine instance (for shared state)."""
    global _engine
    _engine = engine


@mcp.tool()
def buy_stock(
    symbol: str,
    quantity: float,
    order_type: str = "market",
    limit_price: float | None = None,
    reasoning: str = "",
    risk_score: float = 0.0,
) -> str:
    """
    Place a buy order for a stock.
    order_type: 'market' or 'limit'
    """
    engine = _get_engine()
    result = engine.buy(
        symbol=symbol,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        reasoning=reasoning,
        risk_score=risk_score,
    )
    return json.dumps(result)


@mcp.tool()
def sell_stock(
    symbol: str,
    quantity: float,
    order_type: str = "market",
    limit_price: float | None = None,
    reasoning: str = "",
    risk_score: float = 0.0,
) -> str:
    """
    Place a sell order for a stock.
    order_type: 'market' or 'limit'
    """
    engine = _get_engine()
    result = engine.sell(
        symbol=symbol,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        reasoning=reasoning,
        risk_score=risk_score,
    )
    return json.dumps(result)


@mcp.tool()
def get_portfolio() -> str:
    """Get the current portfolio including all positions and their P&L."""
    engine = _get_engine()
    return json.dumps(engine.get_portfolio())


@mcp.tool()
def get_account_balance() -> str:
    """Get account balance: cash, positions value, total value, and return."""
    engine = _get_engine()
    return json.dumps(engine.get_account_balance())


@mcp.tool()
def get_trade_history(limit: int = 50) -> str:
    """Get recent trade history with timestamps and AI reasoning."""
    engine = _get_engine()
    return json.dumps(engine.get_trade_history(limit))


@mcp.tool()
def get_open_orders() -> str:
    """Get all pending limit orders."""
    engine = _get_engine()
    return json.dumps(engine.get_open_orders())


@mcp.tool()
def cancel_order(order_id: str) -> str:
    """Cancel a pending limit order by its ID."""
    engine = _get_engine()
    return json.dumps(engine.cancel_order(order_id))


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="localhost", port=8003)
