"""
Main entry point for running the AI Stock Trading Agent.
Supports three modes: dashboard, agent-only, and MCP servers.
"""
import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_dashboard():
    import subprocess
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "dashboard/app.py",
        "--server.port", "8501",
    ])


def run_agent():
    from agent.trading_agent import TradingAgent
    from simulator.paper_trading import PaperTradingEngine
    from mcp_servers.trade_server import set_engine

    engine = PaperTradingEngine()
    set_engine(engine)
    agent = TradingAgent()

    logger.info("Starting AI Trading Agent in interactive mode...")
    print("\n" + "=" * 60)
    print("  AI Stock Trading Agent - Interactive Mode")
    print("  Type 'analyze' to run a full analysis cycle")
    print("  Type 'portfolio' to view your portfolio")
    print("  Type 'quit' to exit")
    print("  Or type any question to chat with the AI")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() == "quit":
                break
            elif user_input.lower() == "analyze":
                print("\nRunning full analysis cycle...")
                result = agent.run_analysis()
                print(f"\nRisk Score: {result['risk_score']}")
                print(f"Reasoning:\n{result['reasoning']}")
                balance = result["balance_after"]
                print(f"\nPortfolio: ${balance['total_value']:,.2f} (Return: {balance['total_return_pct']:+.2f}%)")
            elif user_input.lower() == "portfolio":
                balance = engine.get_account_balance()
                portfolio = engine.get_portfolio()
                print(f"\nCash: ${balance['cash']:,.2f}")
                print(f"Positions: ${balance['positions_value']:,.2f}")
                print(f"Total: ${balance['total_value']:,.2f}")
                print(f"Return: {balance['total_return_pct']:+.2f}%")
                if portfolio.get("positions"):
                    print("\nPositions:")
                    for sym, pos in portfolio["positions"].items():
                        print(f"  {sym}: {pos['quantity']} shares @ ${pos['current_price']:.2f} "
                              f"(P&L: ${pos['unrealized_pnl']:.2f})")
            else:
                response = agent.chat(user_input)
                print(f"\nAgent: {response}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

    print("\nGoodbye!")


def run_mcp_servers():
    """Run all three MCP servers (for standalone deployment)."""
    import subprocess
    import time

    servers = [
        ("Financial Data", "mcp_servers/financial_data_server.py"),
        ("Geopolitical", "mcp_servers/geopolitical_server.py"),
        ("Trade", "mcp_servers/trade_server.py"),
        ("Banking", "mcp_servers/banking_server.py"),
        ("Price Alerts", "mcp_servers/price_alert_server.py"),
        ("Watchlist", "mcp_servers/watchlist_server.py"),
        ("Pattern Scanner", "mcp_servers/pattern_scanner_server.py"),
        ("Risk Metrics", "mcp_servers/risk_metrics_server.py"),
    ]

    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(".")
    
    processes = []
    for name, path in servers:
        logger.info(f"Starting {name} MCP Server...")
        proc = subprocess.Popen([sys.executable, path], env=env)
        processes.append(proc)
        time.sleep(1)

    logger.info("All MCP servers running. Press Ctrl+C to stop.")
    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        for proc in processes:
            proc.terminate()
        logger.info("All servers stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Stock Trading Agent")
    parser.add_argument(
        "mode",
        choices=["dashboard", "agent", "servers"],
        default="dashboard",
        nargs="?",
        help="Run mode: 'dashboard' (web UI), 'agent' (interactive CLI), 'servers' (MCP servers only)",
    )
    args = parser.parse_args()

    if args.mode == "dashboard":
        run_dashboard()
    elif args.mode == "agent":
        run_agent()
    elif args.mode == "servers":
        run_mcp_servers()
