import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "trades.db"
CACHE_DIR = DATA_DIR / "cache"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# Plaid Open Banking
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "")
PLAID_SECRET = os.getenv("PLAID_SECRET", "")
PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")  # sandbox | development | production
PLAID_TOKEN_CACHE = DATA_DIR / "plaid_token.json"

INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "100000"))
COMMISSION_RATE = float(os.getenv("COMMISSION_RATE", "0.001"))

GEMINI_MODEL = "gemini-3.0-flash"

MCP_SERVERS = {
    "financial_data": {"host": "localhost", "port": 8001},
    "geopolitical": {"host": "localhost", "port": 8002},
    "trade_execution": {"host": "localhost", "port": 8003},
}

RISK_THRESHOLDS = {
    "low": 30,
    "medium": 70,
    "high": 100,
}

SUPPORTED_SECTORS = [
    "technology", "energy", "healthcare", "finance",
    "defense", "consumer", "industrial", "materials",
]

# Autopilot settings
AUTOPILOT_POLL_INTERVAL = int(os.getenv("AUTOPILOT_POLL_INTERVAL", "60"))
AUTOPILOT_ROUTINE_INTERVAL = int(os.getenv("AUTOPILOT_ROUTINE_INTERVAL", "300"))
AUTOPILOT_RISK_CHANGE_THRESHOLD = float(os.getenv("AUTOPILOT_RISK_CHANGE_THRESHOLD", "10"))
