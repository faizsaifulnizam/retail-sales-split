# Sensitivity — how the July 2026 read moves with the choices

Machine-readable: [`../outputs/sensitivity.csv`](../outputs/sensitivity.csv). These variants use the same source snapshot; they are not independent datasets.

## How to read it

| Choice | Variant | Result (July 2026) |
|---|---|---|
| **Basis** | chained volume | **−1.28% YoY** · SA MoM **+0.40%** |
| | current-price value | **+1.46% YoY** · SA MoM **+0.88%** |
| **SA window** | 1-month change | volume **+0.40%** · value **+0.88%** |
| | cumulative 3-month change (Apr → Jul), not a monthly average | volume **+0.51%** · value **−0.39%** |
| **Contribution calculation** | fixed weights, current prices | covered sum **+1.4404 pp** vs total growth +1.4578%; residual **+0.0174 pp** |
| | approximate, chained volume | covered sum **−1.179 pp** vs total growth −1.281%; residual **−0.102 pp** |
| **Weight set** | 2025 weights, renormalized 11-industry subset | **+1.66%** |
| | 2017 weights, same current indices and subset | **+1.45%** → difference **+0.21 pp** |

## What moves, what holds

- **Basis changes the sign.** Price-adjusted volume fell while current-price sales value grew. Neither is a customer count. The implied value/volume growth ratio is an aggregate implicit deflator (+2.77%), not CPI or evidence about particular consumers.
- **Both 1-month SA rates are positive; the 3-month value change is negative.** The different windows show why one month should not be treated as a trend. The Apr→Jul change is cumulative, not a rolling monthly average or proof of a persistent trend.
- **Contribution arithmetic is not a complete headline identity.** July's covered value sum leaves a small residual, but June's **+3.3093 pp** covered sum versus **+4.0182%** total leaves **+0.7088 pp**. May 2026 residual is **+0.3201 pp**; July 2025 is **+0.4390 pp**. Historical series are linked; using current base weights does not reconstruct exact old-base contributions. See [`../outputs/contribution_reconciliation.csv`](../outputs/contribution_reconciliation.csv) for coverage and residuals.
- **The volume residual is not an error bound.** Fixed weights applied to chain-linked indices are approximate. Missing industries, chain linking and rounding can all contribute to the difference; July's roughly −0.10 pp residual does not guarantee ±0.1 pp accuracy in other months.
- **Weight swap is a subset sensitivity.** It raises the calculated growth of the same observed basket by +0.21 pp. It does not establish a +0.21 pp effect on the published +1.46% headline or reconstruct the 2017-base headline. Motor Vehicles' weight fell 3.3 pp, watches' rose 2.6 pp; the calculation holds current indices fixed rather than isolating all rebase changes.

## Limits of the variants

Computer & Telecommunications Equipment, Optical Goods & Books and Others have no current monthly index data in these exports. They represent **13.9% of the 2025 weight** and are absent from covered contribution sums and the rebase subset; release growth rates are context only, not estimated contributions. Total headline and SA-window variants use the published **full total**, not the subset.

The weight-swap ratio renormalizes the covered industries separately under each weight set. Pre-2026 values are linked; SSIC 2025 classification moves (including motorcycles into Motor Vehicles and musical instruments into Recreational Goods) cannot be reversed here. Coverage, linking and rounding mean the residual cannot be identified as the missing industries' contribution alone. Growth contributions are in **pp**, not weighted **index-point changes**. The new-month transcription, narrative and snapshot checks require explicit review; a re-pull is not enough.
