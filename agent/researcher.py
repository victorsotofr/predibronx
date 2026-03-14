"""Research context for markets using the LinkUp deep search API."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel

import config
from agent.market_selector import MarketInfo

logger = logging.getLogger(__name__)

LINKUP_BASE = "https://api.linkup.so"
LINKUP_SEARCH = f"{LINKUP_BASE}/v1/search"


class ResearchItem(BaseModel):
    """A single piece of research context."""

    source: str
    content: str
    url: str


class MarketResearch(BaseModel):
    """Research results for a specific market."""

    market_id: str
    market_question: str
    items: list[ResearchItem]
    query_used: str
    resolution_source: str = ""


# Well-known authoritative data providers that Polymarket markets reference.
_KNOWN_SOURCES: list[str] = [
    "USGS",
    "CoinDesk",
    "CoinGecko",
    "Bureau of Labor Statistics",
    "BLS",
    "Federal Reserve",
    "Fed",
    "NOAA",
    "NHC",
    "CDC",
    "WHO",
    "Associated Press",
    "Reuters",
    "AP News",
    "EIA",
    "Treasury Department",
    "European Central Bank",
    "ECB",
    "IMF",
    "World Bank",
    "ESPN",
    "FIFA",
    "UEFA",
    "NBA",
    "NFL",
    "MLB",
    "PGA",
    "ATP",
    "WTA",
    "Kaggle",
    "CoinMarketCap",
    "Metaculus",
]

# Regex patterns that Polymarket descriptions commonly use to indicate the
# resolution source.  Each pattern should have a named group ``source``.
_RESOLUTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"resolution\s+source\s*[:.]\s*(?P<source>[^.\n]+)", re.I),
    re.compile(r"resolved?\s+(?:by|via|using|from|according\s+to)\s+(?P<source>[^.\n]+)", re.I),
    re.compile(r"according\s+to\s+(?P<source>[^.\n]+)", re.I),
    re.compile(r"data\s+(?:from|provided\s+by)\s+(?P<source>[^.\n]+)", re.I),
    re.compile(r"as\s+reported\s+by\s+(?P<source>[^.\n]+)", re.I),
    re.compile(r"source\s+of\s+truth\s*[:.]\s*(?P<source>[^.\n]+)", re.I),
    re.compile(r"official\s+source\s*[:.]\s*(?P<source>[^.\n]+)", re.I),
]


def _extract_resolution_source(description: str) -> str:
    """Try to extract the official resolution source from a market description.

    Returns the source name (trimmed) or an empty string if none found.
    """
    if not description:
        return ""

    # 1. Try regex patterns first (they capture the most context).
    for pattern in _RESOLUTION_PATTERNS:
        m = pattern.search(description)
        if m:
            source = m.group("source").strip().rstrip(".,:;")
            if len(source) > 3:  # avoid noise
                return source

    # 2. Fall back to known source names found verbatim in the description.
    desc_lower = description.lower()
    for name in _KNOWN_SOURCES:
        if name.lower() in desc_lower:
            return name

    return ""


def _build_query(market: MarketInfo, resolution_source: str = "") -> str:
    """Derive a search query from the market title.

    Strips the trailing '?' and adds context keywords for better results.
    If a *resolution_source* is known, it is appended to bias the search
    toward the authoritative data provider.
    """
    q = market.question.rstrip("?").strip()
    base = f"{q} latest news analysis"
    if resolution_source:
        base = f"{base} {resolution_source}"
    return base


async def research_market(
    market: MarketInfo,
    *,
    depth: str = "deep",
    lookback_hours: int = 48,
) -> MarketResearch:
    """Call LinkUp deep search for a single market and return structured results."""
    resolution_source = _extract_resolution_source(market.description)
    if resolution_source:
        logger.info("Detected resolution source '%s' for market %s", resolution_source, market.id)

    query = _build_query(market, resolution_source)
    now = datetime.now(timezone.utc)
    from_date = (now - timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    headers = {"Authorization": f"Bearer {config.LINKUP_API_KEY}"}
    payload = {
        "q": query,
        "depth": depth,
        "outputType": "searchResults",
        "fromDate": from_date,
        "toDate": to_date,
    }

    items: list[ResearchItem] = []
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(LINKUP_SEARCH, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        for result in data.get("results", []):
            items.append(
                ResearchItem(
                    source=result.get("name", "Unknown"),
                    content=result.get("content", ""),
                    url=result.get("url", ""),
                )
            )
    except httpx.HTTPError as exc:
        logger.error("LinkUp search failed for market %s: %s", market.id, exc)

    logger.info("Got %d research items for '%s'", len(items), market.question[:60])
    return MarketResearch(
        market_id=market.id,
        market_question=market.question,
        items=items,
        query_used=query,
        resolution_source=resolution_source,
    )


async def research_markets(markets: list[MarketInfo]) -> list[MarketResearch]:
    """Research all markets concurrently."""
    import asyncio

    tasks = [research_market(m) for m in markets]
    return await asyncio.gather(*tasks)


if __name__ == "__main__":
    import asyncio

    from agent.market_selector import fetch_top_markets

    async def _main() -> None:
        markets = await fetch_top_markets(top_n=2)
        results = await research_markets(markets)
        for r in results:
            print(f"\n{'='*60}")
            print(f"Market: {r.market_question}")
            print(f"Query:  {r.query_used}")
            print(f"Results: {len(r.items)}")
            for item in r.items[:3]:
                print(f"  - [{item.source}] {item.content[:120]}...")

    asyncio.run(_main())
