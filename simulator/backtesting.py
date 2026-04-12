from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import pandas as pd
import yfinance as yf

from simulator.models import OrderSide, OrderType
from simulator.portfolio_manager import PortfolioManager
from config import INITIAL_BALANCE, COMMISSION_RATE

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    total_return: float = 0.0
    total_return_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    portfolio_values: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    daily_returns: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_return": round(self.total_return, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "benchmark_return_pct": round(self.benchmark_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "win_rate": round(self.win_rate, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
        }


class BacktestEngine:
    """Backtesting engine that replays historical data day-by-day."""

    def __init__(
        self,
        initial_balance: float = INITIAL_BALANCE,
        commission_rate: float = COMMISSION_RATE,
        benchmark_symbol: str = "SPY",
    ):
        self.initial_balance = initial_balance
        self.commission_rate = commission_rate
        self.benchmark_symbol = benchmark_symbol

    def fetch_historical_data(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> dict[str, pd.DataFrame]:
        data = {}
        all_symbols = list(set(symbols + [self.benchmark_symbol]))
        for symbol in all_symbols:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=start_date, end=end_date)
                if not df.empty:
                    data[symbol] = df
            except Exception as e:
                logger.error(f"Failed to fetch history for {symbol}: {e}")
        return data

    def run(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        strategy_fn: Callable[
            [dict[str, pd.Series], PortfolioManager, datetime], list[dict]
        ],
    ) -> BacktestResult:
        """
        Run a backtest.

        strategy_fn receives (daily_prices_row, portfolio_manager, current_date)
        and returns a list of trade dicts: [{"symbol", "side", "quantity", "reasoning"}]
        """
        historical = self.fetch_historical_data(symbols, start_date, end_date)
        if not historical:
            logger.error("No historical data available")
            return BacktestResult()

        ref_symbol = symbols[0] if symbols[0] in historical else list(historical.keys())[0]
        trading_days = historical[ref_symbol].index

        portfolio = PortfolioManager(
            initial_balance=self.initial_balance,
            commission_rate=self.commission_rate,
        )

        result = BacktestResult()
        prev_value = self.initial_balance
        peak_value = self.initial_balance

        for day in trading_days:
            day_prices = {}
            for sym, df in historical.items():
                if day in df.index:
                    day_prices[sym] = df.loc[day, "Close"]

            portfolio.update_prices(day_prices)

            sim_date = day.to_pydatetime()
            trades = strategy_fn(day_prices, portfolio, sim_date)
            for trade in trades:
                sym = trade["symbol"].upper()
                price = day_prices.get(sym)
                if price is None:
                    continue
                side = OrderSide.BUY if trade["side"] == "buy" else OrderSide.SELL
                portfolio.submit_order(
                    symbol=sym,
                    side=side,
                    quantity=trade["quantity"],
                    order_type=OrderType.MARKET,
                    current_price=price,
                    reasoning=trade.get("reasoning", ""),
                    timestamp=sim_date,
                )

            snapshot = portfolio.take_snapshot(timestamp=sim_date)
            current_value = snapshot.total_value

            daily_ret = (current_value - prev_value) / prev_value if prev_value > 0 else 0
            result.daily_returns.append(daily_ret)
            result.portfolio_values.append({
                "date": day.isoformat(),
                "value": round(current_value, 2),
            })

            if current_value > peak_value:
                peak_value = current_value
            drawdown = peak_value - current_value
            if drawdown > result.max_drawdown:
                result.max_drawdown = drawdown
                result.max_drawdown_pct = (drawdown / peak_value) * 100

            prev_value = current_value

        self._compute_final_metrics(result, portfolio, historical)
        return result

    def _compute_final_metrics(
        self,
        result: BacktestResult,
        portfolio: PortfolioManager,
        historical: dict[str, pd.DataFrame],
    ):
        final_value = portfolio.cash + sum(
            p.market_value for p in portfolio.positions.values()
        )
        result.total_return = final_value - self.initial_balance
        result.total_return_pct = (result.total_return / self.initial_balance) * 100

        if self.benchmark_symbol in historical:
            bench = historical[self.benchmark_symbol]
            if len(bench) >= 2:
                bench_start = bench.iloc[0]["Close"]
                bench_end = bench.iloc[-1]["Close"]
                result.benchmark_return_pct = (
                    (bench_end - bench_start) / bench_start
                ) * 100

        if result.daily_returns:
            returns = pd.Series(result.daily_returns)
            mean_ret = returns.mean()
            std_ret = returns.std()
            if std_ret > 0:
                result.sharpe_ratio = (mean_ret / std_ret) * (252 ** 0.5)

        result.trades = portfolio.get_trade_history(limit=9999)
        result.total_trades = len(result.trades)

        buy_sells: dict[str, list] = {}
        for t in result.trades:
            sym = t["symbol"]
            buy_sells.setdefault(sym, []).append(t)

        winning = 0
        losing = 0
        for sym, sym_trades in buy_sells.items():
            buys = [t for t in sym_trades if t["side"] == "buy"]
            sells = [t for t in sym_trades if t["side"] == "sell"]
            for sell in sells:
                matching_buys = [b for b in buys if b["price"] < sell["price"]]
                if matching_buys:
                    winning += 1
                else:
                    losing += 1

        result.winning_trades = winning
        result.losing_trades = losing
        result.win_rate = (
            (winning / (winning + losing)) * 100
            if (winning + losing) > 0
            else 0.0
        )
