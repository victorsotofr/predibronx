"""Fetch and filter top markets from the Polymarket Gamma API."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
GAMMA_MARKETS = f"{GAMMA_BASE}/markets"
GAMMA_EVENTS = f"{GAMMA_BASE}/events"


class MarketInfo(BaseModel):
    """Slim representation of a Polymarket market for downstream use."""

    id: str
    question: str
    description: str = ""
    end_date: str  # ISO-8601
    category: str = ""
    volume: float = 0.0
    liquidity: float = 0.0
    yes_price: float = 0.5
    clob_token_ids: list[str] = Field(default_factory=list)


def _parse_market(raw: dict[str, Any]) -> MarketInfo | None:
    """Convert a raw Gamma API market dict into a MarketInfo, or None if invalid."""
    end_date_str = raw.get("endDate") or raw.get("end_date_iso") or ""
    if not end_date_str:
        return None

    try:
        # Gamma returns ISO strings like "2025-06-30T00:00:00Z"
        end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    # Parse outcome prices — Gamma returns a JSON string like "[\"0.55\",\"0.45\"]"
    import json

    yes_price = 0.5
    raw_prices = raw.get("outcomePrices", "")
    if isinstance(raw_prices, str) and raw_prices:
        try:
            prices = json.loads(raw_prices)
            yes_price = float(prices[0])
        except (json.JSONDecodeError, IndexError, ValueError):
            pass
    elif isinstance(raw_prices, list) and raw_prices:
        try:
            yes_price = float(raw_prices[0])
        except (ValueError, IndexError):
            pass

    clob_ids: list[str] = []
    raw_clob = raw.get("clobTokenIds", "")
    if isinstance(raw_clob, str) and raw_clob:
        try:
            clob_ids = json.loads(raw_clob)
        except json.JSONDecodeError:
            pass
    elif isinstance(raw_clob, list):
        clob_ids = [str(t) for t in raw_clob]

    return MarketInfo(
        id=str(raw.get("id", "")),
        question=raw.get("question", ""),
        description=raw.get("description", ""),
        end_date=end_dt.date().isoformat(),
        category=raw.get("groupItemTitle", "") or raw.get("category", "") or "",
        volume=float(raw.get("volume", 0) or 0),
        liquidity=float(raw.get("liquidity", 0) or 0),
        yes_price=yes_price,
        clob_token_ids=clob_ids,
    )


def _is_crypto(market: MarketInfo) -> bool:
    """Check if a market is crypto-related by category or keywords."""
    text = f"{market.category} {market.question}".lower()
    crypto_terms = {"crypto", "cryptocurrency", "bitcoin", "btc", "ethereum", "eth", "solana", "sol"}
    return any(term in text for term in crypto_terms)


async def fetch_top_markets(
    top_n: int = config.TOP_MARKETS,
    max_end_days: int = config.MAX_END_DAYS,
) -> list[MarketInfo]:
    """
    Fetch active markets from Gamma API, filter and rank them.

    Filters:
    - Active + not closed + not archived
    - Has order book enabled
    - Resolves within `max_end_days`
    - Not crypto-related
    - Sorted by volume descending, return top N
    """
    cutoff = date.today() + timedelta(days=max_end_days)
    all_markets: list[MarketInfo] = []
    offset = 0
    limit = 100

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict[str, Any] = {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "enableOrderBook": "true",
                "limit": limit,
                "offset": offset,
                "order": "volume",
                "ascending": "false",
            }
            resp = await client.get(GAMMA_MARKETS, params=params)
            resp.raise_for_status()
            batch = resp.json()

            if not batch:
                break

            for raw in batch:
                m = _parse_market(raw)
                if m is None:
                    continue
                # Filter: ends within window
                try:
                    end = date.fromisoformat(m.end_date)
                except ValueError:
                    continue
                if end > cutoff or end < date.today():
                    continue
                # Filter: not crypto
                if _is_crypto(m):
                    continue
                all_markets.append(m)

            # Stop early once we have enough candidates or hit end of results
            if len(batch) < limit or len(all_markets) >= top_n * 5:
                break
            offset += limit

    # Sort by volume descending, take top N
    all_markets.sort(key=lambda m: m.volume, reverse=True)
    selected = all_markets[:top_n]
    logger.info("Selected %d markets from %d candidates", len(selected), len(all_markets))
    return selected


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        markets = await fetch_top_markets()
        for i, m in enumerate(markets, 1):
            print(f"{i:2}. [{m.yes_price:.0%}] {m.question}")
            print(f"    vol={m.volume:,.0f}  ends={m.end_date}  cat={m.category}")

    asyncio.run(_main())
