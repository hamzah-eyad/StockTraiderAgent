"""
Pattern Scanner MCP Server
===========================
Scans stocks for active technical signals: golden/death cross (SMA 50/200),
RSI overbought/oversold, MACD crossover, and Bollinger Band breakouts.
Returns a signal score and bullish/bearish/neutral bias for each stock.

Uses 6 months of daily OHLCV data from yfinance and the `ta` library.
Zero new dependencies — everything is already in requirements.txt.

Standalone run:
    python mcp_servers/pattern_scanner_server.py

Default port: 8007
"""

import json
import logging

import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("Pattern Scanner Server", host="0.0.0.0", port=8007)


# ─────────────────────────────────────────────
# Core analysis helper
# ─────────────────────────────────────────────

def _analyze_symbol(symbol: str) -> dict:
    """Fetch OHLCV and compute all technical signals for one symbol."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="6mo", interval="1d")

        if df.empty or len(df) < 30:
            return {
                "symbol": symbol.upper(),
                "error": "Insufficient historical data (need at least 30 days).",
                "signal_score": 0,
                "bias": "neutral",
                "signals": {},
            }

        close = df["Close"]

        # ── Indicators ───────────────────────────────────────────────────────
        rsi_series = RSIIndicator(close=close, window=14).rsi()
        macd_obj = MACD(close=close)
        macd_diff = macd_obj.macd_diff()
        bb = BollingerBands(close=close, window=20, window_dev=2)
        sma50 = SMAIndicator(close=close, window=50).sma_indicator()
        sma200 = SMAIndicator(close=close, window=200).sma_indicator()

        # ── Latest values ─────────────────────────────────────────────────────
        current = float(close.iloc[-1])
        rsi_val = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0
        macd_now = float(macd_diff.iloc[-1]) if not pd.isna(macd_diff.iloc[-1]) else 0.0
        macd_prev = (
            float(macd_diff.iloc[-2])
            if len(macd_diff) > 1 and not pd.isna(macd_diff.iloc[-2])
            else 0.0
        )
        bb_upper = float(bb.bollinger_hband().iloc[-1])
        bb_lower = float(bb.bollinger_lband().iloc[-1])
        sma50_val = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else current

        # ── Signal detection ──────────────────────────────────────────────────
        rsi_oversold = rsi_val < 30
        rsi_overbought = rsi_val > 70
        macd_bullish_cross = macd_now > 0 and macd_prev <= 0
        macd_bearish_cross = macd_now < 0 and macd_prev >= 0
        bb_lower_break = current < bb_lower
        bb_upper_break = current > bb_upper

        # Golden/death cross: detect SMA50 crossing SMA200 in the last 5 bars.
        # Also track whether SMA50 is generally above SMA200 (uptrend).
        golden_cross = False
        death_cross = False
        sma50_above_sma200 = False
        if len(sma200.dropna()) >= 5:
            last5_50 = sma50.iloc[-5:]
            last5_200 = sma200.iloc[-5:]
            valid_mask = (~last5_50.isna()) & (~last5_200.isna())
            s50v = last5_50[valid_mask]
            s200v = last5_200[valid_mask]
            if len(s50v) >= 2:
                above_now = bool(s50v.iloc[-1] > s200v.iloc[-1])
                above_first = bool(s50v.iloc[0] > s200v.iloc[0])
                sma50_above_sma200 = above_now
                golden_cross = above_now and not above_first
                death_cross = not above_now and above_first

        # ── Signal score: bullish signals +, bearish signals − ────────────────
        score = 0
        score += 2 if golden_cross else 0
        score -= 2 if death_cross else 0
        score += 1 if rsi_oversold else 0
        score -= 1 if rsi_overbought else 0
        score += 1 if macd_bullish_cross else 0
        score -= 1 if macd_bearish_cross else 0
        score += 1 if bb_lower_break else 0
        score -= 1 if bb_upper_break else 0
        # Bonus point for being in a sustained uptrend (SMA50 > SMA200 without a fresh cross)
        if sma50_above_sma200 and not golden_cross and not death_cross:
            score += 1

        bias = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"

        return {
            "symbol": symbol.upper(),
            "current_price": round(current, 2),
            "signals": {
                "golden_cross": golden_cross,
                "death_cross": death_cross,
                "sma50_above_sma200": sma50_above_sma200,
                "rsi_oversold": rsi_oversold,
                "rsi_overbought": rsi_overbought,
                "macd_bullish_cross": macd_bullish_cross,
                "macd_bearish_cross": macd_bearish_cross,
                "bb_upper_break": bb_upper_break,
                "bb_lower_break": bb_lower_break,
            },
            "signal_score": score,
            "bias": bias,
            "rsi": round(rsi_val, 2),
            "macd_diff": round(macd_now, 4),
            "sma_50": round(sma50_val, 2),
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "error": None,
        }
    except Exception as e:
        logger.error("Pattern scan error for %s: %s", symbol, e)
        return {
            "symbol": symbol.upper(),
            "error": str(e),
            "signal_score": 0,
            "bias": "neutral",
            "signals": {},
        }


# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────

@mcp.tool()
def scan_patterns(symbols: str) -> str:
    """
    Scan multiple stocks for active technical signals and return a bullish/bearish
    bias with a signal score for each. Higher positive scores = more bullish signals
    active simultaneously.

    Detects: golden cross, death cross, RSI overbought/oversold, MACD crossover,
    and Bollinger Band breakouts. Uses 6 months of daily data.

    Args:
        symbols: Comma-separated ticker symbols, e.g. 'AAPL,MSFT,NVDA'.

    Returns:
        JSON with a list of signal objects sorted by signal score (most bullish first).
    """
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            return json.dumps({"status": "error", "message": "No symbols provided."})

        results = []
        for sym in symbol_list:
            logger.info("Scanning patterns for %s", sym)
            results.append(_analyze_symbol(sym))

        bullish = [r for r in results if r.get("bias") == "bullish"]
        bearish = [r for r in results if r.get("bias") == "bearish"]
        neutral = [r for r in results if r.get("bias") == "neutral"]

        return json.dumps({
            "status": "success",
            "scanned": len(results),
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "neutral_count": len(neutral),
            "results": sorted(results, key=lambda r: r.get("signal_score", 0), reverse=True),
        })
    except Exception as e:
        logger.error("scan_patterns error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_signal_summary(symbol: str) -> str:
    """
    Get a detailed breakdown of all current technical signals for a single stock.

    Returns RSI value, MACD differential, Bollinger Band levels, SMA crossover
    status, and a signal score with bullish/bearish/neutral bias.

    Args:
        symbol: Stock ticker symbol, e.g. 'AAPL'.

    Returns:
        JSON with full signal analysis for the stock.
    """
    try:
        symbol = symbol.strip().upper()
        result = _analyze_symbol(symbol)

        if result.get("error"):
            return json.dumps({
                "status": "error",
                "message": result["error"],
                "symbol": symbol,
            })

        return json.dumps({"status": "success", **result})
    except Exception as e:
        logger.error("get_signal_summary error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
