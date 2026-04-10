"""Telegram bot for alerts, commands, and trade approval flow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import config
from agent.evaluator import compute_running_performance

if TYPE_CHECKING:
    from agent.forecaster import ForecastDecision

logger = logging.getLogger(__name__)

# Global state for scheduler pause/resume
_scheduler_paused = False


def is_paused() -> bool:
    return _scheduler_paused


# ── Command handlers ─────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message."""
    await update.message.reply_text(
        "PrediBronx is online.\n\n"
        "Commands:\n"
        "/status — Open positions & P&L\n"
        "/markets — Today's picks with rationale\n"
        "/explain <market_id> — Full reasoning for a market\n"
        "/performance — Running Brier scores & returns\n"
        "/pause — Pause daily scheduler\n"
        "/resume — Resume daily scheduler\n"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — show current state."""
    import sqlite3

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row

    # Latest run's decisions
    row = conn.execute(
        "SELECT run_date, COUNT(*) as n FROM decisions GROUP BY run_date ORDER BY run_date DESC LIMIT 1"
    ).fetchone()

    if row is None:
        await update.message.reply_text("No decisions logged yet.")
        conn.close()
        return

    last_run = row["run_date"]
    n_decisions = row["n"]

    perf = compute_running_performance()
    mode = "LIVE" if config.LIVE_TRADING else "PAPER"
    paused = "PAUSED" if _scheduler_paused else "RUNNING"

    text = (
        f"*Status*\n"
        f"Mode: {mode} | Scheduler: {paused}\n"
        f"Last run: {last_run} ({n_decisions} markets)\n\n"
        f"*Performance*\n"
        f"Resolved: {perf['total_resolved']}\n"
    )
    if perf["avg_brier"] is not None:
        text += (
            f"Avg Brier: {perf['avg_brier']:.4f}\n"
            f"  vs Random: {perf['avg_random_brier']:.4f}\n"
            f"  vs Market: {perf['avg_market_brier']:.4f}\n"
            f"Total Return: {perf['total_return']:.2%}\n"
        )

    conn.close()
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_markets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /markets — show today's picks with rationale."""
    import sqlite3

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT d.market_id, m.title, d.estimated_prob, d.market_price,
               d.bet_direction, d.bet_fraction, d.confidence, d.rationale
        FROM decisions d
        JOIN markets m ON d.market_id = m.id
        WHERE d.run_date = (SELECT MAX(run_date) FROM decisions)
        ORDER BY d.bet_fraction DESC
        """
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No markets evaluated yet.")
        return

    lines = [f"*Today's Picks* ({len(rows)} markets)\n"]
    for i, r in enumerate(rows, 1):
        edge = abs(r["estimated_prob"] - r["market_price"])
        emoji = "+" if r["bet_direction"] == "YES" else "-"
        lines.append(
            f"{i}. `{r['market_id']}`\n"
            f"   *{r['title'][:60]}*\n"
            f"   {emoji}{r['bet_direction']} | "
            f"Mkt: {r['market_price']:.0%} → Est: {r['estimated_prob']:.0%} | "
            f"Edge: {edge:.1%} | Conf: {r['confidence']}/10\n"
            f"   _{r['rationale'][:120]}_\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_explain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /explain <market_id> — full reasoning."""
    import sqlite3

    if not context.args:
        await update.message.reply_text("Usage: /explain <market_id>")
        return

    market_id = context.args[0]
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT d.*, m.title, m.description, m.end_date
        FROM decisions d
        JOIN markets m ON d.market_id = m.id
        WHERE d.market_id = ?
        ORDER BY d.created_at DESC
        LIMIT 1
        """,
        (market_id,),
    ).fetchone()
    conn.close()

    if row is None:
        await update.message.reply_text(f"No decision found for market {market_id}")
        return

    edge = abs(row["estimated_prob"] - row["market_price"])
    text = (
        f"*{row['title']}*\n"
        f"Ends: {row['end_date']}\n\n"
        f"Market price: {row['market_price']:.2%}\n"
        f"Our estimate: {row['estimated_prob']:.2%}\n"
        f"Edge: {edge:.2%}\n"
        f"Direction: {row['bet_direction']}\n"
        f"Bet fraction: {row['bet_fraction']:.4f}\n"
        f"Confidence: {row['confidence']}/10\n\n"
        f"*Rationale:*\n{row['rationale']}\n\n"
        f"_{row['description'][:300]}_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_performance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /performance — running metrics from scored predictions."""
    import sqlite3

    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row

    # Count scored predictions
    row = conn.execute(
        """
        SELECT COUNT(*) as n,
               AVG((d.estimated_prob - (CASE WHEN o.resolved_yes THEN 1.0 ELSE 0.0 END))
                   * (d.estimated_prob - (CASE WHEN o.resolved_yes THEN 1.0 ELSE 0.0 END))) as avg_brier,
               AVG((d.market_price - (CASE WHEN o.resolved_yes THEN 1.0 ELSE 0.0 END))
                   * (d.market_price - (CASE WHEN o.resolved_yes THEN 1.0 ELSE 0.0 END))) as avg_market_brier
        FROM decisions d
        JOIN outcomes o ON d.market_id = o.market_id
        WHERE o.resolved_yes IS NOT NULL
          AND d.id = (
              SELECT id FROM decisions
              WHERE market_id = d.market_id
              ORDER BY created_at DESC LIMIT 1
          )
        """
    ).fetchone()

    n = row["n"] or 0
    if n == 0:
        await update.message.reply_text("No resolved markets scored yet.")
        conn.close()
        return

    avg_brier = row["avg_brier"]
    avg_market_brier = row["avg_market_brier"]
    random_baseline = 0.25  # Brier score of always predicting 0.5

    # Compute cumulative return
    returns_row = conn.execute(
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
        """
    ).fetchall()
    conn.close()

    cumulative_return = 0.0
    for r in returns_row:
        direction = r["bet_direction"]
        fraction = r["bet_fraction"]
        price = r["market_price"] if direction == "YES" else 1.0 - r["market_price"]
        won = (r["resolved_yes"] and direction == "YES") or (not r["resolved_yes"] and direction == "NO")
        if fraction > 0 and 0 < price < 1:
            cumulative_return += fraction * ((1.0 - price) / price) if won else -fraction

    # Verdict
    if avg_brier < avg_market_brier:
        verdict = "✅ Beating the market"
    elif avg_brier < random_baseline:
        verdict = "⚠️ Better than random, worse than market"
    else:
        verdict = "❌ Worse than random"

    text = (
        f"*Performance ({n} scored)*\n\n"
        f"Avg Brier: {avg_brier:.4f}\n"
        f"  vs Random (0.5): {random_baseline:.4f}\n"
        f"  vs Market: {avg_market_brier:.4f}\n\n"
        f"Cumulative Return: {cumulative_return:.2%}\n\n"
        f"{verdict}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pause — stop the daily scheduler."""
    global _scheduler_paused
    _scheduler_paused = True
    await update.message.reply_text("Scheduler paused. Use /resume to restart.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resume — restart the daily scheduler."""
    global _scheduler_paused
    _scheduler_paused = False
    await update.message.reply_text("Scheduler resumed.")


# ── Daily summary ────────────────────────────────────────────────────────────


def format_daily_summary(decisions: list[ForecastDecision]) -> str:
    """Format the daily run results for Telegram."""
    if not decisions:
        return "Daily run complete — no viable markets found."

    # Sort by absolute edge
    ranked = sorted(decisions, key=lambda d: abs(d.estimated_probability - d.market_price), reverse=True)
    top3 = ranked[:3]

    lines = [f"*Daily Run — {len(decisions)} markets evaluated*\n"]
    lines.append("*Top 3 picks:*\n")

    for i, d in enumerate(top3, 1):
        if d.bet_direction == "YES":
            edge = d.estimated_probability - d.market_price
        else:
            edge = d.market_price - d.estimated_probability
        lines.append(
            f"{i}. `{d.market_id}`\n"
            f"   *{d.market_title[:55]}*\n"
            f"   {d.bet_direction} | Mkt: {d.market_price:.0%} → Est: {d.estimated_probability:.0%} "
            f"(edge: {edge:+.1%}) | Conf: {d.confidence}/10\n"
        )

    mode_label = "LIVE" if config.LIVE_TRADING else "PAPER"
    lines.append(f"\n_All {len(decisions)} decisions logged ({mode_label} mode)_")
    if config.DASHBOARD_URL:
        lines.append(f"[View dashboard]({config.DASHBOARD_URL})")
    return "\n".join(lines)


async def send_summary(app: Application, decisions: list[ForecastDecision]) -> None:
    """Send the daily summary message to the configured chat."""
    text = format_daily_summary(decisions)
    await app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")


async def send_approval_request(
    app: Application,
    decision: ForecastDecision,
) -> None:
    """Send a trade approval request with inline buttons (for live mode)."""
    edge = decision.estimated_probability - decision.market_price
    text = (
        f"*Trade Approval*\n\n"
        f"`{decision.market_id}`\n"
        f"*{decision.market_title}*\n"
        f"Direction: {decision.bet_direction}\n"
        f"Market: {decision.market_price:.2%} → Est: {decision.estimated_probability:.2%}\n"
        f"Edge: {edge:+.2%} | Fraction: {decision.bet_fraction:.4f}\n"
        f"Confidence: {decision.confidence}/10\n\n"
        f"Approve this trade?"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"approve:{decision.market_id}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{decision.market_id}"),
            ]
        ]
    )
    await app.bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle approval/rejection button presses."""
    query = update.callback_query
    await query.answer()
    action, market_id = query.data.split(":", 1)

    if action == "approve":
        # Phase 4: trigger actual CLOB execution here
        await query.edit_message_text(f"Trade APPROVED for {market_id}\n_(execution not implemented yet)_")
        logger.info("Trade approved for %s", market_id)
    else:
        await query.edit_message_text(f"Trade REJECTED for {market_id}")
        logger.info("Trade rejected for %s", market_id)


# ── Bot setup ────────────────────────────────────────────────────────────────


def build_app() -> Application:
    """Build and configure the Telegram bot application."""
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("markets", cmd_markets))
    app.add_handler(CommandHandler("explain", cmd_explain))
    app.add_handler(CommandHandler("performance", cmd_performance))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CallbackQueryHandler(handle_approval_callback))

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = build_app()
    print("Starting Telegram bot...")
    app.run_polling()
