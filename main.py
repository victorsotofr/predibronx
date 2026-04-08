"""PrediBronx — AI-powered Polymarket prediction system.

Entrypoint that starts the Telegram bot and daily scheduler.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import config
from agent.executor import _init_db
from bot.scheduler import create_scheduler, run_daily_pipeline
from bot.telegram_bot import build_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.BASE_DIR / "bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("predibronx")


def main() -> None:
    """Start PrediBronx: init DB, start scheduler, run Telegram bot."""
    logger.info("PrediBronx starting up...")
    logger.info("Mode: %s", "LIVE" if config.LIVE_TRADING else "PAPER")
    logger.info("DB: %s", config.DB_PATH)

    # Initialize database
    conn = _init_db()
    conn.close()
    logger.info("Database initialized")

    # Build Telegram app
    app = build_app()

    # Create scheduler
    scheduler = create_scheduler(app)

    # Handle --run-now flag for immediate pipeline execution
    run_now = "--run-now" in sys.argv

    async def post_init(application) -> None:
        """Start scheduler after Telegram bot is initialized."""
        scheduler.start()
        logger.info("Scheduler started")
        if run_now:
            logger.info("Running pipeline immediately (--run-now)")
            await run_daily_pipeline(application)

    app.post_init = post_init

    async def post_shutdown(application) -> None:
        """Clean up scheduler on shutdown."""
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    app.post_shutdown = post_shutdown

    # Start polling (blocks until interrupted)
    logger.info("Starting Telegram bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
