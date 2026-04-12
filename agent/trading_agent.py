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

    def _all_tools(self) -> dict:
        return {**self._financial_tools, **self._geopolitical_tools, **self._trade_tools}

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
