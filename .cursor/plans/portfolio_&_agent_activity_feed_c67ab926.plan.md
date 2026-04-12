---
name: Portfolio & Agent Activity Feed
overview: Add a dedicated "My Portfolio" page showing everything the user owns with live prices, and enrich the agent to capture each buy/sell decision as a structured event so users can see exactly what the agent did and why in a clear activity feed.
todos:
  - id: agent-live-actions
    content: Add _live_actions capture to TradingAgent.run_analysis() in agent/trading_agent.py
    status: pending
  - id: allocation-chart
    content: Add create_allocation_pie() chart to dashboard/components/charts.py
    status: pending
  - id: portfolio-page
    content: Create new dashboard/views/portfolio.py with holdings table, allocation chart, and agent actions feed
    status: pending
  - id: overview-actions-summary
    content: Update dashboard/views/overview.py to show compact agent actions summary after a cycle runs
    status: pending
  - id: nav-update
    content: Add My Portfolio to navigation in dashboard/app.py
    status: pending
isProject: false
---

# Portfolio Page & Live Agent Activity Feed

## What's Missing

1. **No dedicated ownership page.** Holdings are a tiny widget buried in Overview. The user can't easily see what they own, how much they paid, what each position is worth today, or their P&L per stock.

2. **Agent decisions are opaque.** `run_analysis()` in [agent/trading_agent.py](agent/trading_agent.py) returns only a wall of reasoning text. When a `buy_stock` or `sell_stock` tool call fires inside the loop, nothing records it as a structured event -- so there's no clear "the agent bought X shares of Y because Z" feed.

## Changes

### 1. Update `agent/trading_agent.py` -- Capture live actions

Add a `_live_actions: list[dict]` attribute to `TradingAgent`. Inside `run_analysis()`, the function-call loop already processes every tool call. Extend it to detect `buy_stock` / `sell_stock` calls and record them:

```python
# Clear at the start of each cycle
self._live_actions = []

# Inside the tool-call loop, after _execute_tool_call:
if fc.name in ("buy_stock", "sell_stock"):
    result_data = json.loads(result)
    self._live_actions.append({
        "action": fc.name,
        "symbol": fc.args.get("symbol"),
        "quantity": fc.args.get("quantity"),
        "order_type": fc.args.get("order_type", "market"),
        "reasoning": fc.args.get("reasoning", ""),
        "risk_score": fc.args.get("risk_score", 0),
        "status": result_data.get("status"),
        "price": result_data.get("price"),
        "timestamp": datetime.utcnow().isoformat(),
    })
```

Also add a `get_live_actions()` method that returns `_live_actions`. These survive between Streamlit reruns because the agent is a `@st.cache_resource`.

### 2. New page `dashboard/views/portfolio.py`

A dedicated "My Portfolio" page with four sections:

**Section A -- Account Summary bar** (4 metrics across the top)
- Total Portfolio Value (with delta from initial balance)
- Cash Available
- Invested Value (positions)
- Total Return %

**Section B -- Holdings table** (the main content)
Each owned stock gets a row with:
- Symbol + company name (looked up from yfinance `fast_info`)
- Shares owned
- Avg Cost (what you paid per share)
- Current Price (live from yfinance, color-coded green/red vs avg cost)
- Market Value (shares × current price)
- Unrealized P&L in $ and %
- A mini colored bar showing gain/loss magnitude

A "Refresh Prices" button fetches live prices for all positions.

**Section C -- Allocation pie chart**
A Plotly donut chart showing portfolio allocation: each stock as a slice + a cash slice, so the user can see diversification at a glance.

**Section D -- Last Agent Cycle Actions feed**
Shows `agent.get_live_actions()`. If the agent has run at least once, shows each trade it made as a structured card:

```
[BUY]  AAPL  ×10 shares @ $213.50          ✓ filled
       Risk score: 45  |  14:23:01 UTC
       "RSI oversold at 28, price below SMA20, low geopolitical risk"

[SELL] TSLA  ×5 shares @ $178.20           ✓ filled
       Risk score: 72  |  14:23:04 UTC
       "High geopolitical risk - rotating out of growth stocks"
```

If no agent cycle has run yet, shows a prompt to run one.

### 3. Update `dashboard/app.py`

Add "My Portfolio" to the navigation dict so it appears in the sidebar:

```python
pages = {
    "Overview": "overview",
    "My Portfolio": "portfolio",      # new
    "Stock Analysis": "stock_analysis",
    ...
}
```

### 4. Update `dashboard/views/overview.py` -- agent actions preview

After "Run AI Analysis Cycle" completes, instead of only showing the reasoning expander, also show a compact inline summary:

```
Agent completed: 3 trades executed
  BUY  NVDA ×8   @ $487.20   "momentum signal + low risk"
  SELL TSLA ×12  @ $178.50   "high risk rotation"
  BUY  LMT  ×3   @ $441.00   "defense sector hedge"
```

This uses the same `agent.get_live_actions()` data -- no new state needed.

### 5. New chart in `dashboard/components/charts.py`

Add `create_allocation_pie(positions, cash)` -- a Plotly donut chart for the portfolio page.

## Files Changed

- `agent/trading_agent.py` -- add `_live_actions` capture in `run_analysis()`
- `dashboard/views/portfolio.py` -- new dedicated portfolio page
- `dashboard/views/overview.py` -- add compact agent actions summary after cycle
- `dashboard/app.py` -- add "My Portfolio" to navigation
- `dashboard/components/charts.py` -- add `create_allocation_pie()`
