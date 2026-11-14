# Architecture, setup, and historical operation

[← PrediBronx](../README.md)

**The experiment is stopped.** These are implementation and setup notes, not a claim that its services are currently running.

## Pipeline

During the experiment, PrediBronx ran a daily pipeline: selecting markets, researching them with live web data, estimating probabilities with Claude, sizing hypothetical bets with quarter-Kelly, and delivering results to Telegram and a web dashboard.

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
   Executor / DB        ← SQLite log + paper decision record
        │
        ▼
  Telegram Bot          ← daily summary, explanations, /performance
        │
        ▼
 Dashboard (Vercel)     ← live or archived UI: picks, P&L per bet, Brier scores
        │
        ▼
   Evaluator            ← Brier scores & returns once markets resolve
```

When explicitly enabled, the pipeline is scheduled at a configurable time (default 08:00 ET). A separate, opt-in resolution job checks Polymarket for newly resolved markets. Both are disabled in the default stopped configuration.

---

## Operational status

Status: **stopped on 2026-05-19**. The default configuration now keeps the prediction pipeline disabled (`EXPERIMENT_STOPPED=true`) and disables automatic resolution checks unless explicitly re-enabled.

Operational shutdown steps for the deployed VM:

```bash
sudo systemctl stop predibronx-bot.service
sudo systemctl disable predibronx-bot.service
sudo systemctl restart predibronx-api.service
```

The Vercel dashboard includes a static archive at `dashboard/public/archive.json`, so the VM can stay stopped while the historical run history, picks, performance metrics, and log tail remain visible. Historical VM stop command (requires owner approval before execution; stopping a VM does not remove storage or other billable resources):

```bash
gcloud compute instances stop predibronx-server --project predibronx --zone us-central1-c
```

---

## Key design choices

- **Confidence gating** — bets are zeroed when Claude's confidence < 5/10, avoiding low-conviction noise trades (unlike fixed-stake benchmarks)
- **Resolution-source verification** — Claude is explicitly instructed to verify predictions against the market's official data source (BLS, FIFA, AP News, etc.) and reduce confidence if it cannot; this asks the model to check sources, but does not guarantee accurate interpretation
- **Quarter-Kelly sizing** — bet fractions are computed from the Kelly criterion and multiplied by 0.25 for conservatism, capped at 10% per market
- **Brier scoring** — every resolved market is scored against a random baseline (always predict 0.5) and a market-price baseline; this follows the methodology from PrediBench

### What PrediBench taught us

PrediBench's most actionable finding: **research depth drives performance**. Models that visited more webpages (Perplexity Sonar Deep Research: 16+ pages) significantly outperformed models that only read search snippets. PrediBronx used a single LinkUp search per market; if a future version tries to beat market prices, deeper research is necessary but not sufficient. It also needs evidence that the research adds information not already reflected in the price.

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

---

## Installation

```bash
git clone https://github.com/victorsotofr/predibronx.git
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

# Keep paper mode: live execution is not implemented
LIVE_TRADING=false

# Optional — experiment kill-switch
EXPERIMENT_STOPPED=true
RUN_RESOLUTION_CHECKS=false

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
| `DAILY_LOSS_LIMIT` | 0.02 | Configuration value only; no automatic loss-limit enforcement |
| `KELLY_FRACTION` | 0.25 | Kelly multiplier (quarter-Kelly) |
| `TOP_MARKETS` | 10 | Markets evaluated per daily run |
| `MAX_END_DAYS` | 60 | Only consider markets resolving within this window |

Set `EXPERIMENT_STOPPED=false` to restart scheduled prediction runs. Set `RUN_RESOLUTION_CHECKS=true` only if you want the bot to keep polling Polymarket for newly resolved archived markets.

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

## Historical GCP deployment

The deployment used two systemd services on a GCP e2-micro VM:

```
predibronx-bot.service   ← paper forecasting pipeline + Telegram polling
predibronx-api.service   ← FastAPI dashboard API on :8080
```

The service definitions use `Restart=always` and `WantedBy=multi-user.target`; this describes their configuration, not the current VM state.

The dashboard is deployed to Vercel from the `dashboard/` subdirectory, with `PREDIBRONX_API_URL=http://<VM_IP>:8080` set as a server-side environment variable.

When the VM API is unreachable, the Vercel API routes and React client fall back to the static archive in `dashboard/public/archive.json`.

---

## Dashboard

The archived dashboard can run without a VM or provider keys. Its Vercel routes and client fall back to `dashboard/public/archive.json` when the API is unavailable; omit `PREDIBRONX_API_URL` for archive-only use.

Deploy the `dashboard/` directory to Vercel:

1. New Project → import repo → set **Root Directory** to `dashboard`
2. For an explicitly operated live API only, set `PREDIBRONX_API_URL=http://<VM_IP>:8080`; otherwise omit it to use the archive.
3. Deploy

The dashboard proxies API calls server-side (Vercel → VM) to avoid mixed-content browser issues. If the VM is stopped, the dashboard serves the static archive instead.

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

Live CLOB execution was planned as a future phase but was not implemented during this experiment.

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
│   ├── executor.py        # SQLite persistence + paper decision logging
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
- **Paper return sum** — sum of stake-weighted hypothetical returns from the latest decision per resolved market; not compounded portfolio performance
- **Win rate** — fraction of resolved bets where direction was correct

---

## Disclaimer

This project is experimental and for personal use. Past prediction performance does not guarantee future results. PrediBronx did not validate a market edge; do not risk capital without independent validation.
