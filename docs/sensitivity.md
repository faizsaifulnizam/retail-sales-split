# Sensitivity — how the July 2026 read moves with the choices

Machine-readable: [`../outputs/sensitivity.csv`](../outputs/sensitivity.csv). Every variant
re-runs the same arithmetic; nothing here is a different data source.

## How to read it

| Choice | Variant | Result (July 2026) |
|---|---|---|
| **Basis** (the big one) | chained volume (repo headline) | **−1.28% YoY** · SA MoM **+0.40%** |
| | current prices (release basis) | **+1.46% YoY** · SA MoM **+0.88%** |
| **MoM window** | SA MoM, 1 month | volume +0.40 · prices +0.88 |
| | SA change, 3 months (Apr → Jul) | volume **+0.51** · prices **−0.39** |
| **Contribution method** | exact, current prices (published formula ΣwᵢLᵢ) | Σ 11 industries **+1.440 pp** vs total +1.458 pp (residual **+0.017**) |
| | approximate, chained volume (chain-linked weights) | Σ **−1.179 pp** vs total −1.281 pp (residual **−0.102**) |
| **Weight set** (rebase) | 2025-based weights | 11-industry basket **+1.66%** |
| | 2017-based weights, same indices | **+1.45%** → weight effect **+0.21 pp** |

## What moves, what holds

- **Basis flips the sign — by construction.** Volume (−1.28%) removes price effects; current
  prices (+1.46%) include them. The divergence *is* the finding: real volumes fell while sales
  values grew. Both are always shown; neither is presented as "the" number alone.
- **The 1-month SA print is noisy; the 3-month read disagrees on prices.** Volume is mildly
  positive on both windows (+0.40 / +0.51); prices flip (+0.88 → −0.39), i.e. July's +0.9%
  SA MoM sits above the recent 3-month trend. A single month is a print, not a trend.
- **Contribution method:** exact on current prices (the published index is literally a weighted
  average of the industry indices; residual +0.017 pp from the three industries without monthly
  data). The volume sum is an approximation by ~0.1 pp because chained volume re-weights
  annually — labelled, never presented as exact.
- **Weight set:** the rebase alone (same industry indices) moves the 11-industry basket by
  +0.21 pp — the weights now lean toward industries that grew (Watches & Jewellery up 2.6 pp)
  and away from one that didn't drag (Motor Vehicles down 3.3 pp). See
  [`../outputs/rebase_read.csv`](../outputs/rebase_read.csv).

## Limits of the variants

The three industries without monthly Table Builder data (Computer & Telecommunications
Equipment, Optical Goods & Books, Others — 13.9% of the 2025 weight) are absent from every
variant's industry sums; their contributions are quoted from the release where needed and
never silently estimated. The rebase counterfactual holds industry indices fixed — SSIC 2025
definitional moves (motorcycles into Motor Vehicles; musical instruments into Recreational
Goods) cannot be undone from published data.
