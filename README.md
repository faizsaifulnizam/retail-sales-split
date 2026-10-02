# retail-sales-split

> **Is the latest slowdown in retail sales broad-based — or one or two categories? And does the 2025 rebasing change the headline?**

**Status:** scaffolded — question, data and approach are locked; analysis, figures and reproduce steps pending. Part of a six-repo series on Singapore's public data.

## The question

The monthly retail sales headline is a net number, and a net number can hide very different stories: a broad slowdown, or one or two categories dragging the average. This repo splits the latest print by industry to see who carried it and who dragged it — and checks what the 2025 rebasing of the index did to the picture. Food & beverage services are a separate index and stay separate here.

## The data

- **Retail Sales Index and Food & Beverage Services Index** (2025 = 100) — Singapore Department of Statistics:
  - [Table Builder — Retail Sales Index, 2025=100, chained volume](https://tablebuilder.singstat.gov.sg/table/TS/M602221)
  - [Table Builder — Retail Sales Value, 2025=100](https://tablebuilder.singstat.gov.sg/table/TS/M602171)
  - [Rebasing of the indices (2025=100) — info paper](https://www.singstat.gov.sg/publication-resources/re-basing-of-the-retail-sales-and-food-and-beverage-services-indices-2025-100)
- Licence: Singapore Open Data Licence / SingStat terms. Download the index tables; do not treat a scraped PDF as the source.

## Planned approach

- Headline year-on-year and seasonally-adjusted month-on-month, side by side.
- Industry split for the latest month: gainers and decliners; a contribution view where the tables allow, otherwise stated as a growth-rate split.
- Motor vehicles called out (they move the headline); note the rebase's effect on industry weights.
- One-page note: broad or narrow; two sectors to watch next month; what the index is not (a shop's sales, online vs in-store unless stated, or a forecast).

## Done when

The README figure matches the SingStat release; retail and F&B are never mixed; no forecast without an error column.

## Out of scope

A macro model, a stock call, and dashboards with more than one chart.

## Licence

Code: MIT. Data: Singapore Open Data Licence — © Singapore Department of Statistics. This is an independent, unofficial analysis.

---

*Part of a six-repo series on Singapore's public data.* **The others:** [hdb-resale-mart](https://github.com/faizsaifulnizam/hdb-resale-mart) · [card-book-quality](https://github.com/faizsaifulnizam/card-book-quality) · [coe-quota-premium](https://github.com/faizsaifulnizam/coe-quota-premium) · [coe-category-break](https://github.com/faizsaifulnizam/coe-category-break) · [hdb-lease-slope](https://github.com/faizsaifulnizam/hdb-lease-slope)
