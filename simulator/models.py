from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, String, Float, DateTime, Enum as SAEnum, create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String, nullable=False)
    side = Column(SAEnum(OrderSide), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    total_cost = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    reasoning = Column(String, default="")
    risk_score = Column(Float, default=0.0)


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    reasoning: str = ""
    risk_score: float = 0.0


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_cost": round(self.avg_cost, 2),
            "current_price": round(self.current_price, 2),
            "market_value": round(self.market_value, 2),
            "cost_basis": round(self.cost_basis, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
        }


@dataclass
class PortfolioSnapshot:
    cash: float
    positions: dict[str, Position]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_positions_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def total_value(self) -> float:
        return self.cash + self.total_positions_value

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    def to_dict(self) -> dict:
        return {
            "cash": round(self.cash, 2),
            "total_positions_value": round(self.total_positions_value, 2),
            "total_value": round(self.total_value, 2),
            "total_unrealized_pnl": round(self.total_unrealized_pnl, 2),
            "positions": {
                sym: pos.to_dict() for sym, pos in self.positions.items()
            },
            "timestamp": self.timestamp.isoformat(),
        }


def get_db_session(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
