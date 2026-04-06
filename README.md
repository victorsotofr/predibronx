# PrediBronx

AI-powered prediction trading system for [Polymarket](https://polymarket.com). PrediBronx runs a fully automated daily pipeline that selects markets, researches them with live web data, generates probability estimates using Claude, sizes bets with the Kelly criterion, and delivers everything to a Telegram bot — with optional live execution on the Polymarket CLOB.

---

## How it works

```
Polymarket Gamma API
        │
        ▼
 Market Selector        ← filters active, non-crypto markets resolving within 60 days
        │
        ▼
   Researcher           ← LinkUp deep search (last 48h) for each market
        │
        ▼
   Forecaster           ← Claude superforecaster estimates TRUE probability
        │
        ▼
   Bet Sizer            ← Quarter-Kelly criterion, confidence-scaled
        │
        ▼
   Executor / DB        ← SQLite log of decisions + paper/live execution
        │
        ▼
  Telegram Bot          ← daily summary, per-trade approvals, /performance
        │
        ▼
   Evaluator            ← Brier scores & returns once markets resolve
```

The pipeline runs once a day at a configurable time (default 08:00 ET). A second daily job checks Polymarket for newly resolved markets and scores them automatically.

---

## Features

- **Market selection** — fetches top markets by volume, excludes crypto, filters by time-to-resolution
- **Live research** — LinkUp deep search supplies up-to-date context for each market question
- **Resolution-source verification** — Claude is instructed to verify predictions against the market's official resolution source; low-confidence estimates are zero-sized
- **Probability forecasting** — Claude acts as a superforecaster, returning a calibrated YES probability + confidence score
- **Kelly bet sizing** — quarter-Kelly fraction, capped at 10% per market, zeroed when confidence < 5/10
- **Paper / Live trading modes** — paper mode logs decisions only; live mode routes approved trades to the Polymarket CLOB API
- **Telegram bot** — interactive control panel with real-time alerts and trade approval buttons
- **Performance tracking** — Brier scores compared against random and market-price baselines, cumulative return

---

## Prerequisites

- Python ≥ 3.11
- A [Telegram bot token](https://core.telegram.org/bots#botfather) and a chat/channel ID
- An [Anthropic API key](https://console.anthropic.com/)
- A [LinkUp API key](https://linkup.so/)
- *(Live mode only)* Polymarket API key and a Polygon wallet private key

---

## Installation

```bash
git clone https://github.com/your-org/predibronx.git
cd predibronx
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

---

## Configuration

Copy the example below into a `.env` file at the project root:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
LINKUP_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Live trading (optional — defaults to paper mode)
LIVE_TRADING=false
POLYMARKET_API_KEY=
POLYGON_WALLET_PRIVATE_KEY=

# Scheduling (optional)
DAILY_RUN_HOUR=8
DAILY_RUN_MINUTE=0
TIMEZONE=America/New_York
```

All risk and market-selection parameters can be tuned directly in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `MAX_BET_FRACTION` | 0.10 | Max fraction of per-market budget on a single bet |
| `DAILY_LOSS_LIMIT` | 0.02 | Max daily portfolio drawdown before pausing |
| `KELLY_FRACTION` | 0.25 | Kelly multiplier (quarter-Kelly) |
| `TOP_MARKETS` | 10 | Number of markets evaluated per daily run |
| `MAX_END_DAYS` | 60 | Only consider markets resolving within this window |

---

## Running

```bash
# Start the bot (polls Telegram, runs scheduler in background)
python main.py

# Trigger the full pipeline immediately on startup
python main.py --run-now
```

The SQLite database is created automatically at `db/predibronx.db` on first run.

---

## Telegram commands

| Command | Description |
|---|---|
| `/start` | Show available commands |
| `/status` | Mode, last run, and performance summary |
| `/markets` | Today's picks with edge and rationale |
| `/explain <market_id>` | Full reasoning for a specific market |
| `/performance` | Brier scores and cumulative return vs baselines |
| `/pause` | Pause the daily scheduler |
| `/resume` | Resume the daily scheduler |

In live mode, each trade with a non-zero bet fraction triggers an inline approval button before execution.

---

## Project structure

```
predibronx/
├── main.py                # Entrypoint — wires scheduler + Telegram bot
├── config.py              # All settings (loaded from .env)
├── agent/
│   ├── market_selector.py # Polymarket Gamma API wrapper + filtering
│   ├── researcher.py      # LinkUp deep search + resolution-source extraction
│   ├── forecaster.py      # Claude superforecaster + Kelly sizing
│   ├── executor.py        # SQLite persistence + (future) CLOB execution
│   └── evaluator.py       # Brier scoring + return calculation
├── bot/
│   ├── telegram_bot.py    # Command handlers + approval flow
│   └── scheduler.py       # APScheduler daily jobs
└── db/
    └── predibronx.db      # Auto-created SQLite database
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude API client (forecaster) |
| `httpx` | Async HTTP (Polymarket + LinkUp APIs) |
| `python-telegram-bot` | Telegram bot framework |
| `apscheduler` | Cron-style daily job scheduling |
| `pydantic` | Data models and validation |
| `python-dotenv` | `.env` file loading |

---

## Disclaimer

This project is experimental. Past prediction performance does not guarantee future results. Use paper mode until you have validated the system's edge. Never risk capital you cannot afford to lose.
