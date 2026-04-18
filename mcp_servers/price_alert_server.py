"""
Price Alert MCP Server
========================
Allows the Trading Agent to set, manage, and evaluate price alerts
for stocks on behalf of the user.

Alerts are persisted in the same SQLite database used by the rest of
the project (data/trades.db) under the `price_alerts` table.

Standalone run:
    python mcp_servers/price_alert_server.py

Default port: 8004
"""

import json
import logging
import os
from datetime import datetime

import yfinance as yf
from mcp.server.fastmcp import FastMCP
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("Price Alert Server", host="0.0.0.0", port=8004)

# ─────────────────────────────────────────────
# Database Setup
# ─────────────────────────────────────────────

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "trades.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    ticker     = Column(String,  nullable=False)
    condition  = Column(String,  nullable=False)   # "above" | "below"
    target     = Column(Float,   nullable=False)
    note       = Column(String,  default="")
    status     = Column(String,  default="active")  # "active" | "triggered" | "deleted"
    created_at = Column(DateTime, default=datetime.utcnow)
    triggered_at = Column(DateTime, nullable=True)


Base.metadata.create_all(engine)


def _get_current_price(ticker: str) -> float:
    """Fetch the latest market price for a ticker via yfinance."""
    data = yf.Ticker(ticker)
    info = data.fast_info
    price = getattr(info, "last_price", None)
    if price is None:
        hist = data.history(period="1d")
        if hist.empty:
            raise ValueError(f"Cannot fetch price for '{ticker}'.")
        price = float(hist["Close"].iloc[-1])
    return round(float(price), 4)


# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────

@mcp.tool()
def set_price_alert(ticker: str, target_price: float, condition: str, note: str = "") -> str:
    """
    Set a price alert for a stock on behalf of the user.

    The agent will be able to notify the user when the stock crosses
    the target threshold by calling check_alerts().

    Args:
        ticker:       Stock symbol (e.g., 'AAPL').
        target_price: The price level to watch.
        condition:    Either 'above' (alert when price rises above target)
                      or 'below' (alert when price drops below target).
        note:         Optional user-facing note, e.g. 'Take profit level'.

    Returns:
        JSON string confirming the created alert with its ID.
    """
    condition = condition.lower().strip()
    if condition not in ("above", "below"):
        return json.dumps({
            "status": "error",
            "message": "condition must be 'above' or 'below'.",
        })

    try:
        # Validate ticker and get current price for context
        current_price = _get_current_price(ticker)

        with SessionLocal() as session:
            alert = PriceAlert(
                ticker=ticker.upper(),
                condition=condition,
                target=target_price,
                note=note,
                status="active",
            )
            session.add(alert)
            session.commit()
            session.refresh(alert)
            alert_id = alert.id

        return json.dumps({
            "status": "success",
            "message": f"Alert set! You will be notified when {ticker.upper()} goes {condition} ${target_price}.",
            "alert_id": alert_id,
            "ticker": ticker.upper(),
            "condition": condition,
            "target_price": target_price,
            "current_price": current_price,
            "note": note,
            "created_at": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.error("set_price_alert error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def list_alerts(status_filter: str = "active") -> str:
    """
    List all price alerts for the user, optionally filtered by status.

    Args:
        status_filter: One of 'active', 'triggered', 'deleted', or 'all'.
                       Defaults to 'active' to show only pending alerts.

    Returns:
        JSON string with a list of alerts and their details.
    """
    try:
        with SessionLocal() as session:
            query = session.query(PriceAlert)
            if status_filter != "all":
                query = query.filter(PriceAlert.status == status_filter)
            alerts = query.order_by(PriceAlert.created_at.desc()).all()

        result = [
            {
                "alert_id": a.id,
                "ticker": a.ticker,
                "condition": a.condition,
                "target_price": a.target,
                "note": a.note,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
            }
            for a in alerts
        ]

        return json.dumps({
            "status": "success",
            "filter": status_filter,
            "count": len(result),
            "alerts": result,
        })
    except Exception as e:
        logger.error("list_alerts error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def delete_alert(alert_id: int) -> str:
    """
    Cancel and delete an active price alert by its ID.

    Args:
        alert_id: The numeric ID of the alert to delete (from list_alerts).

    Returns:
        JSON string confirming deletion or an error if not found.
    """
    try:
        with SessionLocal() as session:
            alert = session.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
            if not alert:
                return json.dumps({
                    "status": "error",
                    "message": f"No alert found with ID {alert_id}.",
                })

            ticker = alert.ticker
            target = alert.target
            condition = alert.condition
            alert.status = "deleted"
            session.commit()

        return json.dumps({
            "status": "success",
            "message": f"Alert #{alert_id} ({ticker} {condition} ${target}) has been deleted.",
            "alert_id": alert_id,
        })
    except Exception as e:
        logger.error("delete_alert error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def check_alerts() -> str:
    """
    Evaluate all active price alerts against current live market prices.

    The agent should call this periodically or before making trading decisions.
    Any alert whose condition is met will be marked as 'triggered' and returned
    so the agent can notify the user.

    Returns:
        JSON string listing any newly triggered alerts, or a confirmation
        that no alerts were triggered.
    """
    try:
        with SessionLocal() as session:
            active_alerts = (
                session.query(PriceAlert)
                .filter(PriceAlert.status == "active")
                .all()
            )

            if not active_alerts:
                return json.dumps({
                    "status": "success",
                    "message": "No active alerts to check.",
                    "triggered": [],
                })

            triggered = []
            for alert in active_alerts:
                try:
                    current_price = _get_current_price(alert.ticker)
                    condition_met = (
                        (alert.condition == "above" and current_price >= alert.target) or
                        (alert.condition == "below" and current_price <= alert.target)
                    )

                    if condition_met:
                        alert.status = "triggered"
                        alert.triggered_at = datetime.utcnow()
                        triggered.append({
                            "alert_id": alert.id,
                            "ticker": alert.ticker,
                            "condition": alert.condition,
                            "target_price": alert.target,
                            "current_price": current_price,
                            "note": alert.note,
                            "triggered_at": alert.triggered_at.isoformat(),
                            "message": (
                                f"🔔 ALERT: {alert.ticker} is now at ${current_price}, "
                                f"which is {alert.condition} your target of ${alert.target}."
                            ),
                        })
                except Exception as ticker_err:
                    logger.warning("Could not check alert %s: %s", alert.id, ticker_err)

            session.commit()

        return json.dumps({
            "status": "success",
            "alerts_checked": len(active_alerts),
            "triggered_count": len(triggered),
            "triggered": triggered,
            "message": (
                f"{len(triggered)} alert(s) triggered."
                if triggered
                else "All clear — no alerts triggered."
            ),
        })
    except Exception as e:
        logger.error("check_alerts error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")