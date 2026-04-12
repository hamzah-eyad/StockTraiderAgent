"""
Central glossary of financial terms.
Used by widgets and pages to show hover tooltips.
"""

TERMS: dict[str, str] = {
    # Portfolio & Account
    "Total Value": "The combined worth of your entire portfolio: cash on hand plus the current market value of all stock positions you hold.",
    "Cash Available": "Money in your account that is not invested in any stock. This is the amount you can use to buy new shares.",
    "Positions Value": "The total current market value of all stocks you currently own, calculated as shares x current price for each stock.",
    "Total Return": "Your overall profit or loss since you started, shown as a dollar amount and percentage. Positive means you made money, negative means you lost.",
    "Unrealized P&L": "Profit or Loss on stocks you still hold. 'Unrealized' means you haven't sold yet, so the gain/loss could still change.",
    "Cost Basis": "The total amount you originally paid to buy your shares, including any commissions.",
    "Avg Cost": "The average price you paid per share. If you bought the same stock multiple times at different prices, this is the weighted average.",

    # Stock Price Metrics
    "Price": "The most recent trading price of this stock.",
    "Day High": "The highest price this stock reached during today's trading session.",
    "Day Low": "The lowest price this stock reached during today's trading session.",
    "Volume": "The total number of shares traded today. High volume means lots of buying/selling activity.",
    "Market Cap": "The total value of a company, calculated as share price x total shares outstanding. Large-cap > $10B, mid-cap $2-10B, small-cap < $2B.",
    "52-Week High": "The highest price this stock has traded at in the past year (52 weeks).",
    "52-Week Low": "The lowest price this stock has traded at in the past year (52 weeks).",
    "Previous Close": "The price at which this stock ended trading on the previous day.",

    # Technical Indicators
    "RSI (14)": "Relative Strength Index over 14 days. Measures if a stock is overbought (> 70, may drop) or oversold (< 30, may rise). Range: 0-100.",
    "MACD": "Moving Average Convergence Divergence. Shows momentum direction. When MACD crosses above its signal line, it's bullish (upward trend); below is bearish (downward trend).",
    "MACD Signal": "The signal line of the MACD indicator. When MACD is above this line it suggests upward momentum (bullish); below suggests downward momentum (bearish).",
    "MACD Histogram": "The difference between MACD and its signal line. Positive bars = bullish momentum growing, negative bars = bearish momentum growing.",
    "SMA 20": "Simple Moving Average over 20 days. The average closing price of the last 20 trading days. Helps identify short-term price trends.",
    "SMA 50": "Simple Moving Average over 50 days. A medium-term trend indicator. Price above SMA 50 suggests an uptrend; below suggests a downtrend.",
    "EMA 12": "Exponential Moving Average over 12 days. Like SMA but gives more weight to recent prices, making it react faster to price changes.",
    "Bollinger Upper": "The upper Bollinger Band (SMA 20 + 2 standard deviations). Price touching this band may indicate the stock is overbought.",
    "Bollinger Middle": "The middle Bollinger Band, which is simply the 20-day Simple Moving Average.",
    "Bollinger Lower": "The lower Bollinger Band (SMA 20 - 2 standard deviations). Price touching this band may indicate the stock is oversold.",
    "Overbought": "A condition where a stock's price has risen too fast and may be due for a pullback. RSI above 70 signals this.",
    "Oversold": "A condition where a stock's price has fallen too fast and may be due for a rebound. RSI below 30 signals this.",
    "Bullish": "A positive market outlook. Indicates prices are expected to go UP. A bullish signal suggests it may be a good time to buy.",
    "Bearish": "A negative market outlook. Indicates prices are expected to go DOWN. A bearish signal suggests caution or selling.",

    # Geopolitical
    "Geopolitical Risk Score": "A composite score from 0 to 100 measuring global political instability. Calculated from news sentiment across conflicts, sanctions, politics, economics, and energy.",
    "Sentiment": "A measure of the emotional tone in news articles. Positive sentiment = optimistic news, negative = alarming/pessimistic news. Compound score ranges from -1 (very negative) to +1 (very positive).",
    "Compound Score": "An overall sentiment score from -1.0 to +1.0 combining positive, negative, and neutral tones. Above +0.05 is positive, below -0.05 is negative.",
    "Negative Ratio": "The proportion of analyzed news articles that have a negative sentiment. A ratio of 0.7 means 70% of articles are negative.",
    "Sector Impact": "How much current geopolitical events are expected to affect a specific market sector (e.g., energy is highly sensitive to conflicts in oil-producing regions).",
    "Conflict Monitor": "A real-time tracker of major global conflicts, measuring their intensity and potential market impact based on news volume and sentiment.",

    # Trading
    "Buy Order": "An instruction to purchase a specified number of shares of a stock.",
    "Sell Order": "An instruction to sell a specified number of shares you currently hold.",
    "Market Order": "An order to buy or sell immediately at the current market price. Executes fast but you can't control the exact price.",
    "Limit Order": "An order to buy or sell only at a specific price or better. You control the price, but it may not execute if the market doesn't reach your price.",
    "Commission": "A small fee charged per trade, calculated as a percentage of the trade value. This is the cost of executing a transaction.",
    "Open Orders": "Limit orders that have been placed but not yet filled because the stock hasn't reached the specified limit price.",

    # Backtesting & Strategy
    "Strategy Return": "The total percentage gain or loss your trading strategy produced during the backtest period.",
    "Benchmark (SPY)": "S&P 500 ETF used as a comparison baseline. If your strategy beats this, it outperformed the overall market.",
    "Sharpe Ratio": "Measures risk-adjusted return. Higher is better. Above 1.0 is good, above 2.0 is very good. It tells you how much return you get per unit of risk.",
    "Max Drawdown": "The largest peak-to-trough drop in portfolio value during the test. A drawdown of 20% means at worst your portfolio fell 20% from its highest point.",
    "Win Rate": "The percentage of trades that were profitable. A 60% win rate means 6 out of 10 trades made money.",
    "Momentum Strategy": "A strategy that buys stocks whose prices are trending upward (above their recent average) and sells when the trend reverses downward.",
    "Mean Reversion Strategy": "A strategy based on the idea that prices tend to return to their average. Buys when price drops significantly below average, sells when it rises above.",
    "Defensive Strategy": "A strategy activated during high geopolitical risk that sells volatile growth stocks and rotates into safer sectors like healthcare and utilities.",

    # Market Indices
    "S&P 500": "An index tracking the 500 largest U.S. companies. It's the most common benchmark for overall U.S. stock market performance.",
    "NASDAQ": "An index heavily weighted toward technology companies. Includes Apple, Microsoft, Google, Amazon, etc.",
    "DOW": "Dow Jones Industrial Average. Tracks 30 large U.S. blue-chip companies. One of the oldest and most-watched market indicators.",
    "VIX": "The 'Fear Index'. Measures expected market volatility. High VIX (> 30) means investors are fearful; low VIX (< 15) means calm markets.",
    "Russell 2000": "An index tracking 2,000 small-cap U.S. companies. A gauge of how smaller, more domestic-focused businesses are performing.",
}


def tip(term: str) -> str:
    """Return the glossary definition for a term, or empty string if unknown."""
    return TERMS.get(term, "")
