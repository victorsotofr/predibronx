# PrediBronx

A personal AI forecasting experiment on [Polymarket](https://polymarket.com).

PrediBronx tested whether a simple autonomous AI system could find an edge in prediction markets by selecting active Polymarket questions, researching them with live web search, asking Claude for calibrated probabilities, and logging paper bets against the market price.

## Experiment result: no tradable edge

The paper experiment ran for **53 days**, from **2026-03-14** to **2026-05-19**. It logged **530 paper decisions** across **331 unique markets**, with **195 resolved markets** scored as of **2026-05-19**.

| Metric | PrediBronx | Baseline |
|---|---:|---:|
| Average Brier score | **0.1414** | Market price: **0.1091** |
| Random Brier baseline | **0.2500** | Always predict 50% |
| Paper return | **-41.1%** | Since inception |

The result was clear: PrediBronx was better than random, but worse than simply using the market price. It did not show a tradable edge.

The main failure mode was not broad randomness. It was **overconfident disagreement with the market**, especially on high-edge YES calls. Predictions with estimated probability >=85% resolved YES only 63.2% of the time and contributed about -61.0 percentage points of P&L. Confidence did not reliably protect the system: confidence 7+ calls had the worst Brier bucket and contributed about -49.7 percentage points. Directionally, YES bets were the weak side, while NO bets were positive.

## Interpretation: the market was the baseline to beat

Prediction markets are not just data sources; they are information aggregation mechanisms. Polymarket's [prices and order books](https://docs.polymarket.com/concepts/prices-orderbook) come from peer-to-peer supply and demand in a CLOB, and the displayed price is intended to represent the market's probability estimate. Classic prediction-market research makes the same point more generally: prices can compress dispersed beliefs and information into a forecast, while also requiring care because prices are not perfect truth and can be distorted by liquidity, incentives, risk preferences, and market design ([Wolfers and Zitzewitz](https://www.aeaweb.org/articles?id=10.1257%2F0895330041371321), [Manski](https://www.nber.org/papers/w10359)).

That matters for an AI bot. If the information LinkUp retrieves is public and already salient to traders, then search may improve the explanation without creating new edge. In many markets, PrediBronx was probably rediscovering information already embedded in the price, then occasionally adding brittle interpretation on top. The hard problem was not "can the model find relevant facts?" It was "can the model add incremental information, better calibration, or faster interpretation than the market?"

My takeaway: the market price is the first model to beat. A future version would need a real source of advantage: deeper multi-source retrieval, better parsing of market resolution rules, faster reaction to new information, calibrated rejection of extreme edges, or empirical evidence that a specific class of markets is systematically mispriced.

## Paper mode, not market making

PrediBronx did **not** execute live trades, post quotes, or provide liquidity on the Polymarket CLOB. It was a paper forecaster: it observed the market price, generated a probability estimate, sized a hypothetical bet with quarter-Kelly, logged the decision, and scored it after resolution.

That makes the negative result stronger. The reported -41.1% return is before real execution frictions such as spread, slippage, order-fill uncertainty, liquidity constraints, and operational risk. The strategy failed before it had to survive live trading.

## What PrediBronx does

PrediBronx runs a fully automated daily pipeline: it selects markets, researches them with live web data, generates calibrated probability estimates using Claude, sizes hypothetical bets with the Kelly criterion, and delivers results to a Telegram bot and web dashboard.

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
 Dashboard (Vercel)     ← live UI: picks, P&L per bet, Brier scores
        │
        ▼
   Evaluator            ← Brier scores & returns once markets resolve
```

The pipeline runs daily at a configurable time (default 08:00 ET). A second job checks Polymarket for newly resolved markets and scores them automatically.

---

## Operational status

Status: **stopped on 2026-05-19**. The default configuration now keeps the prediction pipeline disabled (`EXPERIMENT_STOPPED=true`) and disables automatic resolution checks unless explicitly re-enabled.

Operational shutdown steps for the deployed VM:

```bash
sudo systemctl stop predibronx-bot.service
sudo systemctl disable predibronx-bot.service
sudo systemctl restart predibronx-api.service
```

The Vercel dashboard includes a static archive at `dashboard/public/archive.json`, so the VM can stay stopped while the historical run history, picks, performance metrics, and log tail remain visible. To stop all Google runtime cost, stop the VM:

```bash
gcloud compute instances stop predibronx-server --project predibronx --zone us-central1-c
```

---

## Key design choices

- **Confidence gating** — bets are zeroed when Claude's confidence < 5/10, avoiding low-conviction noise trades (unlike fixed-stake benchmarks)
- **Resolution-source verification** — Claude is explicitly instructed to verify predictions against the market's official data source (BLS, FIFA, AP News, etc.) and reduce confidence if it cannot; this prevents acting on media misreporting
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
- *(Future live execution only)* Polymarket API key and a Polygon wallet private key

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

# Optional — live trading flag (execution is not implemented; defaults to paper mode)
LIVE_TRADING=false
POLYMARKET_API_KEY=
POLYGON_WALLET_PRIVATE_KEY=

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
| `DAILY_LOSS_LIMIT` | 0.02 | Daily drawdown limit before pausing |
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

## GCP deployment (production)

The bot runs as two systemd services on a GCP e2-micro VM:

```
predibronx-bot.service   ← paper forecasting pipeline + Telegram polling
predibronx-api.service   ← FastAPI dashboard API on :8080
```

Both are set to `Restart=always` and `WantedBy=multi-user.target`.

The dashboard is deployed to Vercel from the `dashboard/` subdirectory, with `PREDIBRONX_API_URL=http://<VM_IP>:8080` set as a server-side environment variable.

When the VM API is unreachable, the Vercel API routes and React client fall back to the static archive in `dashboard/public/archive.json`.

---

## Dashboard

Deploy the `dashboard/` directory to Vercel:

1. New Project → import repo → set **Root Directory** to `dashboard`
2. Set environment variable: `PREDIBRONX_API_URL=http://<VM_IP>:8080`
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
- **Cumulative return** — paper P&L computed from bet direction, fraction, and market price at decision time
- **Win rate** — fraction of resolved bets where direction was correct

---

## Disclaimer

This project is experimental and for personal use. Past prediction performance does not guarantee future results. PrediBronx did not validate a market edge; do not risk capital without independent validation.
