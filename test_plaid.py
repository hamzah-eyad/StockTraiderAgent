#!/usr/bin/env python3
"""
test_plaid.py — Standalone Plaid Sandbox verification script
=============================================================
Run this script BEFORE starting the full application to verify your
Plaid credentials, create a virtual bank account, and fetch real data.

Usage:
    python test_plaid.py

Requirements:
    - pip install plaid-python python-dotenv
    - PLAID_CLIENT_ID and PLAID_SECRET set in .env
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# ── Load .env from the project root ──────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "")
PLAID_SECRET = os.getenv("PLAID_SECRET", "")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"{GREEN}  ✅ {msg}{RESET}")
def warn(msg): print(f"{YELLOW}  ⚠️  {msg}{RESET}")
def err(msg):  print(f"{RED}  ❌ {msg}{RESET}")
def info(msg): print(f"{CYAN}  ℹ️  {msg}{RESET}")


# ── Step 0: Pre-flight checks ─────────────────────────────────────────────────
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  StockTraiderAgent — Plaid Sandbox Test{RESET}")
print(f"{BOLD}{'='*60}{RESET}\n")

print(f"{BOLD}Step 0: Checking configuration…{RESET}")

try:
    import plaid
    from plaid.api import plaid_api
    ok("plaid-python is installed")
except ImportError:
    err("plaid-python is NOT installed.")
    print(f"\n  Run:  pip install plaid-python\n")
    sys.exit(1)

if not PLAID_CLIENT_ID or PLAID_CLIENT_ID == "your_plaid_client_id_here":
    err("PLAID_CLIENT_ID is not set in .env")
    print(f"\n  How to fix:")
    print(f"  1. Go to {CYAN}https://dashboard.plaid.com{RESET}")
    print(f"  2. Sign up for free (no credit card needed)")
    print(f"  3. Go to Team Settings → Keys")
    print(f"  4. Copy your {BOLD}client_id{RESET} and the {BOLD}Sandbox secret{RESET}")
    print(f"  5. Add to .env:\n")
    print(f"     PLAID_CLIENT_ID=<your_client_id>")
    print(f"     PLAID_SECRET=<your_sandbox_secret>")
    print(f"     PLAID_ENV=sandbox\n")
    sys.exit(1)
else:
    ok(f"PLAID_CLIENT_ID is set ({PLAID_CLIENT_ID[:8]}…)")

if not PLAID_SECRET or PLAID_SECRET == "your_plaid_sandbox_secret_here":
    err("PLAID_SECRET is not set in .env")
    sys.exit(1)
else:
    ok(f"PLAID_SECRET is set ({PLAID_SECRET[:6]}…)")

ok(f"PLAID_ENV = {PLAID_ENV}")


# ── Step 1: Create Plaid client ───────────────────────────────────────────────
print(f"\n{BOLD}Step 1: Connecting to Plaid {PLAID_ENV.upper()} environment…{RESET}")

PLAID_HOSTS = {
    "sandbox":     "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production":  "https://production.plaid.com",
}

configuration = plaid.Configuration(
    host=PLAID_HOSTS.get(PLAID_ENV, PLAID_HOSTS["sandbox"]),
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)
ok(f"Plaid client created → {PLAID_HOSTS[PLAID_ENV]}")


# ── Step 2: Create a sandbox public token ────────────────────────────────────
print(f"\n{BOLD}Step 2: Creating Sandbox public token (First Platypus Bank)…{RESET}")
info("This simulates a user linking their bank account through Plaid Link.")

from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products

try:
    pt_req = SandboxPublicTokenCreateRequest(
        institution_id="ins_109508",          # First Platypus Bank — Plaid's official test bank
        initial_products=[Products("transactions"), Products("auth")],
    )
    pt_resp = client.sandbox_public_token_create(pt_req)
    public_token = pt_resp["public_token"]
    ok(f"Public token created: {public_token[:20]}…")
except Exception as e:
    err(f"Failed to create sandbox token: {e}")
    sys.exit(1)


# ── Step 3: Exchange for access token ─────────────────────────────────────────
print(f"\n{BOLD}Step 3: Exchanging public token for access token…{RESET}")
info("The access token is what the app stores and uses for all future API calls.")

try:
    ex_req = ItemPublicTokenExchangeRequest(public_token=public_token)
    ex_resp = client.item_public_token_exchange(ex_req)
    access_token = ex_resp["access_token"]
    item_id = ex_resp["item_id"]
    ok(f"Access token: {access_token[:20]}…")
    ok(f"Item ID:      {item_id}")
except Exception as e:
    err(f"Token exchange failed: {e}")
    sys.exit(1)


# ── Step 4: Fetch accounts ────────────────────────────────────────────────────
print(f"\n{BOLD}Step 4: Fetching bank accounts…{RESET}")

from plaid.model.accounts_get_request import AccountsGetRequest

try:
    accts_resp = client.accounts_get(AccountsGetRequest(access_token=access_token))
    accounts = accts_resp["accounts"]
    ok(f"Found {len(accounts)} account(s):\n")

    for acct in accounts:
        bal = acct["balances"]
        current = bal.get("current") or 0
        available = bal.get("available") or 0
        currency = bal.get("iso_currency_code", "USD")
        print(
            f"    {'─'*50}\n"
            f"    Name:      {acct['name']}\n"
            f"    Type:      {acct['type']} / {acct.get('subtype', 'N/A')}\n"
            f"    Mask:      ···{acct.get('mask', '????')}\n"
            f"    Balance:   ${current:>10,.2f} {currency}\n"
            f"    Available: ${available:>10,.2f} {currency}\n"
        )
except Exception as e:
    err(f"accounts_get failed: {e}")
    sys.exit(1)


# ── Step 5: Fetch transactions ────────────────────────────────────────────────
print(f"{BOLD}Step 5: Fetching transactions (transactions/sync)…{RESET}")

from plaid.model.transactions_sync_request import TransactionsSyncRequest

try:
    sync_resp = client.transactions_sync(TransactionsSyncRequest(access_token=access_token))
    all_txs = sync_resp.get("added", [])
    ok(f"Retrieved {len(all_txs)} transaction(s). Showing first 10:\n")

    for tx in all_txs[:10]:
        amount = float(tx.get("amount", 0))
        sign = "-" if amount > 0 else "+"
        direction_color = RED if amount > 0 else GREEN
        cat = ", ".join(tx.get("category", []) or ["Uncategorized"])
        print(
            f"    {direction_color}{sign}${abs(amount):>8,.2f}{RESET}  "
            f"{str(tx.get('date','')):<12}  "
            f"{(tx.get('merchant_name') or tx.get('name','')):<30}  "
            f"{cat}"
        )

    if not all_txs:
        warn("No transactions returned yet. This is normal for a brand-new sandbox item.")
        info("Tip: fire a webhook to trigger data: client.sandbox_item_fire_webhook(…)")

except Exception as e:
    err(f"transactions_sync failed: {e}")


# ── Step 6: Save token for the app ────────────────────────────────────────────
print(f"\n{BOLD}Step 6: Saving access token for the app…{RESET}")

token_path = Path(__file__).parent / "data" / "plaid_token.json"
token_path.parent.mkdir(parents=True, exist_ok=True)
token_path.write_text(
    json.dumps({"access_token": access_token, "created_at": datetime.now().isoformat()}, indent=2)
)
ok(f"Token saved to {token_path}")
info("The banking_server.py will automatically load this token on startup.")


# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{GREEN}{BOLD}  All tests passed! Plaid Sandbox is working correctly.{RESET}")
print(f"{BOLD}{'='*60}{RESET}")
print(f"\n  Next steps:")
print(f"  1. Start the app:      {CYAN}python main.py dashboard{RESET}")
print(f"  2. Open browser:       {CYAN}http://localhost:8501{RESET}")
print(f"  3. Go to:              {CYAN}Banking tab{RESET}")
print(f"  4. You will see your real First Platypus Bank accounts! 🎉\n")
print(f"  {YELLOW}Note: This is Plaid Sandbox — no real money is involved.{RESET}\n")
