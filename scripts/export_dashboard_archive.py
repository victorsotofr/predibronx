"""Export a static dashboard archive from the production SQLite database."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TOKEN_PATTERNS = [
    (re.compile(r"bot\d+:[A-Za-z0-9_-]+"), "bot<redacted>"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]+"), "sk-ant-<redacted>"),
]


def redact(line: str) -> str:
    for pattern, replacement in TOKEN_PATTERNS:
        line = pattern.sub(replacement, line)
    return line


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def fetchall(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def fetchone(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def export_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return fetchall(
        conn,
        """
        SELECT
            d.run_date,
            COUNT(*) as n_decisions,
            CASE WHEN SUM(d.bet_fraction) > 0
                 THEN SUM(ABS(d.estimated_prob - d.market_price) * d.bet_fraction) / SUM(d.bet_fraction)
                 ELSE AVG(ABS(d.estimated_prob - d.market_price))
            END as avg_edge,
            AVG(d.confidence) as avg_confidence,
            MAX(ABS(d.estimated_prob - d.market_price)) as max_edge
        FROM decisions d
        GROUP BY d.run_date
        ORDER BY d.run_date DESC
        """,
    )


def export_decisions(conn: sqlite3.Connection, run_date: str) -> list[dict[str, Any]]:
    rows = fetchall(
        conn,
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
    )

    for row in rows:
        raw_edge = row["estimated_prob"] - row["market_price"]
        row["edge"] = raw_edge if row["bet_direction"] == "YES" else -raw_edge

        if row["resolved_yes"] is None:
            row["won"] = None
            row["pnl"] = None
            continue

        direction = row["bet_direction"]
        fraction = row["bet_fraction"]
        price = row["market_price"] if direction == "YES" else 1.0 - row["market_price"]
        resolved = bool(row["resolved_yes"])
        won = (resolved and direction == "YES") or (not resolved and direction == "NO")
        row["won"] = won
        row["pnl"] = fraction * (1.0 - price) / price if won and fraction > 0 and 0 < price < 1 else -fraction
        if not fraction or not (0 < price < 1):
            row["pnl"] = 0.0

    return rows


def export_performance(conn: sqlite3.Connection) -> dict[str, Any]:
    totals = fetchone(
        conn,
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
          AND d.id = (
              SELECT id FROM decisions
              WHERE market_id = d.market_id
              ORDER BY created_at DESC LIMIT 1
          )
        """,
    )
    scored_rows = fetchall(
        conn,
        """
        SELECT d.bet_direction, d.bet_fraction, d.market_price, o.resolved_yes
        FROM decisions d
        JOIN outcomes o ON d.market_id = o.market_id
        WHERE o.resolved_yes IS NOT NULL
          AND d.id = (
              SELECT id FROM decisions
              WHERE market_id = d.market_id
              ORDER BY created_at DESC LIMIT 1
          )
        """,
    )
    total_runs = fetchone(conn, "SELECT COUNT(DISTINCT run_date) as n FROM decisions")["n"]

    cumulative_return = 0.0
    for row in scored_rows:
        direction = row["bet_direction"]
        fraction = row["bet_fraction"]
        price = row["market_price"] if direction == "YES" else 1.0 - row["market_price"]
        won = (row["resolved_yes"] and direction == "YES") or (
            not row["resolved_yes"] and direction == "NO"
        )
        if fraction > 0 and 0 < price < 1:
            cumulative_return += fraction * ((1.0 - price) / price) if won else -fraction

    total_resolved = totals["total_resolved"] or 0
    avg_brier = totals["avg_brier"]
    avg_market_brier = totals["avg_market_brier"]
    random_baseline = 0.25

    verdict = None
    if total_resolved > 0 and avg_brier is not None:
        if avg_brier < avg_market_brier:
            verdict = "beating_market"
        elif avg_brier < random_baseline:
            verdict = "better_than_random"
        else:
            verdict = "worse_than_random"

    return {
        "total_runs": total_runs,
        "total_resolved": total_resolved,
        "avg_brier": avg_brier,
        "avg_market_brier": avg_market_brier,
        "random_baseline": random_baseline,
        "cumulative_return": cumulative_return,
        "verdict": verdict,
    }


def export_logs(log_path: Path, limit: int) -> dict[str, list[str]]:
    if not log_path.exists():
        return {"lines": []}

    lines: list[str] = []
    for raw_line in log_path.read_text(errors="replace").splitlines():
        if "getUpdates" in raw_line or "HTTP Request" in raw_line:
            continue
        lines.append(redact(raw_line.rstrip()))
    return {"lines": lines[-limit:]}


def build_archive(db_path: Path, log_path: Path, log_lines: int) -> dict[str, Any]:
    with connect(db_path) as conn:
        runs = export_runs(conn)
        decisions = {run["run_date"]: export_decisions(conn, run["run_date"]) for run in runs}
        performance = export_performance(conn)

        latest_run = runs[0] if runs else None
        health = {
            "status": "archive",
            "source": "archive",
            "last_run": latest_run["run_date"] if latest_run else None,
            "last_run_decisions": latest_run["n_decisions"] if latest_run else 0,
            "experiment_stopped": True,
        }

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    return {
        "archive_version": 1,
        "generated_at": generated_at,
        "health": health,
        "runs": runs,
        "decisions": decisions,
        "performance": performance,
        "logs": export_logs(log_path, log_lines),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--log-lines", type=int, default=300)
    args = parser.parse_args()

    archive = build_archive(args.db, args.log, args.log_lines)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
