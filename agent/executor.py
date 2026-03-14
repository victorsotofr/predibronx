"""Execute (or log) trading decisions.

Phase 1: Paper mode only — logs decisions to SQLite, never touches CLOB.
Phase 4 (future): Will integrate with py_clob_client for real order execution.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path

import config
from agent.forecaster import ForecastDecision
from agent.market_selector import MarketInfo

logger = logging.getLogger(__name__)


def _init_db(db_path: str | None = None) -> sqlite3.Connection:
    """Initialize the database, creating tables if needed."""
    path = db_path or str(config.DB_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)

    schema_path = config.BASE_DIR / "db" / "schema.sql"
    if schema_path.exists():
        conn.executescript(schema_path.read_text())

    return conn


def log_markets(markets: list[MarketInfo], db_path: str | None = None) -> None:
    """Insert or update market records in the database."""
    conn = _init_db(db_path)
    for m in markets:
        conn.execute(
            """
            INSERT INTO markets (id, title, description, end_date, category, volume, liquidity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                volume = excluded.volume,
                liquidity = excluded.liquidity
            """,
            (m.id, m.question, m.description[:1000], m.end_date, m.category, m.volume, m.liquidity),
        )
    conn.commit()
    conn.close()
    logger.info("Logged %d markets to DB", len(markets))


def log_decisions(decisions: list[ForecastDecision], db_path: str | None = None) -> None:
    """Log forecast decisions to the database."""
    conn = _init_db(db_path)
    today = date.today().isoformat()

    for d in decisions:
        conn.execute(
            """
            INSERT INTO decisions
                (market_id, run_date, estimated_prob, market_price,
                 bet_direction, bet_fraction, confidence, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.market_id,
                today,
                d.estimated_probability,
                d.market_price,
                d.bet_direction,
                d.bet_fraction,
                d.confidence,
                d.rationale,
            ),
        )
    conn.commit()
    conn.close()
    logger.info("Logged %d decisions to DB", len(decisions))


def execute_decisions(decisions: list[ForecastDecision]) -> list[dict]:
    """Execute or log decisions based on trading mode.

    In paper mode: just log and return summaries.
    In live mode: NOT IMPLEMENTED — will integrate CLOB in Phase 4.
    """
    if config.LIVE_TRADING:
        logger.error("LIVE TRADING IS NOT IMPLEMENTED. Falling back to paper mode.")
        # Future Phase 4: integrate py_clob_client here
        # Do NOT proceed with real trades until executor is reviewed

    log_decisions(decisions)

    summaries = []
    for d in decisions:
        edge = abs(d.estimated_probability - d.market_price)
        summaries.append(
            {
                "market_id": d.market_id,
                "market_title": d.market_title,
                "direction": d.bet_direction,
                "fraction": d.bet_fraction,
                "edge": edge,
                "confidence": d.confidence,
                "mode": "PAPER",
            }
        )

    return summaries


if __name__ == "__main__":
    print(f"Trading mode: {'LIVE' if config.LIVE_TRADING else 'PAPER'}")
    print(f"DB path: {config.DB_PATH}")
    print(f"Max bet fraction: {config.MAX_BET_FRACTION}")
    print(f"Daily loss limit: {config.DAILY_LOSS_LIMIT}")

    # Quick DB init test
    conn = _init_db()
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    conn.close()
