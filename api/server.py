"""FastAPI server exposing PrediBronx data for the dashboard."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "predibronx.db"
LOG_PATH = BASE_DIR / "bot.log"

app = FastAPI(title="PrediBronx API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    """Bot status and last run date."""
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT run_date, COUNT(*) as n FROM decisions GROUP BY run_date ORDER BY run_date DESC LIMIT 1"
        ).fetchone()
        conn.close()
        last_run = row["run_date"] if row else None
        n = row["n"] if row else 0
        return {"status": "ok", "last_run": last_run, "last_run_decisions": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runs")
def get_runs():
    """List of all run dates with summary stats."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT
            d.run_date,
            COUNT(*) as n_decisions,
            AVG(ABS(d.estimated_prob - d.market_price)) as avg_edge,
            AVG(d.confidence) as avg_confidence,
            MAX(ABS(d.estimated_prob - d.market_price)) as max_edge
        FROM decisions d
        GROUP BY d.run_date
        ORDER BY d.run_date DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/decisions")
def get_decisions(run_date: str | None = Query(default=None)):
    """All decisions, optionally filtered by run_date. Defaults to latest."""
    conn = get_db()
    if run_date is None:
        run_date_row = conn.execute(
            "SELECT MAX(run_date) as d FROM decisions"
        ).fetchone()
        run_date = run_date_row["d"] if run_date_row else None

    if run_date is None:
        conn.close()
        return []

    rows = conn.execute(
        """
        SELECT
            d.market_id,
            m.title,
            m.end_date,
            m.category,
            m.volume,
            d.run_date,
            d.estimated_prob,
            d.market_price,
            d.bet_direction,
            d.bet_fraction,
            d.confidence,
            d.rationale,
            o.resolved_yes,
            o.resolved_at
        FROM decisions d
        JOIN markets m ON d.market_id = m.id
        LEFT JOIN outcomes o ON d.market_id = o.market_id
        WHERE d.run_date = ?
        ORDER BY ABS(d.estimated_prob - d.market_price) DESC
        """,
        (run_date,),
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        raw_edge = d["estimated_prob"] - d["market_price"]
        d["edge"] = raw_edge if d["bet_direction"] == "YES" else -raw_edge

        # P&L and outcome for resolved markets
        if d["resolved_yes"] is not None:
            direction = d["bet_direction"]
            fraction = d["bet_fraction"]
            price = d["market_price"] if direction == "YES" else 1.0 - d["market_price"]
            resolved = bool(d["resolved_yes"])
            won = (resolved and direction == "YES") or (not resolved and direction == "NO")
            d["won"] = won
            if fraction > 0 and 0 < price < 1:
                d["pnl"] = fraction * (1.0 - price) / price if won else -fraction
            else:
                d["pnl"] = 0.0
        else:
            d["won"] = None
            d["pnl"] = None

        result.append(d)
    return result


@app.get("/performance")
def get_performance():
    """Aggregated performance metrics across all scored predictions."""
    conn = get_db()

    totals = conn.execute(
        """
        SELECT
            COUNT(*) as total_resolved,
            AVG(
                (d.estimated_prob - CAST(o.resolved_yes AS REAL))
                * (d.estimated_prob - CAST(o.resolved_yes AS REAL))
            ) as avg_brier,
            AVG(
                (d.market_price - CAST(o.resolved_yes AS REAL))
                * (d.market_price - CAST(o.resolved_yes AS REAL))
            ) as avg_market_brier
        FROM decisions d
        JOIN outcomes o ON d.market_id = o.market_id
        WHERE o.resolved_yes IS NOT NULL
        """
    ).fetchone()

    scored_rows = conn.execute(
        """
        SELECT d.bet_direction, d.bet_fraction, d.market_price, o.resolved_yes
        FROM decisions d
        JOIN outcomes o ON d.market_id = o.market_id
        WHERE o.resolved_yes IS NOT NULL
        """
    ).fetchall()

    total_runs = conn.execute(
        "SELECT COUNT(DISTINCT run_date) as n FROM decisions"
    ).fetchone()["n"]

    conn.close()

    cumulative_return = 0.0
    for r in scored_rows:
        direction = r["bet_direction"]
        fraction = r["bet_fraction"]
        price = r["market_price"] if direction == "YES" else 1.0 - r["market_price"]
        won = (r["resolved_yes"] and direction == "YES") or (
            not r["resolved_yes"] and direction == "NO"
        )
        if fraction > 0 and 0 < price < 1:
            cumulative_return += fraction * ((1.0 - price) / price) if won else -fraction

    n = totals["total_resolved"] or 0
    avg_brier = totals["avg_brier"]
    avg_market_brier = totals["avg_market_brier"]
    random_baseline = 0.25

    verdict = None
    if n > 0 and avg_brier is not None:
        if avg_brier < avg_market_brier:
            verdict = "beating_market"
        elif avg_brier < random_baseline:
            verdict = "better_than_random"
        else:
            verdict = "worse_than_random"

    return {
        "total_runs": total_runs,
        "total_resolved": n,
        "avg_brier": avg_brier,
        "avg_market_brier": avg_market_brier,
        "random_baseline": random_baseline,
        "cumulative_return": cumulative_return,
        "verdict": verdict,
    }


@app.get("/logs")
def get_logs(lines: int = Query(default=100, le=500)):
    """Last N lines from bot.log."""
    if not LOG_PATH.exists():
        return {"lines": []}
    with open(LOG_PATH) as f:
        all_lines = f.readlines()
    return {"lines": [l.rstrip() for l in all_lines[-lines:]]}
