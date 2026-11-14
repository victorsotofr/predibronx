"""APScheduler job: daily pipeline run at configurable time."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

import config
from agent.executor import execute_decisions, log_markets
from agent.evaluator import check_and_score_resolved_markets
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
    if config.EXPERIMENT_STOPPED:
        logger.info("Experiment is stopped, skipping daily pipeline run")
        return

    if is_paused():
        logger.info("Scheduler is paused, skipping daily run")
        return

    logger.info("Starting daily pipeline run")

    try:
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

        logger.info("Step 2/4: Researching %d markets...", len(markets))
        research = await research_markets(markets)

        logger.info("Step 3/4: Forecasting...")
        decisions = await forecast_all(markets, research)

        logger.info("Step 4/4: Logging decisions...")
        summaries = execute_decisions(decisions)

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

    if not config.EXPERIMENT_STOPPED:
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
    else:
        logger.info("Experiment stopped: daily prediction pipeline is disabled")

    # Resolution check — runs daily at 09:00 ET (1h after main pipeline)
    async def _run_resolution_check() -> None:
        """Wrapper to run resolution check and notify via Telegram."""
        newly_scored = await check_and_score_resolved_markets()
        if newly_scored > 0:
            await app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=f"🎯 Resolution check: {newly_scored} market(s) newly scored."
                     f" Use /performance to see updated stats.",
            )

    if config.RUN_RESOLUTION_CHECKS:
        resolution_trigger = CronTrigger(
            hour=9,
            minute=0,
            timezone=config.TIMEZONE,
        )

        scheduler.add_job(
            _run_resolution_check,
            trigger=resolution_trigger,
            id="resolution_check",
            name="Daily resolution check",
            replace_existing=True,
        )
    else:
        logger.info("Resolution checks are disabled")

    pipeline_status = (
        "disabled"
        if config.EXPERIMENT_STOPPED
        else f"{config.DAILY_RUN_HOUR:02d}:{config.DAILY_RUN_MINUTE:02d}"
    )
    resolution_status = (
        "enabled at 09:00" if config.RUN_RESOLUTION_CHECKS else "disabled"
    )
    logger.info(
        "Scheduler configured: pipeline %s, resolution check %s (%s)",
        pipeline_status,
        resolution_status,
        config.TIMEZONE,
    )
    return scheduler


def scheduler_status_message() -> str:
    """Human-readable status for CLI diagnostics."""
    pipeline_status = (
        "disabled"
        if config.EXPERIMENT_STOPPED
        else f"at {config.DAILY_RUN_HOUR:02d}:{config.DAILY_RUN_MINUTE:02d}"
    )
    return (
        "Experiment stopped; scheduled prediction and resolution jobs are disabled."
        if config.EXPERIMENT_STOPPED and not config.RUN_RESOLUTION_CHECKS
        else (
            f"Pipeline {pipeline_status}; "
            f"resolution checks {'enabled' if config.RUN_RESOLUTION_CHECKS else 'disabled'} "
            f"({config.TIMEZONE})."
        )
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(scheduler_status_message())
    print("Run main.py to start the full system.")
