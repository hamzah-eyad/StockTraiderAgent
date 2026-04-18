"""
MCP Server 1: Financial Data Server
Provides real-time and historical stock data via yfinance.
"""
from __future__ import annotations

import json
import logging

import pandas as pd
import yfinance as yf
import ta

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("Financial Data Server", host="0.0.0.0", port=8001)


@mcp.tool()
def get_stock_price(symbol: str) -> str:
    """Get the current price and key metrics for a stock symbol."""
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.fast_info
        hist = ticker.history(period="2d")

        last_price = info.get("lastPrice", 0)
        prev_close = info.get("previousClose", 0)
        change = last_price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        result = {
            "symbol": symbol.upper(),
            "price": round(last_price, 2),
            "previous_close": round(prev_close, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "day_high": round(info.get("dayHigh", 0), 2),
            "day_low": round(info.get("dayLow", 0), 2),
            "volume": int(info.get("lastVolume", 0)),
            "market_cap": info.get("marketCap", 0),
            "fifty_two_week_high": round(info.get("yearHigh", 0), 2),
            "fifty_two_week_low": round(info.get("yearLow", 0), 2),
        }
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e), "symbol": symbol.upper()})


@mcp.tool()
def get_stock_history(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
) -> str:
    """
    Get historical OHLCV data for a stock.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
    interval: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return json.dumps({"error": f"No data for {symbol}", "data": []})

        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": idx.isoformat(),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })

        return json.dumps({
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "count": len(records),
            "data": records[-60:],
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_technical_indicators(symbol: str, period: str = "3mo") -> str:
    """
    Calculate technical indicators for a stock: RSI, MACD, Bollinger Bands, SMA, EMA.
    """
    try:
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period, interval="1d")
        if len(df) < 20:
            return json.dumps({"error": "Not enough data for indicators"})

        close = df["Close"]

        rsi = ta.momentum.RSIIndicator(close, window=14)
        macd = ta.trend.MACD(close)
        bb = ta.volatility.BollingerBands(close, window=20)
        sma_20 = ta.trend.SMAIndicator(close, window=20)
        sma_50 = ta.trend.SMAIndicator(close, window=50)
        ema_12 = ta.trend.EMAIndicator(close, window=12)

        latest = {
            "symbol": symbol.upper(),
            "price": round(close.iloc[-1], 2),
            "rsi_14": round(rsi.rsi().iloc[-1], 2),
            "macd": round(macd.macd().iloc[-1], 4),
            "macd_signal": round(macd.macd_signal().iloc[-1], 4),
            "macd_histogram": round(macd.macd_diff().iloc[-1], 4),
            "bollinger_upper": round(bb.bollinger_hband().iloc[-1], 2),
            "bollinger_middle": round(bb.bollinger_mavg().iloc[-1], 2),
            "bollinger_lower": round(bb.bollinger_lband().iloc[-1], 2),
            "sma_20": round(sma_20.sma_indicator().iloc[-1], 2),
            "sma_50": round(sma_50.sma_indicator().iloc[-1], 2) if len(df) >= 50 else None,
            "ema_12": round(ema_12.ema_indicator().iloc[-1], 2),
        }

        if latest["rsi_14"] > 70:
            latest["rsi_signal"] = "overbought"
        elif latest["rsi_14"] < 30:
            latest["rsi_signal"] = "oversold"
        else:
            latest["rsi_signal"] = "neutral"

        if latest["macd"] > latest["macd_signal"]:
            latest["macd_signal_type"] = "bullish"
        else:
            latest["macd_signal_type"] = "bearish"

        return json.dumps(latest)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_market_overview() -> str:
    """Get an overview of major market indices: S&P 500, NASDAQ, DOW, VIX."""
    indices = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
        "VIX": "^VIX",
        "Russell 2000": "^RUT",
    }
    results = []
    for name, symbol in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            last = info.get("lastPrice", 0)
            prev = info.get("previousClose", 0)
            change = last - prev if prev else 0
            change_pct = (change / prev * 100) if prev else 0
            results.append({
                "name": name,
                "symbol": symbol,
                "price": round(last, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
            })
        except Exception as e:
            results.append({"name": name, "symbol": symbol, "error": str(e)})

    return json.dumps({"indices": results})


@mcp.tool()
def search_stocks(query: str) -> str:
    """Search for stock tickers matching a company name or keyword."""
    try:
        import yfinance as yf
        results = []
        common_stocks = {
            "AAPL": "Apple Inc.",
            "MSFT": "Microsoft Corporation",
            "GOOGL": "Alphabet Inc.",
            "AMZN": "Amazon.com Inc.",
            "NVDA": "NVIDIA Corporation",
            "META": "Meta Platforms Inc.",
            "TSLA": "Tesla Inc.",
            "JPM": "JPMorgan Chase & Co.",
            "V": "Visa Inc.",
            "JNJ": "Johnson & Johnson",
            "WMT": "Walmart Inc.",
            "PG": "Procter & Gamble Co.",
            "XOM": "Exxon Mobil Corporation",
            "BAC": "Bank of America Corp.",
            "DIS": "The Walt Disney Company",
            "NFLX": "Netflix Inc.",
            "AMD": "Advanced Micro Devices",
            "INTC": "Intel Corporation",
            "BA": "Boeing Company",
            "GS": "Goldman Sachs Group",
            "LMT": "Lockheed Martin Corp.",
            "RTX": "RTX Corporation",
            "NOC": "Northrop Grumman Corp.",
        }
        q = query.upper()
        for sym, name in common_stocks.items():
            if q in sym or q in name.upper():
                results.append({"symbol": sym, "name": name})

        return json.dumps({"query": query, "results": results[:10]})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("stock://{symbol}/price")
def stock_price_resource(symbol: str) -> str:
    """Live price resource for a stock symbol."""
    return get_stock_price(symbol)


@mcp.resource("stock://{symbol}/history")
def stock_history_resource(symbol: str) -> str:
    """Historical data resource for a stock symbol."""
    return get_stock_history(symbol, period="1mo")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
