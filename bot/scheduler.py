"""APScheduler job: daily pipeline run at configurable time."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

import config
from agent.executor import execute_decisions, log_markets
from agent.forecaster import forecast_all
from agent.market_selector import fetch_top_markets
from agent.researcher import research_markets
from bot.telegram_bot import (
    format_daily_summary,
    is_paused,
    send_approval_request,
    send_summary,
)

logger = logging.getLogger(__name__)


async def run_daily_pipeline(app: Application) -> None:
    """Full daily pipeline: fetch → research → forecast → log → notify."""
    if is_paused():
        logger.info("Scheduler is paused, skipping daily run")
        return

    logger.info("Starting daily pipeline run")

    try:
        # 1. Fetch markets
        logger.info("Step 1/4: Fetching top markets...")
        markets = await fetch_top_markets()
        if not markets:
            logger.warning("No markets found, aborting run")
            await app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text="Daily run: no eligible markets found today.",
            )
            return
        log_markets(markets)

        # 2. Research
        logger.info("Step 2/4: Researching %d markets...", len(markets))
        research = await research_markets(markets)

        # 3. Forecast
        logger.info("Step 3/4: Forecasting...")
        decisions = await forecast_all(markets, research)

        # 4. Log & execute
        logger.info("Step 4/4: Logging decisions...")
        summaries = execute_decisions(decisions)

        # 5. Notify via Telegram
        await send_summary(app, decisions)

        # In live mode, send per-trade approval requests
        if config.LIVE_TRADING:
            for d in decisions:
                if d.bet_fraction > 0:
                    await send_approval_request(app, d)

        logger.info("Daily pipeline complete: %d decisions logged", len(decisions))

    except Exception:
        logger.exception("Daily pipeline failed")
        try:
            await app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text="Daily run failed — check logs.",
            )
        except Exception:
            logger.exception("Failed to send error notification")


def create_scheduler(app: Application) -> AsyncIOScheduler:
    """Create an APScheduler that runs the daily pipeline."""
    scheduler = AsyncIOScheduler()

    trigger = CronTrigger(
        hour=config.DAILY_RUN_HOUR,
        minute=config.DAILY_RUN_MINUTE,
        timezone=config.TIMEZONE,
    )

    scheduler.add_job(
        run_daily_pipeline,
        trigger=trigger,
        args=[app],
        id="daily_pipeline",
        name="Daily prediction pipeline",
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured: daily at %02d:%02d %s",
        config.DAILY_RUN_HOUR,
        config.DAILY_RUN_MINUTE,
        config.TIMEZONE,
    )
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(
        f"Scheduler would run daily at {config.DAILY_RUN_HOUR:02d}:{config.DAILY_RUN_MINUTE:02d} "
        f"{config.TIMEZONE}"
    )
    print("Run main.py to start the full system.")
