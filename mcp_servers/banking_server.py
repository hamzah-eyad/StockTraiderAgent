"""
MCP Server 4: Real Open Banking via Plaid
------------------------------------------
Supports two modes:
  • Sandbox Demo   — auto-connects to "First Platypus Bank" (no credentials needed beyond API keys)
  • Real Bank Link — user links their own bank via Plaid Link; token saved to data/plaid_real_tokens.json

Fallback: If PLAID_CLIENT_ID / PLAID_SECRET are not set in .env, the server uses
locally stored simulated data with a clear warning.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from config import (
    DATA_DIR,
    PLAID_CLIENT_ID,
    PLAID_SECRET,
    PLAID_ENV,
    PLAID_TOKEN_CACHE,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("Open Banking Server (Plaid)", host="0.0.0.0", port=8006)

# ── Plaid environment mapping ─────────────────────────────────────────────────
_PLAID_HOSTS = {
    "sandbox":     "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production":  "https://production.plaid.com",
}

# Plaid's official sandbox test institution (First Platypus Bank)
_SANDBOX_INSTITUTION_ID = "ins_109508"

# Storage for user-linked real bank tokens
PLAID_REAL_TOKENS_PATH = DATA_DIR / "plaid_real_tokens.json"


# ── Plaid client factory ──────────────────────────────────────────────────────
def _is_plaid_configured() -> bool:
    return bool(PLAID_CLIENT_ID and PLAID_SECRET)


def _get_plaid_client():
    """Return an authenticated Plaid API client, or None if not configured."""
    if not _is_plaid_configured():
        return None
    try:
        import plaid
        from plaid.api import plaid_api

        configuration = plaid.Configuration(
            host=_PLAID_HOSTS.get(PLAID_ENV.lower(), _PLAID_HOSTS["sandbox"]),
            api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
        )
        return plaid_api.PlaidApi(plaid.ApiClient(configuration))
    except ImportError:
        logger.error("plaid-python not installed. Run: pip install plaid-python")
        return None
    except Exception as e:
        logger.error(f"Failed to create Plaid client: {e}")
        return None


# ── Sandbox token management ──────────────────────────────────────────────────
def _load_sandbox_token() -> Optional[str]:
    if PLAID_TOKEN_CACHE.exists():
        try:
            data = json.loads(PLAID_TOKEN_CACHE.read_text())
            token = data.get("access_token")
            if token:
                return token
        except Exception:
            pass
    return None


def _save_sandbox_token(access_token: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    PLAID_TOKEN_CACHE.write_text(
        json.dumps({"access_token": access_token, "created_at": datetime.now().isoformat()})
    )


def _create_sandbox_token(client) -> Optional[str]:
    """Auto-create a Plaid Sandbox token for First Platypus Bank."""
    try:
        from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
        from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
        from plaid.model.products import Products

        pt_req = SandboxPublicTokenCreateRequest(
            institution_id=_SANDBOX_INSTITUTION_ID,
            initial_products=[Products("transactions"), Products("auth")],
        )
        pt_resp = client.sandbox_public_token_create(pt_req)
        ex_req = ItemPublicTokenExchangeRequest(public_token=pt_resp["public_token"])
        ex_resp = client.item_public_token_exchange(ex_req)
        access_token = ex_resp["access_token"]
        _save_sandbox_token(access_token)
        logger.info("Plaid Sandbox token created ✅")
        return access_token
    except Exception as e:
        logger.error(f"Failed to create Plaid sandbox token: {e}")
        return None


def _get_sandbox_token(client) -> Optional[str]:
    token = _load_sandbox_token()
    if not token:
        token = _create_sandbox_token(client)
    return token


# ── Real bank token management ────────────────────────────────────────────────
def _load_real_bank_tokens() -> list[dict]:
    """Load all user-linked real bank tokens from disk."""
    if PLAID_REAL_TOKENS_PATH.exists():
        try:
            return json.loads(PLAID_REAL_TOKENS_PATH.read_text()).get("items", [])
        except Exception:
            pass
    return []


def _save_real_bank_tokens(items: list[dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    PLAID_REAL_TOKENS_PATH.write_text(json.dumps({"items": items}, indent=2))


def exchange_and_save_real_token(public_token: str, institution_name: str = "Unknown Bank") -> dict:
    """
    Exchange a Plaid public_token for an access_token and save it.
    Called by the Plaid Link callback server after user links a bank.
    Returns a dict (not JSON string) for direct use by callers.
    """
    client = _get_plaid_client()
    if not client:
        return {"status": "error", "error": "Plaid not configured"}
    try:
        from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

        ex_req = ItemPublicTokenExchangeRequest(public_token=public_token)
        ex_resp = client.item_public_token_exchange(ex_req)
        access_token = ex_resp["access_token"]
        item_id = ex_resp["item_id"]

        items = _load_real_bank_tokens()
        if not any(i["item_id"] == item_id for i in items):
            items.append({
                "access_token": access_token,
                "item_id": item_id,
                "institution_name": institution_name,
                "linked_at": datetime.now().isoformat(),
            })
            _save_real_bank_tokens(items)

        logger.info(f"Real bank linked: {institution_name} ({item_id})")
        return {
            "status": "success",
            "item_id": item_id,
            "institution_name": institution_name,
            "message": f"'{institution_name}' linked successfully!",
        }
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return {"status": "error", "error": str(e)}


def _fetch_accounts_for_token(client, access_token: str, institution_name: str = "Bank") -> list[dict]:
    """Fetch accounts for a single access_token."""
    from plaid.model.accounts_get_request import AccountsGetRequest
    resp = client.accounts_get(AccountsGetRequest(access_token=access_token))
    accounts = []
    for acct in resp["accounts"]:
        bal = acct["balances"]
        accounts.append({
            "id": acct["account_id"],
            "name": acct["name"],
            "type": str(acct["type"]),
            "subtype": str(acct.get("subtype", "")),
            "balance": float(bal.get("current") or 0),
            "available": float(bal.get("available") or 0),
            "currency": bal.get("iso_currency_code", "USD"),
            "mask": acct.get("mask", "****"),
            "institution": institution_name,
        })
    return accounts


def _fetch_transactions_for_token(client, access_token: str, cursor_key: str, limit: int = 20) -> list[dict]:
    """Fetch transactions for a single access_token using transactions/sync."""
    from plaid.model.transactions_sync_request import TransactionsSyncRequest

    cursor_file = DATA_DIR / f"plaid_cursor_{cursor_key}.txt"
    cursor = cursor_file.read_text().strip() if cursor_file.exists() else None

    req_kwargs: dict = {"access_token": access_token}
    if cursor:
        req_kwargs["cursor"] = cursor

    resp = client.transactions_sync(TransactionsSyncRequest(**req_kwargs))
    next_cursor = resp.get("next_cursor")
    if next_cursor:
        os.makedirs(DATA_DIR, exist_ok=True)
        cursor_file.write_text(next_cursor)

    txs = []
    for tx in resp.get("added", []):
        amount_raw = float(tx.get("amount", 0))
        txs.append({
            "id": tx["transaction_id"],
            "account_id": tx["account_id"],
            "amount": -amount_raw,
            "description": tx.get("name", "Unknown"),
            "merchant": tx.get("merchant_name") or tx.get("name", ""),
            "category": ", ".join(tx.get("category", []) or ["Uncategorized"]),
            "date": str(tx.get("date", "")),
            "pending": tx.get("pending", False),
        })
    return txs[:limit]


# ── Fallback simulation ───────────────────────────────────────────────────────
_FALLBACK_STORAGE = DATA_DIR / "banking_fallback.json"


def _load_fallback_data() -> dict:
    if not _FALLBACK_STORAGE.exists():
        data = {
            "accounts": [
                {"id": "abc_123", "name": "Personal Checking (Simulated)", "type": "checking",
                 "balance": 250000.0, "currency": "USD", "institution": "Demo Bank", "mask": "0000"},
                {"id": "sav_456", "name": "High-Yield Savings (Simulated)", "type": "savings",
                 "balance": 150000.0, "currency": "USD", "institution": "Demo Bank", "mask": "0001"},
            ],
            "transactions": [
                {"id": "tx_001", "account_id": "abc_123", "amount": -45.50,
                 "description": "Starbucks Coffee", "category": "Food & Drink",
                 "date": (datetime.now() - timedelta(hours=2)).isoformat()},
                {"id": "tx_002", "account_id": "abc_123", "amount": 5000.0,
                 "description": "Monthly Salary", "category": "Income",
                 "date": (datetime.now() - timedelta(days=1)).isoformat()},
            ],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        _FALLBACK_STORAGE.write_text(json.dumps(data, indent=4))
        return data
    return json.loads(_FALLBACK_STORAGE.read_text())


def _save_fallback_data(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    _FALLBACK_STORAGE.write_text(json.dumps(data, indent=4))


# ── MCP Tools: Sandbox Mode ───────────────────────────────────────────────────
@mcp.tool()
def get_bank_accounts() -> str:
    """Get sandbox bank accounts (First Platypus Bank). Falls back to simulation if unconfigured."""
    client = _get_plaid_client()
    if client:
        try:
            token = _get_sandbox_token(client)
            if not token:
                raise RuntimeError("Could not obtain sandbox token")
            accounts = _fetch_accounts_for_token(client, token, "First Platypus Bank")
            for a in accounts:
                a["source"] = "plaid_sandbox"
            return json.dumps({"accounts": accounts, "source": "plaid_sandbox", "plaid_env": PLAID_ENV})
        except Exception as e:
            logger.warning(f"Sandbox accounts_get failed: {e}")
            if PLAID_TOKEN_CACHE.exists():
                PLAID_TOKEN_CACHE.unlink()

    data = _load_fallback_data()
    return json.dumps({"accounts": data["accounts"], "source": "simulation",
                       "warning": "Plaid not configured — showing simulated data."})


@mcp.tool()
def get_bank_transactions(account_id: str | None = None, limit: int = 20) -> str:
    """Get sandbox bank transactions. Falls back to simulation if unconfigured."""
    client = _get_plaid_client()
    if client:
        try:
            token = _get_sandbox_token(client)
            if not token:
                raise RuntimeError("Could not obtain sandbox token")
            txs = _fetch_transactions_for_token(client, token, "sandbox", limit)
            if account_id:
                txs = [t for t in txs if t["account_id"] == account_id]
            for t in txs:
                t["source"] = "plaid_sandbox"
            return json.dumps({"transactions": txs, "source": "plaid_sandbox"})
        except Exception as e:
            logger.warning(f"Sandbox transactions failed: {e}")
            if PLAID_TOKEN_CACHE.exists():
                PLAID_TOKEN_CACHE.unlink()

    data = _load_fallback_data()
    txs = data["transactions"]
    if account_id:
        txs = [t for t in txs if t["account_id"] == account_id]
    return json.dumps({"transactions": txs[:limit], "source": "simulation",
                       "warning": "Plaid not configured — showing simulated data."})


# ── MCP Tools: Real Bank Mode ─────────────────────────────────────────────────
@mcp.tool()
def create_plaid_link_token() -> str:
    """
    Generate a Plaid link_token needed to open the Plaid Link flow in the browser.
    The user will use this token to link their own real bank account.
    """
    client = _get_plaid_client()
    if not client:
        return json.dumps({"error": "Plaid credentials not configured. Set PLAID_CLIENT_ID and PLAID_SECRET in .env"})
    try:
        from plaid.model.link_token_create_request import LinkTokenCreateRequest
        from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
        from plaid.model.country_code import CountryCode
        from plaid.model.products import Products

        req = LinkTokenCreateRequest(
            products=[Products("transactions"), Products("auth")],
            client_name="StockTraiderAgent",
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="stock-trader-user-001"),
        )
        resp = client.link_token_create(req)
        return json.dumps({"link_token": resp["link_token"], "expiration": str(resp.get("expiration", ""))})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_linked_real_banks() -> str:
    """Return a list of all user-linked real bank institutions (no tokens exposed)."""
    items = _load_real_bank_tokens()
    safe = [{"item_id": i["item_id"], "institution_name": i["institution_name"],
              "linked_at": i["linked_at"]} for i in items]
    return json.dumps({"banks": safe, "count": len(safe)})


@mcp.tool()
def get_real_bank_accounts() -> str:
    """Fetch accounts from all user-linked real banks (via Plaid Link)."""
    client = _get_plaid_client()
    if not client:
        return json.dumps({"error": "Plaid not configured"})

    items = _load_real_bank_tokens()
    if not items:
        return json.dumps({"accounts": [], "message": "No real banks linked yet. Use Plaid Link to connect your bank."})

    all_accounts = []
    errors = []
    for item in items:
        try:
            accounts = _fetch_accounts_for_token(client, item["access_token"], item["institution_name"])
            for a in accounts:
                a["source"] = "plaid_real"
                a["item_id"] = item["item_id"]
            all_accounts.extend(accounts)
        except Exception as e:
            errors.append({"item_id": item["item_id"], "institution": item["institution_name"], "error": str(e)})

    return json.dumps({"accounts": all_accounts, "source": "plaid_real", "errors": errors})


@mcp.tool()
def get_real_bank_transactions(limit: int = 20) -> str:
    """Fetch recent transactions from all user-linked real banks."""
    client = _get_plaid_client()
    if not client:
        return json.dumps({"error": "Plaid not configured"})

    items = _load_real_bank_tokens()
    if not items:
        return json.dumps({"transactions": [], "message": "No real banks linked yet."})

    all_txs = []
    for item in items:
        try:
            cursor_key = item["item_id"].replace("-", "_")[:20]
            txs = _fetch_transactions_for_token(client, item["access_token"], cursor_key, limit)
            for t in txs:
                t["source"] = "plaid_real"
                t["institution"] = item["institution_name"]
            all_txs.extend(txs)
        except Exception as e:
            logger.warning(f"Transactions failed for {item['institution_name']}: {e}")

    all_txs.sort(key=lambda t: t.get("date", ""), reverse=True)
    return json.dumps({"transactions": all_txs[:limit], "source": "plaid_real"})


@mcp.tool()
def remove_linked_bank(item_id: str) -> str:
    """Remove a previously linked real bank account."""
    items = _load_real_bank_tokens()
    original_len = len(items)
    items = [i for i in items if i["item_id"] != item_id]
    if len(items) == original_len:
        return json.dumps({"status": "not_found", "error": f"No bank with item_id '{item_id}'"})
    _save_real_bank_tokens(items)
    return json.dumps({"status": "success", "message": f"Bank {item_id} removed.", "remaining": len(items)})


# ── MCP Tools: Transfer & Utility ─────────────────────────────────────────────
@mcp.tool()
def initiate_brokerage_transfer(amount: float, account_id: str) -> str:
    """
    Transfer funds from a linked bank account to the brokerage account.
    Validates against live Plaid balance. No real money moves in sandbox.
    """
    client = _get_plaid_client()
    if client:
        try:
            # Check sandbox accounts first, then real bank accounts
            all_accounts = []
            sb_raw = json.loads(get_bank_accounts())
            all_accounts.extend(sb_raw.get("accounts", []))
            rb_raw = json.loads(get_real_bank_accounts())
            all_accounts.extend(rb_raw.get("accounts", []))

            account = next((a for a in all_accounts if a["id"] == account_id), None)
            if not account:
                return json.dumps({"error": f"Account {account_id} not found"})

            available = account.get("available") or account.get("balance", 0)
            if available < amount:
                return json.dumps({"error": f"Insufficient funds. Available: ${available:,.2f}, Requested: ${amount:,.2f}"})

            transfer_log = DATA_DIR / "plaid_transfers.json"
            os.makedirs(DATA_DIR, exist_ok=True)
            log = json.loads(transfer_log.read_text()) if transfer_log.exists() else {"transfers": []}
            log["transfers"].insert(0, {
                "id": f"xfr_{int(datetime.now().timestamp())}",
                "account_id": account_id,
                "account_name": account["name"],
                "institution": account.get("institution", ""),
                "amount": amount,
                "timestamp": datetime.now().isoformat(),
                "status": "completed",
                "source": account.get("source", "plaid"),
            })
            transfer_log.write_text(json.dumps(log, indent=4))

            return json.dumps({
                "status": "success",
                "amount": amount,
                "account_name": account["name"],
                "institution": account.get("institution", ""),
                "available_after": max(0, available - amount),
                "note": "Sandbox: no real money moved." if "sandbox" in account.get("source", "") else "Transfer recorded.",
            })
        except Exception as e:
            logger.warning(f"Transfer validation failed, using fallback: {e}")

    # Fallback
    data = _load_fallback_data()
    account = next((a for a in data["accounts"] if a["id"] == account_id), None)
    if not account:
        return json.dumps({"error": f"Account {account_id} not found"})
    if account["balance"] < amount:
        return json.dumps({"error": "Insufficient funds"})
    account["balance"] -= amount
    data["transactions"].insert(0, {"id": f"tx_{int(datetime.now().timestamp())}",
                                     "account_id": account_id, "amount": -amount,
                                     "description": "Transfer to Brokerage",
                                     "category": "Transfer", "date": datetime.now().isoformat()})
    _save_fallback_data(data)
    return json.dumps({"status": "success", "amount": amount, "new_bank_balance": account["balance"],
                       "account_name": account["name"], "source": "simulation"})


@mcp.tool()
def refresh_plaid_connection() -> str:
    """Reset the sandbox Plaid token and cursor so fresh data is fetched."""
    deleted = []
    for f in [PLAID_TOKEN_CACHE, DATA_DIR / "plaid_cursor_sandbox.txt"]:
        if f.exists():
            f.unlink()
            deleted.append(f.name)

    if not _is_plaid_configured():
        return json.dumps({"status": "skipped", "message": "Plaid not configured."})

    client = _get_plaid_client()
    new_token = _create_sandbox_token(client) if client else None
    return json.dumps({
        "status": "success" if new_token else "failed",
        "cleared_files": deleted,
        "new_token_created": bool(new_token),
        "message": "Sandbox connection refreshed." if new_token else "Token creation failed.",
    })


@mcp.tool()
def get_plaid_connection_status() -> str:
    """Return full connection status: config, sandbox token, and linked real banks."""
    configured = _is_plaid_configured()
    real_items = _load_real_bank_tokens()
    return json.dumps({
        "configured": configured,
        "plaid_env": PLAID_ENV,
        "sandbox_token_cached": PLAID_TOKEN_CACHE.exists(),
        "real_banks_linked": len(real_items),
        "real_banks": [{"institution": i["institution_name"], "item_id": i["item_id"], "linked_at": i["linked_at"]}
                       for i in real_items],
        "source": "plaid" if configured else "simulation",
        "message": "✅ Plaid configured." if configured else "⚠️ Add PLAID_CLIENT_ID + PLAID_SECRET to .env",
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
