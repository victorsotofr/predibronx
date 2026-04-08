"""Generate probability estimates and bet sizing using Claude."""

from __future__ import annotations

import json
import logging
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
Reason privately and output only the final answer.

Given a market question, its current price, description, and recent research, estimate the
true probability that the market resolves YES.

Critical rule: check the market's official resolution source.
- If the supplied research verifies the claim directly against that source, proceed normally.
- If it does not, say so in the rationale, cap confidence at 4/10, and keep the estimate
  within 5 percentage points of the current market price.

Return exactly one JSON object and nothing else. No bullets, no prose, no markdown fence.
Schema:
{
  "estimated_probability": <float 0.0-1.0>,
  "confidence": <int 0-10>,
  "resolution_source_verified": <boolean>,
  "rationale": "<2-3 sentence explanation mentioning the resolution source and whether you verified it.>"
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


def _strip_code_fences(text: str) -> str:
    """Remove common markdown fences before JSON parsing."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _extract_json_object(text: str) -> dict | None:
    """Parse a JSON object from raw model text when possible."""
    cleaned = _strip_code_fences(text)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start == -1:
        return None

    depth = 0
    for idx in range(start, len(cleaned)):
        char = cleaned[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : idx + 1]
                try:
                    parsed = json.loads(candidate)
                    return parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _repair_forecast_payload(raw_text: str, market: MarketInfo) -> dict | None:
    """Ask Claude to convert a non-JSON answer into the required schema."""
    repair_prompt = f"""\
Convert the following forecast answer into exactly one valid JSON object.

Rules:
- Return only JSON, with no markdown fencing.
- Keep the schema exactly:
  {{"estimated_probability": <float>, "confidence": <int>, "resolution_source_verified": <boolean>, "rationale": <string>}}
- If the answer does not clearly state a value, infer conservatively.
- Clamp estimated_probability to [0.0, 1.0].
- Confidence must be an integer from 0 to 10.

Market ID: {market.id}
Market question: {market.question}
Current market price: {market.yes_price:.4f}

Answer to convert:
{raw_text}
"""
    repaired = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=256,
        system="Return exactly one valid JSON object and nothing else.",
        messages=[{"role": "user", "content": repair_prompt}],
    )
    return _extract_json_object(repaired.content[0].text)


async def forecast_market(market: MarketInfo, research: MarketResearch) -> ForecastDecision:
    """Generate a forecast for a single market using Claude."""
    user_prompt = _build_user_prompt(market, research)

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = message.content[0].text.strip()
    result = _extract_json_object(raw_text)
    if result is None:
        logger.warning(
            "Non-JSON forecast response for %s (stop_reason=%s); attempting repair",
            market.id,
            message.stop_reason,
        )
        result = _repair_forecast_payload(raw_text, market)

    if result is None:
        logger.error("Failed to parse Claude response for %s: %s", market.id, raw_text[:200])
        result = {
            "estimated_probability": market.yes_price,
            "confidence": 0,
            "resolution_source_verified": False,
            "rationale": "Parse error",
        }

    est_prob = float(result["estimated_probability"])
    est_prob = max(0.01, min(0.99, est_prob))  # Clamp extremes
    confidence = max(0, min(10, int(result.get("confidence", 5))))
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

    # Zero-out: do not bet at all when confidence is too low
    if confidence < 5 and fraction > 0:
        logger.info(
            "Zeroing bet for %s — confidence %d/10 too low (would have been %.6f)",
            market.id, confidence, fraction,
        )
        fraction = 0.0

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
