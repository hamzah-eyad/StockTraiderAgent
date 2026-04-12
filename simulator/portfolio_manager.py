from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from simulator.models import (
    Order, OrderSide, OrderStatus, OrderType,
    Position, PortfolioSnapshot, TradeRecord, get_db_session,
)
from config import INITIAL_BALANCE, COMMISSION_RATE, DB_PATH

logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages portfolio state: cash, positions, orders, and trade history."""

    def __init__(
        self,
        initial_balance: float = INITIAL_BALANCE,
        commission_rate: float = COMMISSION_RATE,
        db_path: str | None = None,
    ):
        self.cash = initial_balance
        self.initial_balance = initial_balance
        self.commission_rate = commission_rate
        self.positions: dict[str, Position] = {}
        self.open_orders: dict[str, Order] = {}
        self.filled_orders: list[Order] = []
        self.portfolio_history: list[PortfolioSnapshot] = []
        self._db_path = db_path or str(DB_PATH)
        self._db = get_db_session(self._db_path)

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        current_price: Optional[float] = None,
        reasoning: str = "",
        risk_score: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> Order:
        ts = timestamp or datetime.utcnow()
        order = Order(
            symbol=symbol.upper(),
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            reasoning=reasoning,
            risk_score=risk_score,
            created_at=ts,
        )

        if order_type == OrderType.MARKET and current_price is not None:
            return self._fill_order(order, current_price, ts)

        if order_type == OrderType.LIMIT and limit_price is not None:
            self.open_orders[order.id] = order
            logger.info(f"Limit order placed: {order.id} {side.value} {quantity} {symbol} @ {limit_price}")
            return order

        order.status = OrderStatus.REJECTED
        logger.warning(f"Order rejected: missing price for {order_type.value} order")
        return order

    def _fill_order(self, order: Order, fill_price: float, timestamp: Optional[datetime] = None) -> Order:
        commission = fill_price * order.quantity * self.commission_rate
        total_cost = fill_price * order.quantity

        if order.side == OrderSide.BUY:
            required = total_cost + commission
            if required > self.cash:
                order.status = OrderStatus.REJECTED
                logger.warning(
                    f"Order rejected: insufficient funds. Need ${required:.2f}, have ${self.cash:.2f}"
                )
                return order
            self.cash -= required
            self._add_to_position(order.symbol, order.quantity, fill_price)

        elif order.side == OrderSide.SELL:
            pos = self.positions.get(order.symbol)
            if pos is None or pos.quantity < order.quantity:
                order.status = OrderStatus.REJECTED
                held = pos.quantity if pos else 0
                logger.warning(
                    f"Order rejected: insufficient shares. Want {order.quantity}, hold {held}"
                )
                return order
            self.cash += total_cost - commission
            self._remove_from_position(order.symbol, order.quantity)

        order.status = OrderStatus.FILLED
        order.filled_at = timestamp or datetime.utcnow()
        order.filled_price = fill_price
        self.filled_orders.append(order)

        self._record_trade(order, fill_price, commission, total_cost, order.filled_at)
        logger.info(
            f"Order filled: {order.side.value} {order.quantity} {order.symbol} @ ${fill_price:.2f}"
        )
        return order

    def _add_to_position(self, symbol: str, quantity: float, price: float):
        if symbol in self.positions:
            pos = self.positions[symbol]
            total_qty = pos.quantity + quantity
            pos.avg_cost = (
                (pos.avg_cost * pos.quantity) + (price * quantity)
            ) / total_qty
            pos.quantity = total_qty
        else:
            self.positions[symbol] = Position(
                symbol=symbol, quantity=quantity, avg_cost=price, current_price=price,
            )

    def _remove_from_position(self, symbol: str, quantity: float):
        pos = self.positions[symbol]
        pos.quantity -= quantity
        if pos.quantity <= 0:
            del self.positions[symbol]

    def _record_trade(
        self, order: Order, price: float, commission: float, total_cost: float,
        timestamp: Optional[datetime] = None,
    ):
        record = TradeRecord(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            commission=commission,
            total_cost=total_cost,
            reasoning=order.reasoning,
            risk_score=order.risk_score,
            timestamp=timestamp or datetime.utcnow(),
        )
        self._db.add(record)
        self._db.commit()

    def check_limit_orders(self, prices: dict[str, float]):
        """Check and fill any limit orders whose price conditions are met."""
        to_remove = []
        for order_id, order in self.open_orders.items():
            price = prices.get(order.symbol)
            if price is None:
                continue
            should_fill = (
                (order.side == OrderSide.BUY and price <= order.limit_price)
                or (order.side == OrderSide.SELL and price >= order.limit_price)
            )
            if should_fill:
                self._fill_order(order, price)
                to_remove.append(order_id)

        for oid in to_remove:
            del self.open_orders[oid]

    def update_prices(self, prices: dict[str, float]):
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

    def take_snapshot(self, timestamp: Optional[datetime] = None) -> PortfolioSnapshot:
        snapshot = PortfolioSnapshot(
            cash=self.cash,
            positions=dict(self.positions),
            timestamp=timestamp or datetime.utcnow(),
        )
        self.portfolio_history.append(snapshot)
        return snapshot

    def get_portfolio(self) -> dict:
        snapshot = PortfolioSnapshot(cash=self.cash, positions=dict(self.positions))
        return snapshot.to_dict()

    def get_account_balance(self) -> dict:
        total_positions = sum(p.market_value for p in self.positions.values())
        total_value = self.cash + total_positions
        return {
            "cash": round(self.cash, 2),
            "positions_value": round(total_positions, 2),
            "total_value": round(total_value, 2),
            "initial_balance": self.initial_balance,
            "total_return": round(total_value - self.initial_balance, 2),
            "total_return_pct": round(
                ((total_value - self.initial_balance) / self.initial_balance) * 100, 2
            ),
        }

    def get_trade_history(self, limit: int = 50) -> list[dict]:
        records = (
            self._db.query(TradeRecord)
            .order_by(TradeRecord.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "side": r.side.value if isinstance(r.side, OrderSide) else r.side,
                "quantity": r.quantity,
                "price": round(r.price, 2),
                "commission": round(r.commission, 2),
                "total_cost": round(r.total_cost, 2),
                "timestamp": r.timestamp.isoformat(),
                "reasoning": r.reasoning,
                "risk_score": r.risk_score,
            }
            for r in records
        ]

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.open_orders:
            self.open_orders[order_id].status = OrderStatus.CANCELLED
            del self.open_orders[order_id]
            return True
        return False

    def reset(self):
        self.cash = self.initial_balance
        self.positions.clear()
        self.open_orders.clear()
        self.filled_orders.clear()
        self.portfolio_history.clear()
