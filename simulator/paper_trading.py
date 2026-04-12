from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import yfinance as yf

from simulator.models import OrderSide, OrderType
from simulator.portfolio_manager import PortfolioManager
from config import INITIAL_BALANCE, COMMISSION_RATE

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Paper trading engine using real-time stock prices from yfinance."""

    def __init__(
        self,
        initial_balance: float = INITIAL_BALANCE,
        commission_rate: float = COMMISSION_RATE,
        db_path: str | None = None,
    ):
        self.portfolio = PortfolioManager(
            initial_balance=initial_balance,
            commission_rate=commission_rate,
            db_path=db_path,
        )
        self._price_cache: dict[str, tuple[float, datetime]] = {}
        self._cache_ttl_seconds = 15

    def get_live_price(self, symbol: str) -> Optional[float]:
        symbol = symbol.upper()
        now = datetime.utcnow()

        if symbol in self._price_cache:
            cached_price, cached_at = self._price_cache[symbol]
            if (now - cached_at).total_seconds() < self._cache_ttl_seconds:
                return cached_price

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = info.get("lastPrice") or info.get("regularMarketPrice")
            if price:
                self._price_cache[symbol] = (float(price), now)
                return float(price)
        except Exception as e:
            logger.error(f"Failed to fetch price for {symbol}: {e}")

        return self._price_cache.get(symbol, (None,))[0]

    def buy(
        self,
        symbol: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        reasoning: str = "",
        risk_score: float = 0.0,
    ) -> dict:
        symbol = symbol.upper()
        otype = OrderType.LIMIT if order_type == "limit" else OrderType.MARKET
        current_price = self.get_live_price(symbol) if otype == OrderType.MARKET else None

        if otype == OrderType.MARKET and current_price is None:
            return {"status": "rejected", "reason": f"Cannot fetch price for {symbol}"}

        order = self.portfolio.submit_order(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=otype,
            limit_price=limit_price,
            current_price=current_price,
            reasoning=reasoning,
            risk_score=risk_score,
        )
        return {
            "order_id": order.id,
            "status": order.status.value,
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "price": order.filled_price or limit_price,
            "reasoning": reasoning,
        }

    def sell(
        self,
        symbol: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        reasoning: str = "",
        risk_score: float = 0.0,
    ) -> dict:
        symbol = symbol.upper()
        otype = OrderType.LIMIT if order_type == "limit" else OrderType.MARKET
        current_price = self.get_live_price(symbol) if otype == OrderType.MARKET else None

        if otype == OrderType.MARKET and current_price is None:
            return {"status": "rejected", "reason": f"Cannot fetch price for {symbol}"}

        order = self.portfolio.submit_order(
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            order_type=otype,
            limit_price=limit_price,
            current_price=current_price,
            reasoning=reasoning,
            risk_score=risk_score,
        )
        return {
            "order_id": order.id,
            "status": order.status.value,
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "price": order.filled_price or limit_price,
            "reasoning": reasoning,
        }

    def refresh_positions(self):
        """Update all position prices with latest market data."""
        prices = {}
        for symbol in self.portfolio.positions:
            price = self.get_live_price(symbol)
            if price is not None:
                prices[symbol] = price
        self.portfolio.update_prices(prices)
        self.portfolio.check_limit_orders(prices)

    def get_portfolio(self) -> dict:
        self.refresh_positions()
        return self.portfolio.get_portfolio()

    def get_account_balance(self) -> dict:
        self.refresh_positions()
        return self.portfolio.get_account_balance()

    def get_trade_history(self, limit: int = 50) -> list[dict]:
        return self.portfolio.get_trade_history(limit)

    def get_open_orders(self) -> list[dict]:
        return [
            {
                "order_id": o.id,
                "symbol": o.symbol,
                "side": o.side.value,
                "quantity": o.quantity,
                "limit_price": o.limit_price,
                "created_at": o.created_at.isoformat(),
            }
            for o in self.portfolio.open_orders.values()
        ]

    def cancel_order(self, order_id: str) -> dict:
        success = self.portfolio.cancel_order(order_id)
        return {
            "order_id": order_id,
            "cancelled": success,
        }
