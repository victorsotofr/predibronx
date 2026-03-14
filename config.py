from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Directories ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "predibronx.db"

# ── API Keys ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
LINKUP_API_KEY: str = os.environ["LINKUP_API_KEY"]
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID: str = os.environ["TELEGRAM_CHAT_ID"]
POLYMARKET_API_KEY: str = os.environ.get("POLYMARKET_API_KEY", "")
POLYGON_WALLET_PRIVATE_KEY: str = os.environ.get("POLYGON_WALLET_PRIVATE_KEY", "")

# ── Trading Mode ─────────────────────────────────────────────────────────────
LIVE_TRADING: bool = os.environ.get("LIVE_TRADING", "false").lower() == "true"

# ── Risk Limits ──────────────────────────────────────────────────────────────
MAX_BET_FRACTION: float = 0.10  # Max fraction of per-market budget on a single bet
DAILY_LOSS_LIMIT: float = 0.02  # Max daily portfolio drawdown before pausing
KELLY_FRACTION: float = 0.25  # Quarter-Kelly for conservative sizing

# ── Market Selection ─────────────────────────────────────────────────────────
TOP_MARKETS: int = 10
MAX_END_DAYS: int = 60  # Only markets resolving within this many days
EXCLUDED_CATEGORIES: set[str] = {"Crypto", "Cryptocurrency", "Bitcoin", "Ethereum"}

# ── Scheduling ───────────────────────────────────────────────────────────────
DAILY_RUN_HOUR: int = int(os.environ.get("DAILY_RUN_HOUR", "8"))
DAILY_RUN_MINUTE: int = int(os.environ.get("DAILY_RUN_MINUTE", "0"))
TIMEZONE: str = os.environ.get("TIMEZONE", "America/New_York")

# ── Claude Model ─────────────────────────────────────────────────────────────
CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
