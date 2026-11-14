# PrediBronx

An AI forecasting experiment using the Polymarket API, Claude, and web research to test whether an automated system could outperform prediction-market prices.

**Status:** stopped on May 19, 2026. Paper predictions only; live trading was not implemented.

## Results

53 daily runs between March 14 and May 19, 2026 produced 530 decisions across 331 markets. The final evaluation uses the latest decision for each of 195 resolved markets.

| Metric | Result |
|---|---:|
| AI Brier score | 0.1414 |
| Market-price Brier score | 0.1091 |
| Always-50% Brier score | 0.2500 |
| Sum of stake-weighted paper returns | −41.1% |

Lower Brier scores are better. The system beat the always-50% baseline but underperformed market prices. It did not demonstrate a tradable edge. The return figure is a sum of hypothetical returns, not compounded portfolio performance.

The main lesson: overconfident disagreement with the market can outweigh the benefit of useful research. [Results, methodology, and lessons →](docs/results.md)

## How it worked

Polymarket questions → Linkup research → Claude probability estimates → hypothetical bet sizing → SQLite history → Telegram and a web dashboard.

**Stack:** Python · Claude · Linkup · Polymarket Gamma API · SQLite · FastAPI · React.

The dashboard includes a [static archive](dashboard/public/archive.json), so historical results can be viewed without running the forecasting VM or using provider keys.

## Explore

- [Dashboard](https://predibronx.vercel.app)
- [Architecture, setup, and historical operation](docs/setup.md)
- [Evaluation code](agent/evaluator.py)
- Inspired by [PrediBench](https://github.com/PresageLabs/PrediBench).
