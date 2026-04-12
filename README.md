# AI Stock Trading Agent with MCP

An AI-powered stock trading agent that uses **Model Context Protocol (MCP)** to combine real-time financial data with geopolitical risk assessment for informed trading decisions.

## Architecture

The system consists of four main components:

### MCP Servers
1. **Financial Data Server** - Real-time stock prices, historical data, and technical indicators (RSI, MACD, Bollinger Bands) via yfinance
2. **Geopolitical Intelligence Server** - Global news fetching, sentiment analysis (VADER), and composite geopolitical risk scoring
3. **Trade Execution Server** - Buy/sell order execution, portfolio management, and trade history

### AI Agent
- Uses **Google Gemini** as the LLM brain
- Connects to all three MCP servers via function calling
- Implements a risk-adjusted decision framework:
  - Low risk (< 30): Normal trading following technical signals
  - Medium risk (30-70): Reduced position sizes, defensive sectors
  - High risk (> 70): Minimal exposure, safe-haven assets

### Simulator
- **Paper Trading**: Real-time simulation with live market data and virtual money
- **Backtesting**: Historical data replay with performance metrics (Sharpe ratio, max drawdown, win rate)

### Dashboard
- Streamlit web application with portfolio overview, stock analysis, geopolitical risk visualization, trade history, backtesting interface, and settings

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the example env file and add your keys:

```bash
copy .env.example .env
```

Edit `.env` and set:
- `GEMINI_API_KEY` - Get from [Google AI Studio](https://aistudio.google.com/)
- `NEWS_API_KEY` - Get from [NewsAPI.org](https://newsapi.org/) (free tier)

### 3. Run

**Web Dashboard** (recommended):
```bash
python main.py dashboard
```
Or directly:
```bash
streamlit run dashboard/app.py
```

**Interactive CLI Agent**:
```bash
python main.py agent
```

**MCP Servers Only** (standalone):
```bash
python main.py servers
```

## Project Structure

```
project/
├── main.py                         # Entry point (dashboard/agent/servers)
├── config.py                       # Configuration and environment variables
├── requirements.txt                # Python dependencies
├── .env.example                    # API keys template
├── mcp_servers/
│   ├── financial_data_server.py    # MCP Server: Stock data & technicals
│   ├── geopolitical_server.py      # MCP Server: News & risk scoring
│   └── trade_server.py             # MCP Server: Trade execution
├── agent/
│   ├── trading_agent.py            # AI agent with Gemini integration
│   ├── strategies.py               # Trading strategies (momentum, mean reversion, defensive)
│   └── prompts.py                  # System and analysis prompts
├── simulator/
│   ├── models.py                   # Data models (Order, Position, Trade)
│   ├── portfolio_manager.py        # Portfolio tracking and P&L
│   ├── paper_trading.py            # Paper trading engine
│   └── backtesting.py              # Backtesting engine
├── dashboard/
│   ├── app.py                      # Streamlit main app
│   ├── pages/                      # Dashboard pages
│   └── components/                 # Charts and widgets
└── data/
    ├── trades.db                   # SQLite trade history (auto-created)
    └── cache/                      # API response cache
```

## How MCP is Used

MCP serves as the standardized interface between the AI agent and all data/action sources:

- The AI agent (Gemini) makes **MCP tool calls** to fetch stock data, assess geopolitical risk, and execute trades
- Each MCP server exposes **tools** (functions the AI can call) and **resources** (data endpoints)
- The architecture is **decoupled**: swap data providers or LLMs without changing the agent logic
- Every tool call is logged, creating a full **audit trail** of AI decision-making

## Technologies

- **Python 3.10+**
- **MCP SDK** (FastMCP) - Model Context Protocol
- **Google Gemini** - LLM for analysis and decisions
- **yfinance** - Stock market data
- **NewsAPI** - Global news
- **VADER Sentiment** - News sentiment analysis
- **Streamlit + Plotly** - Web dashboard
- **SQLAlchemy + SQLite** - Trade history storage
- **ta** - Technical analysis indicators
