"""
AI Trading Agent -- MCP Client using Google Gemini.
Connects to all three MCP servers and makes trading decisions.
"""
from __future__ import annotations

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, RISK_THRESHOLDS
from agent.prompts import SYSTEM_PROMPT, ANALYSIS_PROMPT
from mcp_servers.price_alert_server import (
    set_price_alert,
    list_alerts,
    delete_alert,
    check_alerts,
)
from mcp_servers.watchlist_server import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist_snapshot,
    clear_watchlist,
)

logger = logging.getLogger(__name__)

DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "AMZN", "JPM", "XOM", "LMT", "JNJ"]


class TradingAgent:
    """
    AI Trading Agent that uses Gemini to make stock trading decisions.
    Calls MCP server tools directly (in-process) rather than over HTTP,
    making it simpler to run and test.
    """

    def __init__(
        self,
        watchlist: list[str] | None = None,
        api_key: str | None = None,
    ):
        self.watchlist = watchlist or DEFAULT_WATCHLIST
        self._api_key = api_key or GEMINI_API_KEY
        self._client = genai.Client(api_key=self._api_key)
        self._model = GEMINI_MODEL

        self._financial_tools = {}
        self._geopolitical_tools = {}
        self._trade_tools = {}
        self._banking_tools = {}
        self._pattern_tools = {}
        self._risk_metrics_tools = {}
        self._last_risk_score: float = 50.0
        self._analysis_history: list[dict] = []
        self._live_actions: list[dict] = []

    def _register_tools(self):
        """Import and register all MCP server tool functions."""
        from mcp_servers.financial_data_server import (
            get_stock_price, get_stock_history, get_technical_indicators,
            get_market_overview, search_stocks,
        )
        from mcp_servers.geopolitical_server import (
            get_global_news, get_news_sentiment, get_geopolitical_risk_score,
            get_region_risk, get_sector_impact, get_conflict_monitor,
        )
        from mcp_servers.trade_server import (
            buy_stock, sell_stock, get_portfolio, get_account_balance,
            get_trade_history, get_open_orders, cancel_order,
        )
        from mcp_servers.banking_server import (
            get_bank_accounts, get_bank_transactions, initiate_brokerage_transfer,
        )
        from mcp_servers.price_alert_server import (
            set_price_alert, list_alerts, delete_alert, check_alerts,
        )
        from mcp_servers.watchlist_server import (
            add_to_watchlist, remove_from_watchlist, get_watchlist_snapshot, clear_watchlist,
        )
        from mcp_servers.pattern_scanner_server import scan_patterns, get_signal_summary
        from mcp_servers.risk_metrics_server import (
            get_portfolio_risk_metrics, get_stock_risk_profile,
        )

        self._financial_tools = {
            "get_stock_price": get_stock_price,
            "get_stock_history": get_stock_history,
            "get_technical_indicators": get_technical_indicators,
            "get_market_overview": get_market_overview,
            "search_stocks": search_stocks,
        }
        self._geopolitical_tools = {
            "get_global_news": get_global_news,
            "get_news_sentiment": get_news_sentiment,
            "get_geopolitical_risk_score": get_geopolitical_risk_score,
            "get_region_risk": get_region_risk,
            "get_sector_impact": get_sector_impact,
            "get_conflict_monitor": get_conflict_monitor,
        }
        self._trade_tools = {
            "buy_stock": buy_stock,
            "sell_stock": sell_stock,
            "get_portfolio": get_portfolio,
            "get_account_balance": get_account_balance,
            "get_trade_history": get_trade_history,
            "get_open_orders": get_open_orders,
            "cancel_order": cancel_order,
        }
        self._banking_tools = {
            "get_bank_accounts": get_bank_accounts,
            "get_bank_transactions": get_bank_transactions,
            "initiate_brokerage_transfer": initiate_brokerage_transfer,
        }
        self._alert_tools = {
            "set_price_alert": set_price_alert,
            "list_alerts": list_alerts,
            "delete_alert": delete_alert,
            "check_alerts": check_alerts,
        }
        self._watchlist_tools = {
            "add_to_watchlist": add_to_watchlist,
            "remove_from_watchlist": remove_from_watchlist,
            "get_watchlist_snapshot": get_watchlist_snapshot,
            "clear_watchlist": clear_watchlist,
        }
        self._pattern_tools = {
            "scan_patterns": scan_patterns,
            "get_signal_summary": get_signal_summary,
        }
        self._risk_metrics_tools = {
            "get_portfolio_risk_metrics": get_portfolio_risk_metrics,
            "get_stock_risk_profile": get_stock_risk_profile,
        }

    def _all_tools(self) -> dict:
        return {
            **self._financial_tools,
            **self._geopolitical_tools,
            **self._trade_tools,
            **self._banking_tools,
            **self._alert_tools,
            **self._watchlist_tools,
            **self._pattern_tools,
            **self._risk_metrics_tools,
        }

    def _build_gemini_tools(self) -> list[types.Tool]:
        """Build Gemini function declarations from the registered MCP tools."""
        declarations = []

        tool_schemas = {
            "get_stock_price": {
                "description": "Get the current price and key metrics for a stock symbol.",
                "params": {"symbol": {"type": "STRING", "description": "Stock ticker symbol (e.g. AAPL)"}},
                "required": ["symbol"],
            },
            "get_stock_history": {
                "description": "Get historical OHLCV data for a stock. period: 1d,5d,1mo,3mo,6mo,1y. interval: 1m,5m,15m,1h,1d.",
                "params": {
                    "symbol": {"type": "STRING", "description": "Stock ticker symbol"},
                    "period": {"type": "STRING", "description": "Time period (default: 1mo)"},
                    "interval": {"type": "STRING", "description": "Data interval (default: 1d)"},
                },
                "required": ["symbol"],
            },
            "get_technical_indicators": {
                "description": "Calculate technical indicators: RSI, MACD, Bollinger Bands, SMA, EMA.",
                "params": {
                    "symbol": {"type": "STRING", "description": "Stock ticker symbol"},
                    "period": {"type": "STRING", "description": "Period for calculation (default: 3mo)"},
                },
                "required": ["symbol"],
            },
            "get_market_overview": {
                "description": "Get overview of major market indices: S&P 500, NASDAQ, DOW, VIX.",
                "params": {},
                "required": [],
            },
            "search_stocks": {
                "description": "Search for stock tickers matching a company name or keyword.",
                "params": {"query": {"type": "STRING", "description": "Search query"}},
                "required": ["query"],
            },
            "get_global_news": {
                "description": "Fetch latest global news articles. Returns headlines, sources, and sentiment.",
                "params": {
                    "query": {"type": "STRING", "description": "News search query (default: geopolitical)"},
                    "count": {"type": "INTEGER", "description": "Number of articles (default: 10)"},
                },
                "required": [],
            },
            "get_news_sentiment": {
                "description": "Get aggregate sentiment analysis for recent news on a topic.",
                "params": {"query": {"type": "STRING", "description": "Topic to analyze sentiment for"}},
                "required": ["query"],
            },
            "get_geopolitical_risk_score": {
                "description": "Compute composite geopolitical risk score 0-100. 0=calm, 100=extreme risk.",
                "params": {},
                "required": [],
            },
            "get_region_risk": {
                "description": "Get risk assessment for a region: middle_east, east_asia, europe, south_asia, americas.",
                "params": {"region": {"type": "STRING", "description": "Region name"}},
                "required": ["region"],
            },
            "get_sector_impact": {
                "description": "Analyze how geopolitical events impact a sector: energy, defense, technology, finance, healthcare, consumer.",
                "params": {"sector": {"type": "STRING", "description": "Market sector name"}},
                "required": ["sector"],
            },
            "get_conflict_monitor": {
                "description": "Monitor active global conflicts and their potential market impact.",
                "params": {},
                "required": [],
            },
            "buy_stock": {
                "description": "Place a buy order. order_type: 'market' or 'limit'.",
                "params": {
                    "symbol": {"type": "STRING", "description": "Stock ticker"},
                    "quantity": {"type": "NUMBER", "description": "Number of shares"},
                    "order_type": {"type": "STRING", "description": "market or limit (default: market)"},
                    "limit_price": {"type": "NUMBER", "description": "Limit price (for limit orders)"},
                    "reasoning": {"type": "STRING", "description": "Reason for the trade"},
                    "risk_score": {"type": "NUMBER", "description": "Current geopolitical risk score"},
                },
                "required": ["symbol", "quantity"],
            },
            "sell_stock": {
                "description": "Place a sell order. order_type: 'market' or 'limit'.",
                "params": {
                    "symbol": {"type": "STRING", "description": "Stock ticker"},
                    "quantity": {"type": "NUMBER", "description": "Number of shares"},
                    "order_type": {"type": "STRING", "description": "market or limit (default: market)"},
                    "limit_price": {"type": "NUMBER", "description": "Limit price (for limit orders)"},
                    "reasoning": {"type": "STRING", "description": "Reason for the trade"},
                    "risk_score": {"type": "NUMBER", "description": "Current geopolitical risk score"},
                },
                "required": ["symbol", "quantity"],
            },
            "get_portfolio": {
                "description": "Get current portfolio including all positions and their P&L.",
                "params": {},
                "required": [],
            },
            "get_account_balance": {
                "description": "Get account balance: cash, positions value, total value, return.",
                "params": {},
                "required": [],
            },
            "get_trade_history": {
                "description": "Get recent trade history with timestamps and AI reasoning.",
                "params": {"limit": {"type": "INTEGER", "description": "Max number of trades (default: 50)"}},
                "required": [],
            },
            "get_open_orders": {
                "description": "Get all pending limit orders.",
                "params": {},
                "required": [],
            },
            "cancel_order": {
                "description": "Cancel a pending limit order by its ID.",
                "params": {"order_id": {"type": "STRING", "description": "Order ID to cancel"}},
                "required": ["order_id"],
            },
            "get_bank_accounts": {
                "description": "Get all linked bank accounts and their current balances.",
                "params": {},
                "required": [],
            },
            "get_bank_transactions": {
                "description": "Get recent transactions for a specific bank account or all accounts.",
                "params": {
                    "account_id": {"type": "STRING", "description": "Optional account ID filter"},
                    "limit": {"type": "INTEGER", "description": "Max number of transactions (default: 10)"},
                },
                "required": [],
            },
            "initiate_brokerage_transfer": {
                "description": "Transfer funds from a bank account to the brokerage account.",
                "params": {
                    "amount": {"type": "NUMBER", "description": "Amount to transfer"},
                    "account_id": {"type": "STRING", "description": "Source bank account ID"},
                },
                "required": ["amount", "account_id"],
            },
            "set_price_alert": {
                "description": "Set a price alert for a stock. The agent will notify the user when the stock crosses the specified target price.",
                "params": {
                    "ticker": {"type": "STRING", "description": "Stock symbol, e.g. 'AAPL'"},
                    "target_price": {"type": "NUMBER", "description": "The price level to watch"},
                    "condition": {"type": "STRING", "description": "'above' or 'below'"},
                    "note": {"type": "STRING", "description": "Optional note for the user"},
                },
                "required": ["ticker", "target_price", "condition"],
            },
            "list_alerts": {
                "description": "List the user's price alerts, filtered by status.",
                "params": {
                    "status_filter": {
                        "type": "STRING",
                        "description": "One of 'active', 'triggered', 'deleted', or 'all'. Default: 'active'.",
                    }
                },
                "required": [],
            },
            "delete_alert": {
                "description": "Cancel and delete an active price alert by its numeric ID.",
                "params": {
                    "alert_id": {"type": "INTEGER", "description": "The ID of the alert to delete"}
                },
                "required": ["alert_id"],
            },
            "check_alerts": {
                "description": "Evaluate all active price alerts against current live prices. Returns any newly triggered alerts so the agent can notify the user.",
                "params": {},
                "required": [],
            },
            "add_to_watchlist": {
                "description": "Add a stock to the user's personal watchlist with an optional note.",
                "params": {
                    "ticker": {"type": "STRING", "description": "Stock symbol to watch, e.g. 'NVDA'"},
                    "notes": {"type": "STRING", "description": "Optional reason for watching"},
                },
                "required": ["ticker"],
            },
            "remove_from_watchlist": {
                "description": "Remove a stock from the user's watchlist.",
                "params": {
                    "ticker": {"type": "STRING", "description": "Stock symbol to remove"}
                },
                "required": ["ticker"],
            },
            "get_watchlist_snapshot": {
                "description": "Fetch a live price snapshot of every stock on the user's watchlist, including daily change % and change since the stock was added.",
                "params": {},
                "required": [],
            },
            "clear_watchlist": {
                "description": "Remove ALL stocks from the user's watchlist. Always confirm with the user before calling this.",
                "params": {},
                "required": [],
            },
            "scan_patterns": {
                "description": (
                    "Scan multiple stocks for active technical signals and return a bullish/bearish "
                    "bias with a signal score for each. Detects: golden cross, death cross (SMA 50/200), "
                    "RSI overbought/oversold, MACD crossover, and Bollinger Band breakouts. "
                    "Use this to identify which stocks have the most setup opportunities right now."
                ),
                "params": {
                    "symbols": {
                        "type": "STRING",
                        "description": "Comma-separated list of ticker symbols, e.g. 'AAPL,MSFT,NVDA'.",
                    }
                },
                "required": ["symbols"],
            },
            "get_signal_summary": {
                "description": (
                    "Get a detailed breakdown of all current technical signals for a single stock: "
                    "RSI, MACD differential, Bollinger Band levels, SMA crossover status, and a "
                    "signal score with bullish/bearish/neutral bias."
                ),
                "params": {
                    "symbol": {"type": "STRING", "description": "Stock ticker symbol, e.g. 'AAPL'."}
                },
                "required": ["symbol"],
            },
            "get_portfolio_risk_metrics": {
                "description": (
                    "Compute portfolio-level quantitative risk metrics using 1 year of daily return data: "
                    "Value at Risk (VaR 95%/99% in dollars), Sharpe Ratio, Sortino Ratio, portfolio beta "
                    "vs S&P 500, annualized volatility, sector concentration (% weight per sector), and "
                    "maximum drawdown. Call this before making large trades to assess current risk exposure."
                ),
                "params": {},
                "required": [],
            },
            "get_stock_risk_profile": {
                "description": (
                    "Get individual stock risk metrics for any ticker: annualized volatility, beta vs "
                    "S&P 500, maximum drawdown, Sharpe ratio, and average daily return over the chosen period."
                ),
                "params": {
                    "symbol": {"type": "STRING", "description": "Stock ticker symbol, e.g. 'AAPL'."},
                    "period": {
                        "type": "STRING",
                        "description": "Lookback period: '1y', '6mo', '3mo', or '2y'. Default: '1y'.",
                    },
                },
                "required": ["symbol"],
            },
        }

        for name, schema in tool_schemas.items():
            properties = {}
            for param_name, param_info in schema["params"].items():
                properties[param_name] = types.Schema(
                    type=param_info["type"],
                    description=param_info["description"],
                )

            fn_decl = types.FunctionDeclaration(
                name=name,
                description=schema["description"],
                parameters=types.Schema(
                    type="OBJECT",
                    properties=properties,
                    required=schema["required"],
                ) if properties else None,
            )
            declarations.append(fn_decl)

        return [types.Tool(function_declarations=declarations)]

    def _execute_tool_call(self, function_name: str, args: dict) -> str:
        """Execute a tool call and return the result."""
        all_tools = self._all_tools()
        if function_name not in all_tools:
            return json.dumps({"error": f"Unknown tool: {function_name}"})

        try:
            fn = all_tools[function_name]
            filtered_args = {k: v for k, v in args.items() if v is not None}
            result = fn(**filtered_args)
            logger.info(f"Tool call: {function_name}({filtered_args}) -> {result[:200]}...")
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {function_name}: {e}")
            return json.dumps({"error": str(e)})

    def run_analysis(self, custom_prompt: str | None = None) -> dict:
        """
        Run a full trading analysis cycle.
        The agent will use Gemini to analyze markets and make trades.
        """
        self._register_tools()

        portfolio = self._execute_tool_call("get_portfolio", {})
        balance = self._execute_tool_call("get_account_balance", {})

        prompt = custom_prompt or ANALYSIS_PROMPT.format(
            portfolio=portfolio,
            balance=balance,
            watchlist=", ".join(self.watchlist),
        )

        tools = self._build_gemini_tools()
        messages = [
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
        ]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=tools,
            temperature=0.3,
        )

        max_iterations = 15
        full_reasoning = []
        self._live_actions = []

        for iteration in range(max_iterations):
            response = self._client.models.generate_content(
                model=self._model,
                contents=messages,
                config=config,
            )

            candidate = response.candidates[0]
            messages.append(candidate.content)

            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if part.function_call
            ]

            if not function_calls:
                text_parts = [
                    part.text for part in candidate.content.parts if part.text
                ]
                full_reasoning.extend(text_parts)
                break

            tool_responses = []
            for fc in function_calls:
                result = self._execute_tool_call(fc.name, dict(fc.args))
                tool_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response=json.loads(result),
                    )
                )

                if fc.name == "get_geopolitical_risk_score":
                    try:
                        risk_data = json.loads(result)
                        self._last_risk_score = risk_data.get("composite_score", 50)
                    except (json.JSONDecodeError, KeyError):
                        pass

                if fc.name in ("buy_stock", "sell_stock"):
                    try:
                        result_data = json.loads(result)
                        args = dict(fc.args)
                        self._live_actions.append({
                            "action": fc.name,
                            "symbol": args.get("symbol", ""),
                            "quantity": args.get("quantity", 0),
                            "order_type": args.get("order_type", "market"),
                            "reasoning": args.get("reasoning", ""),
                            "risk_score": args.get("risk_score", 0),
                            "status": result_data.get("status", "unknown"),
                            "price": result_data.get("price"),
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                    except Exception:
                        pass

            messages.append(types.Content(role="user", parts=tool_responses))

        analysis = {
            "timestamp": datetime.utcnow().isoformat(),
            "reasoning": "\n".join(full_reasoning),
            "risk_score": self._last_risk_score,
            "iterations": min(iteration + 1, max_iterations),
            "portfolio_after": json.loads(self._execute_tool_call("get_portfolio", {})),
            "balance_after": json.loads(self._execute_tool_call("get_account_balance", {})),
        }
        self._analysis_history.append(analysis)
        return analysis

    def get_analysis_history(self) -> list[dict]:
        return self._analysis_history

    def get_live_actions(self) -> list[dict]:
        """Return the structured buy/sell actions from the most recent analysis cycle."""
        return list(self._live_actions)

    def chat(self, user_message: str) -> str:
        """
        Interactive chat mode -- ask the agent anything about markets.
        It can look up data and execute trades via tool calls.
        """
        self._register_tools()

        tools = self._build_gemini_tools()
        messages = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
        ]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=tools,
            temperature=0.4,
        )

        for _ in range(10):
            response = self._client.models.generate_content(
                model=self._model,
                contents=messages,
                config=config,
            )

            candidate = response.candidates[0]
            messages.append(candidate.content)

            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if part.function_call
            ]

            if not function_calls:
                text_parts = [
                    part.text for part in candidate.content.parts if part.text
                ]
                return "\n".join(text_parts)

            tool_responses = []
            for fc in function_calls:
                result = self._execute_tool_call(fc.name, dict(fc.args))
                tool_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response=json.loads(result),
                    )
                )

            messages.append(types.Content(role="user", parts=tool_responses))

        return "Analysis complete. Max iterations reached."
