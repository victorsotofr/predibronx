# PrediBronx

A personal AI-powered prediction trading bot for [Polymarket](https://polymarket.com).

PrediBronx runs a fully automated daily pipeline: it selects markets, researches them with live web data, generates calibrated probability estimates using Claude, sizes bets with the Kelly criterion, and delivers results to a Telegram bot — with a live web dashboard and optional execution on the Polymarket CLOB.

Inspired by [PrediBench](https://github.com/PresageLabs/PrediBench), an open-source benchmark that measures LLM forecasting ability on real-world prediction markets.

---

## How it works

```
Polymarket Gamma API
        │
        ▼
 Market Selector        ← top markets by volume, non-crypto, resolving within 60 days
        │
        ▼
   Researcher           ← LinkUp deep search (last 48h) for each market
        │
        ▼
   Forecaster           ← Claude superforecaster estimates true probability + confidence
        │
        ▼
   Bet Sizer            ← Quarter-Kelly criterion, confidence-gated (no bet if conf < 5/10)
        │
        ▼
   Executor / DB        ← SQLite log + paper/live execution
        │
        ▼
  Telegram Bot          ← daily summary, per-trade approvals, /performance
        │
        ▼
 Dashboard (Vercel)     ← live UI: picks, P&L per bet, Brier scores
        │
        ▼
   Evaluator            ← Brier scores & returns once markets resolve
```

The pipeline runs daily at a configurable time (default 08:00 ET). A second job checks Polymarket for newly resolved markets and scores them automatically.

---

## Key design choices

- **Confidence gating** — bets are zeroed when Claude's confidence < 5/10, avoiding low-conviction noise trades (unlike fixed-stake benchmarks)
- **Resolution-source verification** — Claude is explicitly instructed to verify predictions against the market's official data source (BLS, FIFA, AP News, etc.) and reduce confidence if it cannot; this prevents acting on media misreporting
- **Quarter-Kelly sizing** — bet fractions are computed from the Kelly criterion and multiplied by 0.25 for conservatism, capped at 10% per market
- **Brier scoring** — every resolved market is scored against a random baseline (always predict 0.5) and a market-price baseline; this follows the methodology from PrediBench

### What PrediBench taught us

PrediBench's most actionable finding: **research depth drives performance**. Models that visited more webpages (Perplexity Sonar Deep Research: 16+ pages) significantly outperformed models that only read search snippets. PrediBronx currently uses a single LinkUp search per market — the main lever for improvement is moving toward multi-step agentic research (search → fetch → synthesize multiple sources).

---

## Stack

| Layer | Technology |
|---|---|
| Bot runtime | Python 3.11+, APScheduler, python-telegram-bot |
| AI forecasting | Anthropic Claude (`claude-sonnet-4-6`) |
| Research | LinkUp deep search API |
| Market data | Polymarket Gamma API |
| Storage | SQLite (decisions, outcomes, performance) |
| Infrastructure | GCP Compute Engine (e2-micro), systemd |
| Dashboard | Vite + React, Vercel |
| Dashboard API | FastAPI (uvicorn), GCP firewall port 8080 |

---

## Prerequisites

- Python ≥ 3.11 with [uv](https://github.com/astral-sh/uv)
- A [Telegram bot token](https://core.telegram.org/bots#botfather) and chat ID
- An [Anthropic API key](https://console.anthropic.com/)
- A [LinkUp API key](https://linkup.so/)
- *(Live mode only)* Polymarket API key and a Polygon wallet private key

---

## Installation

```bash
git clone <your-repo>
cd predibronx
uv sync
```

---

## Configuration

Create a `.env` file at the project root:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
LINKUP_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Optional — live trading (defaults to paper mode)
LIVE_TRADING=false
POLYMARKET_API_KEY=
POLYGON_WALLET_PRIVATE_KEY=

# Optional — scheduling
DAILY_RUN_HOUR=8
DAILY_RUN_MINUTE=0
TIMEZONE=America/New_York

# Optional — dashboard link included in Telegram summaries
DASHBOARD_URL=https://your-dashboard.vercel.app
```

Tunable parameters in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `MAX_BET_FRACTION` | 0.10 | Max stake per market (fraction of budget) |
| `DAILY_LOSS_LIMIT` | 0.02 | Daily drawdown limit before pausing |
| `KELLY_FRACTION` | 0.25 | Kelly multiplier (quarter-Kelly) |
| `TOP_MARKETS` | 10 | Markets evaluated per daily run |
| `MAX_END_DAYS` | 60 | Only consider markets resolving within this window |

---

## Running

```bash
# Start bot + scheduler (polls Telegram, runs at configured time)
uv run python main.py

# Trigger full pipeline immediately on startup
uv run python main.py --run-now
```

The SQLite database is created automatically at `db/predibronx.db`.

---

## GCP deployment (production)

The bot runs as two systemd services on a GCP e2-micro VM:

```
predibronx-bot.service   ← main pipeline + Telegram polling
predibronx-api.service   ← FastAPI dashboard API on :8080
```

Both are set to `Restart=always` and `WantedBy=multi-user.target`.

The dashboard is deployed to Vercel from the `dashboard/` subdirectory, with `PREDIBRONX_API_URL=http://<VM_IP>:8080` set as a server-side environment variable.

---

## Dashboard

Deploy the `dashboard/` directory to Vercel:

1. New Project → import repo → set **Root Directory** to `dashboard`
2. Set environment variable: `PREDIBRONX_API_URL=http://<VM_IP>:8080`
3. Deploy

The dashboard proxies API calls server-side (Vercel → VM) to avoid mixed-content browser issues.

---

## Telegram commands

| Command | Description |
|---|---|
| `/start` | Show available commands |
| `/status` | Mode, last run, performance summary |
| `/markets` | Today's picks with edge and rationale |
| `/explain <market_id>` | Full reasoning for a specific market |
| `/performance` | Brier scores and cumulative return vs baselines |
| `/pause` | Pause the daily scheduler |
| `/resume` | Resume the daily scheduler |

In live mode, each trade triggers an inline approval button before execution.

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
│   ├── executor.py        # SQLite persistence + CLOB execution
│   └── evaluator.py       # Brier scoring + return calculation
├── bot/
│   ├── telegram_bot.py    # Command handlers + approval flow
│   └── scheduler.py       # APScheduler daily jobs
├── api/
│   └── server.py          # FastAPI dashboard API
├── dashboard/             # Vite + React web dashboard (deploy to Vercel)
└── db/
    └── predibronx.db      # Auto-created SQLite database
```

---

## Performance metrics

Following [PrediBench](https://github.com/PresageLabs/PrediBench) methodology:

- **Brier score** — mean squared error between estimated probability and binary outcome; lower is better; baselines: random (always 0.5) and market price
- **Cumulative return** — paper P&L computed from bet direction, fraction, and market price at decision time
- **Win rate** — fraction of resolved bets where direction was correct

---

## Disclaimer

This project is experimental and for personal use. Past prediction performance does not guarantee future results. Use paper mode until you have validated the system's edge. Never risk capital you cannot afford to lose.
