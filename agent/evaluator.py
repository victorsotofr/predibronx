"""Evaluate prediction quality: Brier scores, returns, and baselines."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date

import httpx

import config

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Evaluation metrics for a single resolved market."""

    market_id: str
    brier_score: float
    return_pct: float
    baseline_random_brier: float  # Brier if we always predicted 0.5
    baseline_market_brier: float  # Brier if we used market price as prediction


def _brier(predicted: float, outcome: float) -> float:
    """Brier score: (predicted - outcome)^2. Lower is better."""
    return (predicted - outcome) ** 2


def _bet_return(
    direction: str,
    bet_fraction: float,
    market_price: float,
    resolved_yes: bool,
) -> float:
    """Compute return on a bet.

    If you buy YES at price p and it resolves YES, you gain (1-p)/p per unit.
    If it resolves NO, you lose your stake (-1).
    Vice versa for NO bets.
    """
    if bet_fraction == 0:
        return 0.0

    if direction == "YES":
        price = market_price
        won = resolved_yes
    else:
        price = 1.0 - market_price
        won = not resolved_yes

    if price <= 0 or price >= 1:
        return 0.0

    if won:
        gain_per_unit = (1.0 - price) / price
        return bet_fraction * gain_per_unit
    else:
        return -bet_fraction


def evaluate_resolved_market(
    market_id: str,
    resolved_yes: bool,
    db_path: str | None = None,
) -> EvaluationResult | None:
    """Evaluate our prediction for a resolved market.

    Reads the latest decision from SQLite, computes metrics, stores in performance.
    """
    path = db_path or str(config.DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT estimated_prob, market_price, bet_direction, bet_fraction, run_date
        FROM decisions
        WHERE market_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (market_id,),
    ).fetchone()

    if row is None:
        logger.warning("No decision found for market %s", market_id)
        conn.close()
        return None

    outcome = 1.0 if resolved_yes else 0.0

    our_brier = _brier(row["estimated_prob"], outcome)
    random_brier = _brier(0.5, outcome)  # Always-0.5 baseline
    market_brier = _brier(row["market_price"], outcome)  # Market-price baseline
    return_pct = _bet_return(
        row["bet_direction"],
        row["bet_fraction"],
        row["market_price"],
        resolved_yes,
    )

    # Store outcome
    conn.execute(
        """
        INSERT OR REPLACE INTO outcomes (market_id, resolved_yes, resolved_at)
        VALUES (?, ?, datetime('now'))
        """,
        (market_id, 1 if resolved_yes else 0),
    )
    conn.commit()

    result = EvaluationResult(
        market_id=market_id,
        brier_score=our_brier,
        return_pct=return_pct,
        baseline_random_brier=random_brier,
        baseline_market_brier=market_brier,
    )

    logger.info(
        "Eval %s: brier=%.4f (random=%.4f, market=%.4f) return=%.2f%%",
        market_id,
        our_brier,
        random_brier,
        market_brier,
        return_pct * 100,
    )

    conn.close()
    return result


def compute_running_performance(db_path: str | None = None) -> dict:
    """Compute aggregate performance stats across all resolved markets."""
    path = db_path or str(config.DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            d.estimated_prob,
            d.market_price,
            d.bet_direction,
            d.bet_fraction,
            o.resolved_yes
        FROM decisions d
        JOIN outcomes o ON d.market_id = o.market_id
        WHERE o.resolved_yes IS NOT NULL
          AND d.id = (
              SELECT id FROM decisions
              WHERE market_id = d.market_id
              ORDER BY created_at DESC LIMIT 1
          )
        ORDER BY d.created_at
        """
    ).fetchall()

    conn.close()

    if not rows:
        return {
            "total_resolved": 0,
            "avg_brier": None,
            "avg_random_brier": None,
            "avg_market_brier": None,
            "total_return": 0.0,
        }

    briers = []
    random_briers = []
    market_briers = []
    total_return = 0.0

    for r in rows:
        outcome = 1.0 if r["resolved_yes"] else 0.0
        briers.append(_brier(r["estimated_prob"], outcome))
        random_briers.append(_brier(0.5, outcome))
        market_briers.append(_brier(r["market_price"], outcome))
        total_return += _bet_return(
            r["bet_direction"],
            r["bet_fraction"],
            r["market_price"],
            bool(r["resolved_yes"]),
        )

    n = len(rows)
    return {
        "total_resolved": n,
        "avg_brier": sum(briers) / n,
        "avg_random_brier": sum(random_briers) / n,
        "avg_market_brier": sum(market_briers) / n,
        "total_return": total_return,
    }

GAMMA_MARKET_URL = "https://gamma-api.polymarket.com/markets/{market_id}"


async def check_and_score_resolved_markets(db_path: str | None = None) -> int:
    """Poll Polymarket for unscored markets and evaluate any that have resolved.

    Returns the number of newly scored markets.
    """
    path = db_path or str(config.DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Find all market IDs with decisions but no outcome yet
    rows = conn.execute(
        """
        SELECT DISTINCT d.market_id
        FROM decisions d
        LEFT JOIN outcomes o ON d.market_id = o.market_id
        WHERE o.market_id IS NULL
        """
    ).fetchall()
    conn.close()

    unresolved_ids = [r["market_id"] for r in rows]
    if not unresolved_ids:
        logger.info("No unscored markets to check")
        return 0

    logger.info("Checking %d unscored markets for resolution...", len(unresolved_ids))
    newly_scored = 0

    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        for market_id in unresolved_ids:
            try:
                url = GAMMA_MARKET_URL.format(market_id=market_id)
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                # Gamma API uses umaResolutionStatus + outcomePrices to signal
                # resolution. The "resolved" boolean field is unreliable (often None).
                uma_status = data.get("umaResolutionStatus", "")
                is_closed = data.get("closed", False)

                try:
                    outcomes = json.loads(data.get("outcomes") or "[]")
                    prices = [float(p) for p in json.loads(data.get("outcomePrices") or "[]")]
                except (ValueError, TypeError):
                    outcomes, prices = [], []

                has_winner = any(p == 1.0 for p in prices)
                is_resolved = uma_status == "resolved" or (is_closed and has_winner)

                logger.info(
                    "market %s: uma_status=%s, closed=%s, prices=%s → resolved=%s",
                    market_id, uma_status, is_closed, prices, is_resolved,
                )

                if not is_resolved:
                    if is_closed:
                        logger.warning(
                            "Market %s is closed but not yet resolved by Polymarket "
                            "— will recheck tomorrow",
                            market_id,
                        )
                    continue

                # Find the winning outcome (price == 1.0)
                winning_idx = next((i for i, p in enumerate(prices) if p == 1.0), None)
                if winning_idx is None or winning_idx >= len(outcomes):
                    logger.warning(
                        "Market %s resolved but no clear winner in prices %s", market_id, prices
                    )
                    continue

                outcome_str = outcomes[winning_idx].lower()
                if outcome_str == "yes":
                    resolved_yes = True
                elif outcome_str == "no":
                    resolved_yes = False
                else:
                    logger.warning(
                        "Market %s resolved but outcome is '%s' — skipping",
                        market_id, outcomes[winning_idx],
                    )
                    continue

                result = evaluate_resolved_market(market_id, resolved_yes, db_path=path)
                if result:
                    newly_scored += 1
                    logger.info(
                        "Scored market %s: brier=%.4f return=%.2f%%",
                        market_id, result.brier_score, result.return_pct * 100,
                    )

            except httpx.HTTPError as exc:
                logger.error("Failed to check market %s: %s", market_id, exc)
            except Exception:
                logger.exception("Unexpected error checking market %s", market_id)

    logger.info(
        "Resolution check complete: %d checked, %d newly scored",
        len(unresolved_ids), newly_scored,
    )
    return newly_scored


if __name__ == "__main__":
    stats = compute_running_performance()
    print("Running performance:")
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")
