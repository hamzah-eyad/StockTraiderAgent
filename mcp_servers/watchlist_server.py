"""
Watchlist MCP Server
======================
Allows the Trading Agent to manage a personal stock watchlist for the user.
Supports adding/removing tickers with notes and fetching a live snapshot
of all watched stocks.

Persisted in the same SQLite database (data/trades.db) under the
`watchlist` table.

Standalone run:
    python mcp_servers/watchlist_server.py

Default port: 8005
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
)
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("Watchlist Server", host="0.0.0.0", port=8005)

# ─────────────────────────────────────────────
# Database Setup
# ─────────────────────────────────────────────

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(BASE_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "trades.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    ticker     = Column(String,  nullable=False, unique=True)
    notes      = Column(String,  default="")
    added_at   = Column(DateTime, default=datetime.utcnow)
    added_price = Column(Float,  nullable=True)   # Price when the user added it


Base.metadata.create_all(engine)


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _fetch_live_data(ticker: str) -> dict:
    """
    Fetch current price, daily change %, and company name for a ticker.
    Returns a dict; sets error fields on failure.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        hist = t.history(period="2d")

        if hist.empty or len(hist) < 1:
            raise ValueError("No price data available.")

        current_price = round(float(hist["Close"].iloc[-1]), 4)

        if len(hist) >= 2:
            prev_close = float(hist["Close"].iloc[-2])
            daily_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)
        else:
            daily_change_pct = 0.0

        company_name = getattr(info, "quote_type", ticker)
        try:
            company_name = t.info.get("longName", ticker)
        except Exception:
            pass

        return {
            "ticker": ticker.upper(),
            "company_name": company_name,
            "current_price": current_price,
            "daily_change_pct": daily_change_pct,
            "trend": "▲" if daily_change_pct >= 0 else "▼",
            "fetch_error": None,
        }
    except Exception as e:
        return {
            "ticker": ticker.upper(),
            "company_name": None,
            "current_price": None,
            "daily_change_pct": None,
            "trend": None,
            "fetch_error": str(e),
        }


# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────

@mcp.tool()
def add_to_watchlist(ticker: str, notes: str = "") -> str:
    """
    Add a stock ticker to the user's watchlist.

    Records the current price at the time of adding so the user can later
    see how the stock has moved since they started watching it.

    Args:
        ticker: Stock symbol to watch (e.g., 'NVDA').
        notes:  Optional reason or note, e.g. 'Watching for earnings breakout'.

    Returns:
        JSON string confirming the addition with current price context.
    """
    try:
        ticker = ticker.upper().strip()
        live = _fetch_live_data(ticker)

        if live["fetch_error"]:
            return json.dumps({
                "status": "error",
                "message": f"Could not validate ticker '{ticker}': {live['fetch_error']}",
            })

        with SessionLocal() as session:
            existing = (
                session.query(WatchlistItem)
                .filter(WatchlistItem.ticker == ticker)
                .first()
            )
            if existing:
                return json.dumps({
                    "status": "already_exists",
                    "message": f"{ticker} is already on your watchlist.",
                    "ticker": ticker,
                    "notes": existing.notes,
                    "added_at": existing.added_at.isoformat(),
                })

            item = WatchlistItem(
                ticker=ticker,
                notes=notes,
                added_price=live["current_price"],
            )
            session.add(item)
            session.commit()

        return json.dumps({
            "status": "success",
            "message": f"{ticker} has been added to your watchlist.",
            "ticker": ticker,
            "company_name": live["company_name"],
            "price_when_added": live["current_price"],
            "notes": notes,
            "added_at": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.error("add_to_watchlist error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def remove_from_watchlist(ticker: str) -> str:
    """
    Remove a stock ticker from the user's watchlist.

    Args:
        ticker: Stock symbol to remove (e.g., 'NVDA').

    Returns:
        JSON string confirming removal or noting the ticker wasn't found.
    """
    try:
        ticker = ticker.upper().strip()

        with SessionLocal() as session:
            item = (
                session.query(WatchlistItem)
                .filter(WatchlistItem.ticker == ticker)
                .first()
            )
            if not item:
                return json.dumps({
                    "status": "not_found",
                    "message": f"{ticker} was not found on your watchlist.",
                })

            notes = item.notes
            added_at = item.added_at.isoformat() if item.added_at else None
            session.delete(item)
            session.commit()

        return json.dumps({
            "status": "success",
            "message": f"{ticker} has been removed from your watchlist.",
            "ticker": ticker,
            "notes": notes,
            "was_added_at": added_at,
        })
    except Exception as e:
        logger.error("remove_from_watchlist error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_watchlist_snapshot() -> str:
    """
    Fetch a live snapshot of all stocks on the user's watchlist.

    For each ticker, returns the current price, daily % change, the price
    when it was added, and the total % change since being added to the list.

    Returns:
        JSON string with a full live summary of every watched stock.
    """
    try:
        with SessionLocal() as session:
            items = session.query(WatchlistItem).order_by(WatchlistItem.added_at).all()
            snapshot_items = [
                {
                    "ticker": i.ticker,
                    "notes": i.notes,
                    "added_price": i.added_price,
                    "added_at": i.added_at.isoformat() if i.added_at else None,
                }
                for i in items
            ]

        if not snapshot_items:
            return json.dumps({
                "status": "success",
                "message": "Your watchlist is empty. Add stocks with add_to_watchlist.",
                "count": 0,
                "watchlist": [],
            })

        results = []
        for item in snapshot_items:
            live = _fetch_live_data(item["ticker"])
            change_since_added = None
            if live["current_price"] and item["added_price"]:
                change_since_added = round(
                    ((live["current_price"] - item["added_price"]) / item["added_price"]) * 100, 2
                )

            results.append({
                "ticker": item["ticker"],
                "company_name": live["company_name"],
                "current_price": live["current_price"],
                "daily_change_pct": live["daily_change_pct"],
                "trend": live["trend"],
                "price_when_added": item["added_price"],
                "change_since_added_pct": change_since_added,
                "notes": item["notes"],
                "added_at": item["added_at"],
                "error": live["fetch_error"],
            })

        return json.dumps({
            "status": "success",
            "count": len(results),
            "snapshot_time": datetime.utcnow().isoformat(),
            "watchlist": results,
        })
    except Exception as e:
        logger.error("get_watchlist_snapshot error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def clear_watchlist() -> str:
    """
    Remove all stocks from the user's watchlist.

    This action is irreversible. The agent should confirm with the user
    before calling this tool.

    Returns:
        JSON string confirming how many items were removed.
    """
    try:
        with SessionLocal() as session:
            count = session.query(WatchlistItem).count()
            session.query(WatchlistItem).delete()
            session.commit()

        return json.dumps({
            "status": "success",
            "message": f"Watchlist cleared. {count} ticker(s) removed.",
            "items_removed": count,
        })
    except Exception as e:
        logger.error("clear_watchlist error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
