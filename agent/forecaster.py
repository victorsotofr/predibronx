"""Generate probability estimates and bet sizing using Claude."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass

import anthropic

import config
from agent.market_selector import MarketInfo
from agent.researcher import MarketResearch

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


@dataclass
class ForecastDecision:
    """Output of the forecaster for a single market."""

    market_id: str
    market_title: str
    market_price: float  # Current YES probability from market
    estimated_probability: float  # Our estimate of YES probability
    bet_direction: str  # "YES" or "NO"
    bet_fraction: float  # 0–1, fraction of per-market budget
    confidence: int  # 0–10
    rationale: str


SYSTEM_PROMPT = """\
You are a superforecaster making predictions on binary prediction markets.

Your task: given a market question, its current price, description, and recent research, \
estimate the TRUE probability that the market resolves YES.

Follow this process:
1. **Decompose** the question into key factors
2. **Resolution Source Check** (CRITICAL):
   - Extract the official Resolution Source from the market description (e.g. USGS, \
CoinDesk, BLS, AP News, government data portals, etc.).
   - Determine whether the research you received contains data **directly from** that \
resolution source, or only from mainstream media / secondary reporting.
   - If you can verify the claim using the official resolution source, proceed normally.
   - If you CANNOT find data from the official resolution source and only have \
mainstream media reports, you MUST:
     a) Flag this in your rationale (e.g. "Could not verify via [source]").
     b) Significantly reduce your confidence (at most 4/10).
     c) Pull your estimated_probability toward the current market price \
(i.e. do NOT deviate more than 5 percentage points from the market price).
   - This rule exists because media outlets frequently misreport precise figures \
(magnitudes, statistics, scores) that differ from the official resolution source.
3. **Base rate**: What is the historical base rate for events like this?
4. **Evidence update**: How does the research context shift the probability?
5. **Calibration check**: Is your estimate overconfident? Adjust toward the base rate.
6. **Edge assessment**: Compare your estimate to the market price. Only bet when you have genuine edge.

Respond ONLY with valid JSON (no markdown fencing):
{
  "estimated_probability": <float 0.0-1.0>,
  "confidence": <int 0-10>,
  "resolution_source_verified": <boolean>,
  "rationale": "<2-3 sentence explanation. MUST mention the resolution source and whether you verified it.>"
}
"""


def _build_user_prompt(market: MarketInfo, research: MarketResearch) -> str:
    """Build the user prompt with market context and research."""
    research_text = ""
    if research.items:
        research_entries = []
        for item in research.items[:8]:  # Limit to avoid token bloat
            entry = f"[{item.source}] {item.content[:500]}"
            if item.url:
                entry += f"\nSource: {item.url}"
            research_entries.append(entry)
        research_text = "\n\n".join(research_entries)
    else:
        research_text = "(No recent research found)"

    return f"""\
## Market
**Question:** {market.question}
**Current YES price:** {market.yes_price:.2%}
**Ends:** {market.end_date}

## Description
{market.description[:2000] if market.description else "(No description)"}

## Resolution Source
{f'Detected resolution source: **{research.resolution_source}**. You MUST verify your findings against this source.' if research.resolution_source else '(No specific resolution source detected — check the description carefully for any mention of an official data provider.)'}

## Recent Research (last 48h)
{research_text}

Analyze this market and provide your probability estimate as JSON.
"""


def _kelly_bet_fraction(estimated_prob: float, market_price: float) -> tuple[str, float]:
    """Compute quarter-Kelly bet fraction and direction.

    Returns (direction, fraction) where fraction is capped by MAX_BET_FRACTION.
    """
    # Determine if we bet YES or NO
    if estimated_prob > market_price:
        # Edge on YES side
        direction = "YES"
        p = estimated_prob
        odds = (1.0 / market_price) - 1.0  # Decimal odds - 1
    elif estimated_prob < market_price:
        # Edge on NO side
        direction = "NO"
        p = 1.0 - estimated_prob
        odds = (1.0 / (1.0 - market_price)) - 1.0
    else:
        return "YES", 0.0  # No edge

    if odds <= 0:
        return direction, 0.0

    # Kelly criterion: f* = (bp - q) / b where b=odds, p=prob of winning, q=1-p
    q = 1.0 - p
    kelly = (odds * p - q) / odds
    kelly = max(kelly, 0.0)

    # Quarter-Kelly, capped at MAX_BET_FRACTION
    fraction = config.KELLY_FRACTION * kelly
    fraction = min(fraction, config.MAX_BET_FRACTION)

    return direction, round(fraction, 6)


async def forecast_market(market: MarketInfo, research: MarketResearch) -> ForecastDecision:
    """Generate a forecast for a single market using Claude."""
    user_prompt = _build_user_prompt(market, research)

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Parse response
    raw_text = message.content[0].text.strip()
    # Strip potential markdown code fences
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response for %s: %s", market.id, raw_text[:200])
        result = {"estimated_probability": market.yes_price, "confidence": 0, "rationale": "Parse error"}

    est_prob = float(result["estimated_probability"])
    est_prob = max(0.01, min(0.99, est_prob))  # Clamp extremes
    confidence = int(result.get("confidence", 5))
    rationale = result.get("rationale", "")
    source_verified = bool(result.get("resolution_source_verified", True))

    if not source_verified:
        logger.warning(
            "Resolution source NOT verified for market %s — agent flagged low confidence",
            market.id,
        )

    direction, fraction = _kelly_bet_fraction(est_prob, market.yes_price)

    # Scale down further if low confidence
    if confidence < 3:
        fraction *= 0.25
    elif confidence < 5:
        fraction *= 0.5

    decision = ForecastDecision(
        market_id=market.id,
        market_title=market.question,
        market_price=market.yes_price,
        estimated_probability=est_prob,
        bet_direction=direction,
        bet_fraction=round(fraction, 6),
        confidence=confidence,
        rationale=rationale,
    )
    logger.info(
        "Forecast: %s → p=%.2f (mkt=%.2f) dir=%s frac=%.4f conf=%d",
        market.question[:40],
        est_prob,
        market.yes_price,
        direction,
        fraction,
        confidence,
    )
    return decision


async def forecast_all(
    markets: list[MarketInfo],
    research: list[MarketResearch],
) -> list[ForecastDecision]:
    """Forecast all markets. Run sequentially to respect rate limits."""
    research_by_id = {r.market_id: r for r in research}
    decisions: list[ForecastDecision] = []
    for market in markets:
        r = research_by_id.get(market.id)
        if r is None:
            logger.warning("No research for market %s, skipping", market.id)
            continue
        decision = await forecast_market(market, r)
        decisions.append(decision)
    return decisions


if __name__ == "__main__":
    import asyncio

    from agent.market_selector import fetch_top_markets
    from agent.researcher import research_markets

    async def _main() -> None:
        markets = await fetch_top_markets(top_n=2)
        research = await research_markets(markets)
        decisions = await forecast_all(markets, research)
        for d in decisions:
            print(f"\n{'='*60}")
            print(f"Market: {d.market_title}")
            print(f"Price: {d.market_price:.2%} → Our est: {d.estimated_probability:.2%}")
            print(f"Direction: {d.bet_direction}  Fraction: {d.bet_fraction:.4f}  Conf: {d.confidence}")
            print(f"Rationale: {d.rationale}")

    asyncio.run(_main())
