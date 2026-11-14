# Experiment results and lessons

[← PrediBronx](../README.md)

## Experiment result: no tradable edge

The paper experiment recorded **53 daily runs** between **2026-03-14** and **2026-05-19**. It logged **530 paper decisions** across **331 unique markets**. The archive contains **234 decisions with known outcomes**, covering **195 distinct resolved markets**. Aggregate results below use the latest decision for each resolved market, as of **2026-05-19**.

| Metric | PrediBronx | Baseline |
|---|---:|---:|
| Average Brier score | **0.1414** | Market price: **0.1091** |
| Random Brier baseline | **0.2500** | Always predict 50% |
| Sum of stake-weighted paper returns | **-41.1%** | Latest decision per resolved market |

The return metric sums stake-weighted returns across the 195 latest resolved-market decisions; it is not a compounded portfolio equity curve. The figures can be reproduced from [`dashboard/public/archive.json`](../dashboard/public/archive.json), selecting the latest `run_date` per market, using the calculations in [`agent/evaluator.py`](../agent/evaluator.py).

The result was clear: PrediBronx was better than random, but worse than simply using the market price. It did not show a tradable edge.

The main failure mode was not broad randomness. It was **overconfident disagreement with the market**, especially on high-edge YES calls. Predictions with estimated probability >=85% resolved YES only 63.2% of the time and contributed about -61.0 percentage points of P&L. Confidence did not reliably protect the system: confidence 7+ calls had the worst Brier bucket and contributed about -49.7 percentage points. Directionally, YES bets were the weak side, while NO bets were positive.

## Interpretation: the market was the baseline to beat

Prediction markets are not just data sources; they are information aggregation mechanisms. Polymarket's [prices and order books](https://docs.polymarket.com/concepts/prices-orderbook) come from peer-to-peer supply and demand in a CLOB, and the displayed price is intended to represent the market's probability estimate. Classic prediction-market research makes the same point more generally: prices can compress dispersed beliefs and information into a forecast, while also requiring care because prices are not perfect truth and can be distorted by liquidity, incentives, risk preferences, and market design ([Wolfers and Zitzewitz](https://www.aeaweb.org/articles?id=10.1257%2F0895330041371321), [Manski](https://www.nber.org/papers/w10359)).

That matters for an AI bot. If the information LinkUp retrieves is public and already salient to traders, then search may improve the explanation without creating new edge. In many markets, PrediBronx was probably rediscovering information already embedded in the price, then occasionally adding brittle interpretation on top. The hard problem was not "can the model find relevant facts?" It was "can the model add incremental information, better calibration, or faster interpretation than the market?"

My takeaway: the market price is the first model to beat. A future version would need a real source of advantage: deeper multi-source retrieval, better parsing of market resolution rules, faster reaction to new information, calibrated rejection of extreme edges, or empirical evidence that a specific class of markets is systematically mispriced.

## Paper mode, not market making

PrediBronx did **not** execute live trades, post quotes, or provide liquidity on the Polymarket CLOB. It was a paper forecaster: it observed the market price, generated a probability estimate, sized a hypothetical bet with quarter-Kelly, logged the decision, and scored it after resolution.

That makes the negative result stronger. The reported -41.1% return is before real execution frictions such as spread, slippage, order-fill uncertainty, liquidity constraints, and operational risk. The strategy failed before it had to survive live trading.

