# Tableau Public — Singapore retail: split and rebased

**Published:** [Open the interactive dashboard](https://public.tableau.com/views/SingaporeRetail/Singaporeretailsplitandrebased). The workbook is a fixed snapshot through **July 2026**, not an automatically refreshing data feed.

## What the dashboard shows

- **Retail value versus volume:** separate YoY history panels; the header also reports July SA MoM. Retail and F&B are not combined.
- **Observed-industry contributions:** fixed-2025-weight estimates on linked current-price indices. Eleven observed retail industries cover **86.1%** of new-base weight; the stack is not rescaled to force the headline.
- **Published total, covered estimate and residual:** separate panels retain the incomplete-coverage residual. July is **+0.0174 pp**; June is **+0.7088 pp**. The residual is not the missing industries' measured contribution.
- **Industry picker:** changes only the contribution view. Total and excluding-motor-vehicles aggregate rows are excluded from the industry stack. F&B choices in the shared picker do not add F&B to the Retail-scoped chart.

## Data and aggregation

The upload derives from [`outputs/tableau_extract.csv`](../outputs/tableau_extract.csv) and [`outputs/contribution_reconciliation.csv`](../outputs/contribution_reconciliation.csv), with consecutive-month SA MoM and reconciliation fields added for authoring. The published upload has **2,456 rows**; its downloaded CSV was verified byte-for-byte against the prepared upload.

Repeated published-total, coverage and residual fields must use **AVG or MIN at month/sector grain**, not SUM across industry rows. The published total and residual calculations use AVG scoped to Retail/Total. Null contributions remain unavailable, not zero. Contributions are **percentage points of YoY growth**, not index-point changes.

Fixed-weight calculations on linked indices are approximate, not exact historical contributions under contemporaneous weights, and not a measured rebase effect. The static figures and memo retain the fuller analytical discussion and weight-swap sensitivity.

## Publication checks and editable workbook

- Fresh signed-out browser rendered the complete dashboard, all three populated chart groups, header, picker and legend without visible worksheet/data-source errors.
- Food & Alcohol isolation passed in both the editor and the public viewer: one checked industry and one-item contribution legend, with retail/reconciliation panel labels unchanged. This is a specific filter test, not every possible selection or an all-mark numerical invariance test.
- The published default is All selected. An anonymous packaged-workbook download contained three worksheets, one dashboard, the CSV and Hyper extract, confirming editable persistence. Use Tableau's **Download → Tableau Workbook** to retain an editable copy.
- Desktop fixed layout **1000 × 1400** was inspected. Some long axis/filter/legend labels remain ellipsized; a mobile layout is not certified.

## Refresh boundary

A source re-pull updates calculations, not the dated release transcription, prose, dashboard upload or published workbook automatically. Follow the main README refresh checklist, review coverage/residual history, regenerate the upload and republish after checking the new snapshot. Missing monthly industries remain unavailable, not zero.
