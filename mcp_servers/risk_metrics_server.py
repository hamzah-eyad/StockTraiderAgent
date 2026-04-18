"""
Portfolio Risk Metrics MCP Server
===================================
Computes quantitative risk metrics for the live portfolio:
  - Value at Risk (VaR) at 95% and 99% confidence (historical simulation)
  - Sharpe Ratio and Sortino Ratio (annualized, 5% risk-free rate)
  - Portfolio Beta vs S&P 500
  - Annualized volatility
  - Sector concentration (% weight per GICS sector)
  - Maximum drawdown

Also exposes a per-stock risk profiler for any ticker.

All data sourced from yfinance (already in requirements.txt).
No new dependencies required.

Standalone run:
    python mcp_servers/risk_metrics_server.py

Default port: 8008
"""

import json
import logging

import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("Risk Metrics Server", host="0.0.0.0", port=8008)

TRADING_DAYS = 252
RISK_FREE_ANNUAL = 0.05


# ─────────────────────────────────────────────
# Engine access (shared with trade_server)
# ─────────────────────────────────────────────

def _get_engine():
    """Reuse the PaperTradingEngine instance managed by trade_server.
    Since everything runs in-process, the same singleton is returned."""
    from mcp_servers.trade_server import _get_engine as _trade_get_engine
    return _trade_get_engine()


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def _fetch_returns(symbol: str, period: str) -> pd.Series | None:
    """Return a daily percentage-change return Series. Returns None on failure."""
    try:
        hist = yf.Ticker(symbol).history(period=period)
        if hist.empty or len(hist) < 10:
            return None
        return hist["Close"].pct_change().dropna()
    except Exception as e:
        logger.warning("Could not fetch returns for %s: %s", symbol, e)
        return None


def _compute_sharpe(returns: pd.Series, risk_free_daily: float) -> float:
    std = float(returns.std())
    if std <= 0:
        return 0.0
    return (float(returns.mean()) - risk_free_daily) / std * (TRADING_DAYS ** 0.5)


def _compute_sortino(returns: pd.Series, risk_free_daily: float) -> float:
    neg = returns[returns < 0]
    down_std = float(neg.std()) if len(neg) > 1 else float(returns.std())
    if down_std <= 0:
        return 0.0
    return (float(returns.mean()) - risk_free_daily) / down_std * (TRADING_DAYS ** 0.5)


def _compute_beta(port_returns: pd.Series, spy_returns: pd.Series) -> float | None:
    aligned = pd.concat([port_returns, spy_returns.rename("SPY")], axis=1).dropna()
    if len(aligned) < 20:
        return None
    cov = aligned.cov().values
    return float(cov[0][1] / cov[1][1]) if cov[1][1] != 0 else None


def _compute_max_drawdown(returns: pd.Series) -> float:
    cumulative = (1 + returns).cumprod()
    rolling_peak = cumulative.cummax()
    drawdown = (cumulative - rolling_peak) / rolling_peak
    return float(drawdown.min())


# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────

@mcp.tool()
def get_portfolio_risk_metrics() -> str:
    """
    Compute portfolio-level quantitative risk metrics using 1 year of historical
    daily returns from yfinance.

    Metrics returned:
      - VaR 95% and 99% (historical simulation, in dollars)
      - Sharpe Ratio (annualized, 5% risk-free rate)
      - Sortino Ratio (penalizes downside volatility only)
      - Portfolio Beta vs S&P 500
      - Annualized volatility (% and decimal)
      - Sector concentration (% weight per GICS sector)
      - Maximum drawdown over the lookback period

    Call this before making large trades to assess current risk exposure.

    Returns:
        JSON with all portfolio risk metrics and sector breakdown.
    """
    try:
        engine = _get_engine()
        portfolio = engine.get_portfolio()
        positions = portfolio.get("positions", {})

        if not positions:
            return json.dumps({
                "status": "success",
                "message": "No open positions. Buy some stocks first to see portfolio risk metrics.",
                "positions_count": 0,
            })

        # ── Portfolio weights by current market value ─────────────────────────
        pos_values = {
            sym: pos["quantity"] * pos["current_price"]
            for sym, pos in positions.items()
        }
        total_value = sum(pos_values.values())
        weights = {sym: val / total_value for sym, val in pos_values.items()}

        # ── Fetch 1-year return series for all holdings + SPY benchmark ───────
        period = "1y"
        ret_map: dict[str, pd.Series] = {}
        for sym in list(positions.keys()) + ["SPY"]:
            series = _fetch_returns(sym, period)
            if series is not None:
                ret_map[sym] = series

        held_with_data = [s for s in positions if s in ret_map]
        if not held_with_data:
            return json.dumps({
                "status": "error",
                "message": "Could not fetch price history for any held position.",
            })

        # ── Weighted portfolio daily return series ─────────────────────────────
        returns_df = pd.DataFrame({s: ret_map[s] for s in held_with_data}).dropna(how="all")
        total_w = sum(weights[s] for s in held_with_data)
        adj_w = {s: weights[s] / total_w for s in held_with_data}
        port_returns = sum(
            returns_df[s].fillna(0) * adj_w[s] for s in held_with_data
        ).dropna()

        risk_free_daily = RISK_FREE_ANNUAL / TRADING_DAYS
        ann_vol = float(port_returns.std()) * (TRADING_DAYS ** 0.5)

        # ── Core metrics ───────────────────────────────────────────────────────
        sharpe = _compute_sharpe(port_returns, risk_free_daily)
        sortino = _compute_sortino(port_returns, risk_free_daily)
        max_dd = _compute_max_drawdown(port_returns)

        var_95 = float(port_returns.quantile(0.05)) * total_value
        var_99 = float(port_returns.quantile(0.01)) * total_value

        beta = None
        if "SPY" in ret_map:
            beta = _compute_beta(port_returns, ret_map["SPY"])

        # ── Sector weights ─────────────────────────────────────────────────────
        sector_weights: dict[str, float] = {}
        for sym in held_with_data:
            try:
                sector = yf.Ticker(sym).info.get("sector", "Unknown")
            except Exception:
                sector = "Unknown"
            sector_weights[sector] = sector_weights.get(sector, 0.0) + adj_w[sym] * 100

        return json.dumps({
            "status": "success",
            "portfolio_value": round(total_value, 2),
            "positions_count": len(positions),
            "var_95": round(var_95, 2),
            "var_99": round(var_99, 2),
            "var_95_pct": round(float(port_returns.quantile(0.05)) * 100, 3),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "portfolio_beta": round(beta, 3) if beta is not None else None,
            "annualized_volatility": round(ann_vol, 4),
            "annualized_volatility_pct": round(ann_vol * 100, 2),
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "sector_weights": {
                k: round(v, 2)
                for k, v in sorted(sector_weights.items(), key=lambda x: -x[1])
            },
            "lookback_period": period,
            "data_points": len(port_returns),
        })
    except Exception as e:
        logger.error("get_portfolio_risk_metrics error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_stock_risk_profile(symbol: str, period: str = "1y") -> str:
    """
    Get individual stock risk metrics: annualized volatility, beta vs S&P 500,
    max drawdown, Sharpe ratio, and average daily return.

    Args:
        symbol: Stock ticker symbol, e.g. 'AAPL'.
        period: Lookback period — '1y', '6mo', '3mo', '2y'. Default: '1y'.

    Returns:
        JSON with per-stock risk metrics.
    """
    try:
        symbol = symbol.strip().upper()
        if period not in {"1y", "6mo", "3mo", "2y", "5y"}:
            period = "1y"

        stock_rets = _fetch_returns(symbol, period)
        spy_rets = _fetch_returns("SPY", period)

        if stock_rets is None or len(stock_rets) < 10:
            return json.dumps({
                "status": "error",
                "message": f"Could not fetch sufficient data for {symbol}.",
            })

        risk_free_daily = RISK_FREE_ANNUAL / TRADING_DAYS
        ann_vol = float(stock_rets.std()) * (TRADING_DAYS ** 0.5)
        sharpe = _compute_sharpe(stock_rets, risk_free_daily)

        beta = None
        if spy_rets is not None:
            beta = _compute_beta(stock_rets, spy_rets)

        # Max drawdown on price level (more intuitive than return-based)
        try:
            prices = yf.Ticker(symbol).history(period=period)["Close"]
            rolling_peak = prices.cummax()
            max_dd = float(((prices - rolling_peak) / rolling_peak).min())
        except Exception:
            max_dd = _compute_max_drawdown(stock_rets)

        try:
            info = yf.Ticker(symbol).info
            company_name = info.get("longName", symbol)
            sector = info.get("sector", "Unknown")
        except Exception:
            company_name = symbol
            sector = "Unknown"

        return json.dumps({
            "status": "success",
            "symbol": symbol,
            "company_name": company_name,
            "sector": sector,
            "period": period,
            "data_points": len(stock_rets),
            "annualized_volatility": round(ann_vol, 4),
            "annualized_volatility_pct": round(ann_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "beta_vs_spy": round(beta, 3) if beta is not None else None,
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "avg_daily_return_pct": round(float(stock_rets.mean()) * 100, 4),
        })
    except Exception as e:
        logger.error("get_stock_risk_profile error: %s", e)
        return json.dumps({"status": "error", "message": str(e)})


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
