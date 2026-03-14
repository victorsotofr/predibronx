---
name: PrediBronx project overview
description: AI-powered Polymarket prediction trading system — architecture, phases, and key decisions
type: project
---

PrediBronx is a personal AI-powered prediction market trading system on Polymarket.

**Stack:** Python 3.11, uv, SQLite, Anthropic Claude, LinkUp API, Telegram bot, APScheduler.

**Reference repos:** PrediBench (evaluation framework) and Polymarket/agents (API/CLOB integration) in reference_repos/.

**Phases:**
- Phase 1 (DONE): market_selector, researcher, forecaster, evaluator, executor (paper-only), telegram_bot, scheduler, schema.sql, config.py
- Phase 4 (FUTURE): Real CLOB execution via py_clob_client — user explicitly asked to be consulted before implementing this.

**Why:** User wants a daily automated pipeline that fetches markets, researches them, generates probability estimates with Claude, and logs paper trades with Telegram notifications.

**How to apply:** Never implement live trading without explicit user approval. Executor is a stub. Kelly sizing is quarter-Kelly capped at MAX_BET_FRACTION=0.10.
