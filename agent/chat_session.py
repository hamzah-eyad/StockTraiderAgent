"""
ChatSession: multi-turn conversational agent for the AI Assistant page.

Wraps Gemini 2.5 Flash with a read-only MCP tool subset plus a special
`propose_trade` tool. Actual buy/sell execution is done by the UI layer
after the user confirms — the model never calls `buy_stock`/`sell_stock`
directly from this session.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from agent.prompts import CHATBOT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ChatSession:
    """Stateful multi-turn chat session backed by Gemini."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or GEMINI_API_KEY
        self._model = model or GEMINI_MODEL
        self._client = genai.Client(api_key=self._api_key)
        self.history: list[types.Content] = []
        self._read_tools: dict[str, Any] = {}
        self._register_tools()

    def reset(self) -> None:
        self.history = []

    def _register_tools(self) -> None:
        from mcp_servers.financial_data_server import (
            get_stock_price, get_stock_history, get_technical_indicators,
            get_market_overview, search_stocks,
        )
        from mcp_servers.geopolitical_server import (
            get_global_news, get_news_sentiment, get_geopolitical_risk_score,
            get_region_risk, get_sector_impact, get_conflict_monitor,
        )
        from mcp_servers.trade_server import (
            get_portfolio, get_account_balance, get_trade_history, get_open_orders,
        )
        from mcp_servers.banking_server import (
            get_bank_accounts, get_bank_transactions,
        )
        from mcp_servers.price_alert_server import (
            set_price_alert, list_alerts, delete_alert, check_alerts,
        )
        from mcp_servers.watchlist_server import (
            add_to_watchlist, remove_from_watchlist, get_watchlist_snapshot,
        )
        from mcp_servers.pattern_scanner_server import scan_patterns, get_signal_summary
        from mcp_servers.risk_metrics_server import (
            get_portfolio_risk_metrics, get_stock_risk_profile,
        )

        self._read_tools = {
            "get_stock_price": get_stock_price,
            "get_stock_history": get_stock_history,
            "get_technical_indicators": get_technical_indicators,
            "get_market_overview": get_market_overview,
            "search_stocks": search_stocks,
            "get_global_news": get_global_news,
            "get_news_sentiment": get_news_sentiment,
            "get_geopolitical_risk_score": get_geopolitical_risk_score,
            "get_region_risk": get_region_risk,
            "get_sector_impact": get_sector_impact,
            "get_conflict_monitor": get_conflict_monitor,
            "get_portfolio": get_portfolio,
            "get_account_balance": get_account_balance,
            "get_trade_history": get_trade_history,
            "get_open_orders": get_open_orders,
            "get_bank_accounts": get_bank_accounts,
            "get_bank_transactions": get_bank_transactions,
            "set_price_alert": set_price_alert,
            "list_alerts": list_alerts,
            "delete_alert": delete_alert,
            "check_alerts": check_alerts,
            "add_to_watchlist": add_to_watchlist,
            "remove_from_watchlist": remove_from_watchlist,
            "get_watchlist_snapshot": get_watchlist_snapshot,
            "scan_patterns": scan_patterns,
            "get_signal_summary": get_signal_summary,
            "get_portfolio_risk_metrics": get_portfolio_risk_metrics,
            "get_stock_risk_profile": get_stock_risk_profile,
        }

    # ── Tool schema construction ──────────────────────────────────────────────
    def _build_tools(self) -> list[types.Tool]:
        S = types.Schema

        schemas: dict[str, dict] = {
            "get_stock_price": {
                "description": "Get the current price and key metrics for a stock symbol.",
                "params": {"symbol": ("STRING", "Stock ticker (e.g. AAPL)")},
                "required": ["symbol"],
            },
            "get_stock_history": {
                "description": "Historical OHLCV. period: 1d,5d,1mo,3mo,6mo,1y. interval: 1m,5m,15m,1h,1d.",
                "params": {
                    "symbol": ("STRING", "Ticker"),
                    "period": ("STRING", "Default 1mo"),
                    "interval": ("STRING", "Default 1d"),
                },
                "required": ["symbol"],
            },
            "get_technical_indicators": {
                "description": "RSI, MACD, Bollinger Bands, SMA/EMA for a stock.",
                "params": {
                    "symbol": ("STRING", "Ticker"),
                    "period": ("STRING", "Default 3mo"),
                },
                "required": ["symbol"],
            },
            "get_market_overview": {
                "description": "Overview of S&P 500, NASDAQ, DOW, VIX.",
                "params": {},
                "required": [],
            },
            "search_stocks": {
                "description": "Search tickers by company name or keyword.",
                "params": {"query": ("STRING", "Search query")},
                "required": ["query"],
            },
            "get_global_news": {
                "description": "Latest global news with sentiment.",
                "params": {
                    "query": ("STRING", "Default: geopolitical"),
                    "count": ("INTEGER", "Default 10"),
                },
                "required": [],
            },
            "get_news_sentiment": {
                "description": "Aggregate sentiment for a topic.",
                "params": {"query": ("STRING", "Topic")},
                "required": ["query"],
            },
            "get_geopolitical_risk_score": {
                "description": "Composite geopolitical risk score 0-100.",
                "params": {},
                "required": [],
            },
            "get_region_risk": {
                "description": "Risk for a region: middle_east, east_asia, europe, south_asia, americas.",
                "params": {"region": ("STRING", "Region name")},
                "required": ["region"],
            },
            "get_sector_impact": {
                "description": "Geopolitical impact on a sector: energy, defense, technology, finance, healthcare, consumer.",
                "params": {"sector": ("STRING", "Sector name")},
                "required": ["sector"],
            },
            "get_conflict_monitor": {
                "description": "Active global conflicts and their market impact.",
                "params": {},
                "required": [],
            },
            "get_portfolio": {
                "description": "Current portfolio: all positions and their P&L. Use this whenever the user asks what they own.",
                "params": {},
                "required": [],
            },
            "get_account_balance": {
                "description": "Account balance: cash, positions value, total value, total return. Use this whenever the user asks how much money they have.",
                "params": {},
                "required": [],
            },
            "get_trade_history": {
                "description": "Recent trade history with timestamps and reasoning.",
                "params": {"limit": ("INTEGER", "Default 50")},
                "required": [],
            },
            "get_open_orders": {
                "description": "All pending limit orders.",
                "params": {},
                "required": [],
            },
            "get_bank_accounts": {
                "description": "Linked bank accounts and balances.",
                "params": {},
                "required": [],
            },
            "get_bank_transactions": {
                "description": "Recent transactions for a bank account.",
                "params": {
                    "account_id": ("STRING", "Optional account filter"),
                    "limit": ("INTEGER", "Default 10"),
                },
                "required": [],
            },
            "set_price_alert": {
                "description": "Set a price alert on a ticker.",
                "params": {
                    "ticker": ("STRING", "Stock symbol"),
                    "target_price": ("NUMBER", "Target price"),
                    "condition": ("STRING", "'above' or 'below'"),
                    "note": ("STRING", "Optional note"),
                },
                "required": ["ticker", "target_price", "condition"],
            },
            "list_alerts": {
                "description": "List price alerts. status_filter: 'active','triggered','deleted','all'.",
                "params": {"status_filter": ("STRING", "Default: active")},
                "required": [],
            },
            "delete_alert": {
                "description": "Delete a price alert by ID.",
                "params": {"alert_id": ("INTEGER", "Alert ID")},
                "required": ["alert_id"],
            },
            "check_alerts": {
                "description": "Evaluate active price alerts against current prices.",
                "params": {},
                "required": [],
            },
            "add_to_watchlist": {
                "description": "Add a stock to the user's watchlist.",
                "params": {
                    "ticker": ("STRING", "Stock symbol"),
                    "notes": ("STRING", "Optional reason"),
                },
                "required": ["ticker"],
            },
            "remove_from_watchlist": {
                "description": "Remove a stock from the watchlist.",
                "params": {"ticker": ("STRING", "Stock symbol")},
                "required": ["ticker"],
            },
            "get_watchlist_snapshot": {
                "description": "Live snapshot of every watchlist stock.",
                "params": {},
                "required": [],
            },
            "scan_patterns": {
                "description": "Scan multiple tickers for bullish/bearish signals.",
                "params": {"symbols": ("STRING", "Comma-separated tickers")},
                "required": ["symbols"],
            },
            "get_signal_summary": {
                "description": "Detailed current technical signals for a single stock.",
                "params": {"symbol": ("STRING", "Ticker")},
                "required": ["symbol"],
            },
            "get_portfolio_risk_metrics": {
                "description": "Portfolio-level risk metrics: VaR, Sharpe, beta, concentration, drawdown.",
                "params": {},
                "required": [],
            },
            "get_stock_risk_profile": {
                "description": "Individual stock risk metrics.",
                "params": {
                    "symbol": ("STRING", "Ticker"),
                    "period": ("STRING", "1y, 6mo, 3mo, 2y. Default 1y"),
                },
                "required": ["symbol"],
            },
            # Special UI-mediated tool — never executed server-side
            "propose_trade": {
                "description": (
                    "Propose a buy or sell trade for the user to confirm. "
                    "This does NOT execute the trade — the UI will show a confirmation card "
                    "with Confirm/Cancel buttons. ALWAYS use this instead of claiming a trade was placed. "
                    "Explain your reasoning in the `reasoning` field."
                ),
                "params": {
                    "symbol": ("STRING", "Stock ticker, e.g. 'AAPL'"),
                    "side": ("STRING", "'buy' or 'sell'"),
                    "quantity": ("NUMBER", "Number of shares"),
                    "order_type": ("STRING", "'market' or 'limit'. Default 'market'"),
                    "limit_price": ("NUMBER", "Required if order_type is 'limit'"),
                    "reasoning": ("STRING", "Why this trade is appropriate"),
                },
                "required": ["symbol", "side", "quantity"],
            },
        }

        declarations = []
        for name, spec in schemas.items():
            properties = {
                pname: S(type=ptype, description=pdesc)
                for pname, (ptype, pdesc) in spec["params"].items()
            }
            fn_decl = types.FunctionDeclaration(
                name=name,
                description=spec["description"],
                parameters=S(
                    type="OBJECT",
                    properties=properties,
                    required=spec["required"],
                ) if properties else None,
            )
            declarations.append(fn_decl)

        return [types.Tool(function_declarations=declarations)]

    # ── Tool execution (read-only only) ───────────────────────────────────────
    def _execute_read_tool(self, name: str, args: dict) -> str:
        if name not in self._read_tools:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            fn = self._read_tools[name]
            filtered = {k: v for k, v in args.items() if v is not None}
            result = fn(**filtered)
            logger.info(f"ChatSession tool: {name}({filtered}) -> {str(result)[:200]}")
            return result
        except Exception as e:
            logger.error(f"ChatSession tool error {name}: {e}")
            return json.dumps({"error": str(e)})

    # ── Main entry point ──────────────────────────────────────────────────────
    def send(self, user_message: str) -> dict:
        """
        Send a user message, run the Gemini tool-call loop, and return
        {"text": str, "pending_trade": dict|None, "tool_calls": list[str]}.
        """
        self.history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )

        tools = self._build_tools()
        config = types.GenerateContentConfig(
            system_instruction=CHATBOT_SYSTEM_PROMPT,
            tools=tools,
            temperature=0.4,
        )

        tool_calls_used: list[str] = []
        pending_trade: dict | None = None
        final_text_parts: list[str] = []

        for _ in range(8):
            response = self._client.models.generate_content(
                model=self._model,
                contents=self.history,
                config=config,
            )
            candidate = response.candidates[0]
            self.history.append(candidate.content)

            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if part.function_call
            ]
            text_parts = [
                part.text for part in candidate.content.parts if part.text
            ]

            if not function_calls:
                final_text_parts.extend(text_parts)
                break

            tool_responses = []
            trade_proposed = False

            for fc in function_calls:
                tool_calls_used.append(fc.name)

                if fc.name == "propose_trade":
                    args = dict(fc.args)
                    pending_trade = {
                        "symbol": str(args.get("symbol", "")).upper().strip(),
                        "side": str(args.get("side", "buy")).lower().strip(),
                        "quantity": float(args.get("quantity", 0) or 0),
                        "order_type": str(args.get("order_type", "market")).lower().strip(),
                        "limit_price": args.get("limit_price"),
                        "reasoning": args.get("reasoning", ""),
                    }
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={
                                "status": "awaiting_user_confirmation",
                                "message": "The UI will now show a confirmation card to the user. "
                                           "Do NOT call propose_trade again; reply with a short text "
                                           "explaining what you proposed and why.",
                            },
                        )
                    )
                    trade_proposed = True
                else:
                    result = self._execute_read_tool(fc.name, dict(fc.args))
                    try:
                        parsed = json.loads(result)
                    except (json.JSONDecodeError, TypeError):
                        parsed = {"result": str(result)}
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response=parsed if isinstance(parsed, dict) else {"result": parsed},
                        )
                    )

            self.history.append(types.Content(role="user", parts=tool_responses))

            if text_parts:
                final_text_parts.extend(text_parts)

            if trade_proposed:
                # Give the model one more turn to write the explanatory text
                # after the propose_trade function response.
                continue

        text = "\n".join(p for p in final_text_parts if p).strip()
        if not text:
            if pending_trade:
                text = (
                    f"I'm proposing to {pending_trade['side']} "
                    f"{pending_trade['quantity']:g} shares of {pending_trade['symbol']}. "
                    "Please confirm below."
                )
            else:
                text = "Sorry, I couldn't generate a response. Try rephrasing your question."

        return {
            "text": text,
            "pending_trade": pending_trade,
            "tool_calls": tool_calls_used,
        }

    # ── Trade confirmation (UI-driven) ────────────────────────────────────────
    def confirm_trade(self, pending_trade: dict, engine) -> dict:
        """Execute a user-confirmed trade via the paper trading engine."""
        side = pending_trade.get("side", "buy")
        kwargs = dict(
            symbol=pending_trade.get("symbol", ""),
            quantity=float(pending_trade.get("quantity", 0) or 0),
            order_type=pending_trade.get("order_type", "market") or "market",
            limit_price=pending_trade.get("limit_price"),
            reasoning=f"Chatbot-confirmed: {pending_trade.get('reasoning', '')}",
        )
        try:
            if side == "sell":
                result = engine.sell(**kwargs)
            else:
                result = engine.buy(**kwargs)
        except Exception as e:
            result = {"status": "error", "reason": str(e)}

        self.history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text=f"User confirmed the trade. Execution result: {json.dumps(result)}"
                )],
            )
        )
        return result

    def cancel_trade(self, pending_trade: dict) -> None:
        """Record that the user cancelled the proposed trade."""
        self.history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text=(
                        f"User CANCELLED the proposed "
                        f"{pending_trade.get('side','?')} "
                        f"{pending_trade.get('quantity','?')} "
                        f"{pending_trade.get('symbol','?')} trade. Do not retry unless asked."
                    )
                )],
            )
        )
