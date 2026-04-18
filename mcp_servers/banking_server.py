"""
MCP Server 4: Simulated Open Banking Server
Provides tools to check bank balances, view transactions, and fund trading accounts.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from config import DATA_DIR

logger = logging.getLogger(__name__)

mcp = FastMCP("Simulated Open Banking Server", host="0.0.0.0", port=8006)

BANK_STORAGE_PATH = DATA_DIR / "banking.json"

def _load_bank_data() -> dict:
    if not BANK_STORAGE_PATH.exists():
        # Default starting state
        data = {
            "accounts": [
                {
                    "id": "abc_123",
                    "name": "Personal Checking",
                    "type": "checking",
                    "balance": 250000.0,
                    "currency": "USD"
                },
                {
                    "id": "sav_456",
                    "name": "High-Yield Savings",
                    "type": "savings",
                    "balance": 150000.0,
                    "currency": "USD"
                }
            ],
            "transactions": [
                {
                    "id": "tx_001",
                    "account_id": "abc_123",
                    "amount": -45.50,
                    "description": "Starbucks Coffee",
                    "category": "Food & Drink",
                    "date": (datetime.now() - timedelta(hours=2)).isoformat()
                },
                {
                    "id": "tx_002",
                    "account_id": "abc_123",
                    "amount": 5000.0,
                    "description": "Monthly Salary",
                    "category": "Income",
                    "date": (datetime.now() - timedelta(days=1)).isoformat()
                }
            ]
        }
        _save_bank_data(data)
        return data
    
    with open(BANK_STORAGE_PATH, "r") as f:
        return json.load(f)

def _save_bank_data(data: dict):
    os.makedirs(os.path.dirname(BANK_STORAGE_PATH), exist_ok=True)
    with open(BANK_STORAGE_PATH, "w") as f:
        json.dump(data, f, indent=4)

@mcp.tool()
def get_bank_accounts() -> str:
    """Get all linked bank accounts and their current balances."""
    data = _load_bank_data()
    return json.dumps({"accounts": data["accounts"]})

@mcp.tool()
def get_bank_transactions(account_id: str | None = None, limit: int = 10) -> str:
    """Get recent transactions for a specific account or all accounts."""
    data = _load_bank_data()
    txs = data["transactions"]
    if account_id:
        txs = [t for t in txs if t["account_id"] == account_id]
    
    return json.dumps({"transactions": txs[:limit]})

@mcp.tool()
def initiate_brokerage_transfer(amount: float, account_id: str) -> str:
    """
    Transfer funds from a bank account to the brokerage account.
    Returns success status and new bank balance.
    """
    data = _load_bank_data()
    account = next((a for a in data["accounts"] if a["id"] == account_id), None)
    
    if not account:
        return json.dumps({"error": f"Account {account_id} not found"})
    
    if account["balance"] < amount:
        return json.dumps({"error": "Insufficient funds in bank account"})
    
    # Deduct from bank
    account["balance"] -= amount
    
    # Add to transaction history
    new_tx = {
        "id": f"tx_{int(datetime.now().timestamp())}",
        "account_id": account_id,
        "amount": -amount,
        "description": "Transfer to Brokerage",
        "category": "Transfer",
        "date": datetime.now().isoformat()
    }
    data["transactions"].insert(0, new_tx)
    _save_bank_data(data)

    # Note: In a real implementation, this would call TradeServer.add_cash()
    # For this prototype, we'll let the agent or dashboard handle the peer update.
    
    return json.dumps({
        "status": "success",
        "amount": amount,
        "new_bank_balance": account["balance"],
        "account_name": account["name"]
    })

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
