# Open Banking & Plaid — Complete Guide

> Written for the StockTraiderAgent project. Plain English — no jargon.
> Covers everything built in this integration from start to finish.

---

## 1. What is "Banking" in the traditional sense?

When you have money in a bank (e.g., Al Rajhi, SNB, Chase, Wise), that bank knows
everything about you:

- Your account balance
- Every transaction you've ever made
- What type of account you have (savings, checking, credit card...)

But historically, **that data was locked inside the bank**. You could see it on their
app or website, but no other app could access it — even if you wanted them to.

---

## 2. What is Open Banking?

**Open Banking** is a system where banks are required (or allowed) to **share your
financial data with other apps** — but only with your explicit permission.

> 🏦 **Old way:** Your bank data is like a book locked in a safe. Only the bank can read it.
>
> 🔓 **Open Banking:** You give a trusted app a key to that safe. The app can now
> read your balance, see your transactions, or even move money — but only because
> YOU said it was okay.

**Real examples of apps using Open Banking:**
- **Mint / YNAB** — reads your bank transactions to help you budget
- **Robinhood / Trading 212** — reads your bank balance to fund your trading account
- **Wise / Revolut** — moves money between banks on your behalf

---

## 3. What is Plaid?

**Plaid is a company that acts as the bridge between your bank and any app.**

Instead of every app having to build a separate connection to every bank (thousands
of custom integrations), Plaid has already done that work.

```
Your App  ──→  Plaid  ──→  Bank of America
                      ──→  Chase
                      ──→  Wise
                      ──→  HSBC
                      ──→  + 12,000 more banks worldwide
```

**Who uses Plaid in the real world?**

| Company | What they use Plaid for |
|---|---|
| Venmo | Linking your bank to send money |
| Robinhood | Funding your brokerage account |
| Coinbase | Buying crypto with your bank balance |
| American Express | Viewing all accounts in one place |

---

## 4. Why did we choose Plaid specifically?

| Reason | Details |
|---|---|
| **Official Python SDK** | `plaid-python` — no manual HTTP calls |
| **Free Sandbox** | No credit card, no approval, instant access |
| **Self-contained** | Works fully locally, no ngrok or redirect server needed |
| **No user login required for sandbox** | Token auto-created in code |
| **Industry standard** | Used by 8,000+ real companies |
| **Rich test data** | 12 account types + 340+ realistic transactions |

---

## 5. What is a "Sandbox"?

A **Sandbox** is a fake, safe version of a real system — used for testing.

> 🏖️ Like a children's sandbox — you can build anything, break anything, and
> nothing real gets hurt.

Plaid's Sandbox is a **fake bank that runs on real API infrastructure**.

When you use it:
- You connect to a fake bank called **"First Platypus Bank"**
- It gives you fake accounts (Plaid Checking, Plaid Saving, Plaid Credit Card...)
- It gives you fake transaction history (Uber, Starbucks, Amazon...)
- The data looks and behaves **exactly like real bank data**
- But **no real money exists or moves**

---

## 6. How the Plaid connection works (Token Lifecycle)

Plaid uses a 3-step process to link a bank account:

```
┌──────────────────────────────────────────────────────────┐
│  Step 1 — Create a link_token (for user-facing linking)  │
│  link_token_create() → link_token (used to open Plaid UI)│
│                                                          │
│  Step 2 — User goes through Plaid Link UI                │
│  (picks bank, enters credentials on Plaid's servers)     │
│  → Plaid calls onSuccess(public_token)                   │
│                                                          │
│  Step 3 — Exchange public_token → access_token           │
│  item_public_token_exchange() → access_token  💾 saved  │
│                                                          │
│  All future requests use access_token:                   │
│  accounts_get(access_token)    → balances                │
│  transactions_sync(access_token) → transactions          │
└──────────────────────────────────────────────────────────┘
```

---

## 7. Plaid Sandbox Test Credentials

When linking a bank in Sandbox mode, Plaid always shows a mock login page
("First Platypus Bank") regardless of which bank you search for.

**This is expected behaviour — it is not a bug.**

Use these credentials at every step:

| Step | Field | What to enter |
|---|---|---|
| Login | Username | `user_good` |
| Login | Password | `pass_good` |
| MFA / SMS verification | Any code prompt | `1234` |

These work for every institution, every time, in Plaid Sandbox.

---

## 8. What we built in this project

### Architecture Overview

```
StockTraiderAgent/
├── mcp_servers/
│   └── banking_server.py        ← Plaid API calls + MCP tools
├── dashboard/
│   ├── views/banking.py         ← Two-mode UI (Sandbox + Real Bank tabs)
│   └── plaid_link_server.py     ← Local HTTP server (port 8508)
├── config.py                    ← PLAID_* constants
├── .env                         ← Your Plaid credentials
├── data/
│   ├── plaid_token.json         ← Cached sandbox access token
│   ├── plaid_real_tokens.json   ← User-linked real bank tokens
│   └── plaid_transfers.json     ← Transfer history log
└── test_plaid.py                ← Standalone CLI connection test
```

### Two Dashboard Modes

#### 🏖️ Tab 1 — Sandbox Demo
- Auto-connects to First Platypus Bank on first load
- Shows 12 pre-built virtual accounts
- Shows 340+ realistic sandbox transactions
- Transfer button moves sandbox money to the brokerage account
- "Reset Token" button re-creates the connection for demos

#### 🏦 Tab 2 — Link Your Real Bank
- User clicks **Generate Plaid Link Session**
- A `link_token` is created via the Plaid API
- A new browser tab opens with the Plaid Link page (served by the local HTTP server)
- User searches for their bank and logs in (credentials go to Plaid's servers only)
- On success, the Plaid JS sends a `public_token` to the local server (port 8508)
- The local server exchanges it for an `access_token` and saves it to disk
- User returns to the dashboard and clicks **Refresh Linked Banks**
- Real account balances and transactions appear
- Multiple banks can be linked; each has an Unlink button

### Why the local HTTP server (port 8508)?

Plaid Link (their JavaScript SDK) **cannot run inside an iframe** — this is an
explicit Plaid restriction. Streamlit renders custom HTML inside iframes, so we
cannot embed Plaid Link directly in the dashboard.

**Solution:** A tiny Python HTTP server (`plaid_link_server.py`) runs as a background
thread on port 8508. It serves a full standalone Plaid Link HTML page and receives
the `public_token` callback. This bypasses the iframe restriction entirely.

```
Dashboard button click
  → webbrowser.open("http://localhost:8508?token=xxx")
  → New browser tab (full page, no iframe)
  → Plaid Link SDK runs freely ✅
  → onSuccess → POST public_token → localhost:8508
  → Server exchanges token → saves access_token
  → User returns to dashboard → clicks Refresh
```

### MCP Tools Available to the AI Agent

| Tool | Description |
|---|---|
| `get_bank_accounts()` | Sandbox accounts with real Plaid balances |
| `get_bank_transactions(account_id, limit)` | Sandbox transactions with merchant data |
| `create_plaid_link_token()` | Create a link_token to start the Plaid Link flow |
| `get_real_bank_accounts()` | Accounts from all user-linked real banks |
| `get_real_bank_transactions(limit)` | Transactions from all user-linked real banks |
| `get_linked_real_banks()` | List of linked institutions (no tokens exposed) |
| `remove_linked_bank(item_id)` | Unlink a bank |
| `initiate_brokerage_transfer(amount, account_id)` | Transfer bank → brokerage |
| `refresh_plaid_connection()` | Reset sandbox token and cursor |
| `get_plaid_connection_status()` | Full status of config + linked banks |

---

## 9. How to set up (step by step)

### Step 1 — Get free Plaid credentials (2 min)
1. Go to [dashboard.plaid.com](https://dashboard.plaid.com) → sign up free
2. Go to **Team Settings → Keys**
3. Copy `client_id` and the **Sandbox** secret

### Step 2 — Add to your `.env`
```
PLAID_CLIENT_ID=your_client_id_here
PLAID_SECRET=your_sandbox_secret_here
PLAID_ENV=sandbox
```

### Step 3 — Install the library
```bash
pip install plaid-python
```

### Step 4 — Verify the connection
```bash
python3 test_plaid.py
```
This creates a virtual bank account, fetches 12 accounts + transactions,
and saves the token. Takes about 5 seconds.

### Step 5 — Run the dashboard
```bash
python main.py dashboard
# Open http://localhost:8501 → Banking tab
```

---

## 10. The Plaid Sandbox accounts you get

After running `test_plaid.py`, you'll have access to these 12 test accounts:

| Account Name | Type | Balance |
|---|---|---|
| Plaid Checking | depository / checking | $110.00 |
| Plaid Saving | depository / savings | $210.00 |
| Plaid CD | depository / cd | $1,000.00 |
| Plaid Credit Card | credit | $410.00 |
| Plaid Money Market | depository / money market | $43,200.00 |
| Plaid IRA | investment / ira | $320.76 |
| Plaid 401k | investment / 401k | $23,631.98 |
| Plaid Student Loan | loan / student | $65,262.00 |
| Plaid Mortgage | loan / mortgage | $56,302.06 |
| Plaid HSA | depository / hsa | $6,009.00 |
| Plaid Cash Management | depository | $12,060.00 |
| Plaid Business Credit Card | credit | $5,020.00 |

---

## 11. What `transactions/sync` means

Plaid uses a cursor-based system for transactions:

- **First call** — no cursor → returns ALL historical transactions
- **Subsequent calls** — passes the `next_cursor` from last time → returns only NEW changes
- The cursor is saved to `data/plaid_cursor_sandbox.txt`
- This is efficient and mirrors how Plaid works in production

---

## 12. Going to Production (Real Banks)

When you're ready to use **real banks** (not sandbox), here's what changes:

| Item | Sandbox | Production |
|---|---|---|
| `.env` PLAID_ENV | `sandbox` | `production` |
| `.env` PLAID_SECRET | Sandbox secret | Production secret |
| Token creation | Auto via API | User goes through Plaid Link UI |
| Real money | No | Yes |
| Plaid approval | Not needed | Apply at dashboard.plaid.com |
| Cost | Free | Per-item monthly fee |
| Code changes | — | None — same code, same SDK |

**Important:** The entire codebase (`banking_server.py`, `banking.py`,
`plaid_link_server.py`) is already written to handle both environments.
Only the two `.env` values need to change. Nothing else.

---

## 13. Glossary

| Term | Simple meaning |
|---|---|
| **Open Banking** | Banks sharing your data with apps — with your permission |
| **Plaid** | The middleman connecting apps to 12,000+ banks |
| **Sandbox** | A safe, fake testing environment — no real money |
| **link_token** | A short-lived token used to open the Plaid Link UI |
| **public_token** | A one-time token Plaid gives after the user links their bank |
| **access_token** | The permanent token your app uses for all future API calls |
| **Item** | Plaid's word for one linked bank connection |
| **Products** | Types of data you request: `transactions`, `auth`, `identity`... |
| **transactions/sync** | Modern Plaid API that returns only changes since last check |
| **Cursor** | A bookmark: "give me everything after this point" |
| **First Platypus Bank** | Plaid's official fake test bank |
| **MFA** | Multi-Factor Authentication — the extra verification step |
| **Port 8508** | The local HTTP server that serves Plaid Link and handles callbacks |
