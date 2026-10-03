# Data audit — SingStat Retail Sales Index & F&B Services Index (repo 04)

**Files:** 14 SingStat Table Builder exports in `data/raw/` (gitignored), pulled scripted on
**2026-10-04** (`pull_manifest.json` carries SHA-256, rows, coverage, series, `dataLastUpdated`
per table). The publisher's own stamp on every file: **Data Last Updated 07/09/2026** — the
release of the **July 2026** monthly RSI/FSI (embargo lifted 7 Sep 2026, 1.00pm).
Produced with `src/audit.py` (stdlib only — independent of the DuckDB pipeline by design).

## Shape & units (the `[VERIFY]`s, resolved from the live tables)

- **Coverage:** 14 tables; **35,271 cells, 0 non-numeric** (checked cell-by-cell). Monthly
  tables run 1985 Jan → **2026 Jul** (the latest month; the next release is due on the 5th of
  the month); quarterly tables 1985 Q1 → 2026 Q2.
- **Units — stated per the publisher:** index tables = **index (2025 = 100)**; value tables
  (`M602171`, `M602181`) = **S$ millions per month, estimated**; online tables (`M602191`,
  `M602271`) = **% of the industry's total sales**.
- **Two indices, never mixed:** the **RSI** (retail trade) and the **FSI** (F&B services) are
  separate compilations with separate weights; "Food & Alcohol" *inside retail* is a retail
  category, not F&B services. Both are analysed here, always labelled.
- **Two measures per index:** *current prices* (sales values — price × quantity effects) and
  *chained volume* (price effect removed). The monthly **release quotes current prices**;
  this repo's analytical headline is **chained volume** (see the memo for why), shown beside
  the release basis.
- **SA vs original:** seasonally adjusted series are separate tables (`M602202`, `M602122`,
  `M602212`, `M602132`); the original series carry the seasonal pattern. MoM comparisons use
  the SA series only; YoY uses the original series only.

## Industry lists & known gaps

- **Monthly RSI tables** carry 13 rows: Total + 12 industries (Department Stores · Supermarkets
  & Hypermarkets · Mini-Marts & Convenience Stores · Food & Alcohol · Motor Vehicles, Parts &
  Accessories · Petrol Service Stations · Cosmetics, Toiletries & Medical Goods · Wearing
  Apparel & Footwear · Furniture & Household Equipment · Recreational Goods · Watches &
  Jewellery · Computer & Telecommunications Equipment).
- **Monthly F&B tables** carry 6 rows: Total + Restaurants · Fast Food Outlets · Food Caterers ·
  Cafes · Food Courts & Other Eating Places.
- **Gaps (documented, asserted in `sql/05_checks.sql`):**
  1. **Computer & Telecommunications Equipment** in the monthly *index* tables ends **1996 Aug**
     — the publisher does not publish it monthly for recent years (it exists quarterly:
     `M602221`/`M602141` run to 2026 Q2). The release quotes it monthly (+5.1% Jul 2026)
     from tables not in the Table Builder monthly exports. This repo's monthly split therefore
     covers the **11 industries with current monthly data** (86.1% of the 2025 weight).
  2. **Optical Goods & Books** and **Others** are not published monthly at all — quarterly only.
  3. The **excl-MV value series** (`M602171`) starts **2019 Jan** (91 months, no gaps).
  4. A couple of industries start later than 1985 (Dept/Supermarkets 2008; several 1993) —
     irrelevant to the latest-month analysis, recorded in the manifest.
- **No duplicate or missing months anywhere; every series contiguous** (checked).

## The 2025 rebasing (info paper, resolved `[VERIFY]`s)

Source: SingStat Information Paper *"Rebasing of the Retail Sales and Food & Beverage Services
Indices (2025=100)"*, **March 2026**. 8th rebase of the series; released with effect from the
**January 2026** report (published 5 Mar 2026). Weights are computed from the Annual Industry
Survey for reference year **2024**; the new base year is **2025** (index = 100 on average in
2025). Full weights transcribed to `data/reference/rss-weights.csv` (Charts 1–2 of the paper;
both columns sum to 100.0 ±0.1 rounding).

**RSI weights, 2017-based → 2025-based (% of total retail trade):**

| Industry | 2017 | 2025 | Δ pp |
|---|---|---|---|
| Department Stores | 6.2 | 4.3 | −1.9 |
| Supermarkets & Hypermarkets | 14.4 | 16.0 | +1.6 |
| Mini-Marts & Convenience Stores | 4.2 | 3.3 | −0.9 |
| Food & Alcohol | 2.1 | 4.6 | **+2.5** |
| **Motor Vehicles, Parts & Accessories** | **18.1** | **14.8** | **−3.3** |
| Petrol Service Stations | 4.3 | 4.8 | +0.5 |
| Cosmetics, Toiletries & Medical Goods | 6.2 | 6.6 | +0.4 |
| Wearing Apparel & Footwear | 9.8 | 10.9 | +1.1 |
| Furniture & Household Equipment | 7.5 | 7.3 | −0.2 |
| Recreational Goods | 1.5 | 1.9 | +0.4 |
| Watches & Jewellery | 9.0 | 11.6 | **+2.6** |
| Computer & Telecommunications Equipment | 5.5 | 6.3 | +0.8 |
| Optical Goods & Books | 2.9 | 2.0 | −0.9 |
| Others ("Other Retail Trade" in the paper) | 8.2 | 5.6 | −2.6 |

**FSI weights:** Restaurants **41.2 → 47.3**; Fast Food Outlets 12.7 → 9.8; Food Caterers
11.4 → 10.2; Cafes 10.6 → 10.0; Food Courts & Other Eating Places 24.1 → 22.7.

**Definitional moves (SSIC 2025, not just weights):** motorcycles/scooters, tyres & batteries,
and parts & accessories moved into the renamed **Motor Vehicles, Parts & Accessories** group;
musical instruments moved from Furniture to **Recreational Goods**; the FSI group "Cafes, Food
Courts & Other Eating Places" was **split** into Cafes and Food Courts & Other Eating Places.

**Old-vs-new comparability — the publisher's stated position:** the 2017-based series is
**linked** to the 2025-based series with a linking coefficient (ratio of the average 2025-based
index in 2025 to the average 2017-based index in 2025; the paper's worked example: 104.1 ×
100.0/107.0 = 97.3). So **pre-2026 values in the current tables are linked values** — coherent
for growth rates, but they are not the numbers as originally published, and the full old-base
series is no longer published. Comparisons of the same month under old vs new base are therefore
done here via the **weight-swap counterfactual** (`outputs/rebase_read.csv`): the same industry
indices re-aggregated under 2017 weights vs 2025 weights — quantifying the weights' effect only,
with the SSIC definitional moves stated as a limit (they cannot be undone from published data).

## Release cross-check — recomputed vs the July 2026 release

The release's own tables (Table 1 RSI, Table 2 FSI, both at current prices) are transcribed in
`data/reference/release-2026-07-tables.csv`; `src/audit.py` recomputes every comparable row from
the raw tables. **All 19 comparable rows match within ±0.05 pt** (release rounds to 0.1 pt):

| Row | release YoY | recomputed | Row | release SA MoM | recomputed |
|---|---|---|---|---|---|
| Total | +1.5 | +1.46 | Total | +0.9 | +0.88 |
| Total excl MV | +1.5 | +1.49 (value row) | Total excl MV | +0.7 | n/a (no SA value series) |
| Department Stores | −3.5 | −3.49 | Department Stores | +4.6 | +4.56 |
| Supermarkets & Hypermarkets | −2.1 | −2.12 | Supermarkets & Hypermarkets | +4.3 | +4.26 |
| Mini-Marts & Convenience Stores | −1.5 | −1.45 | Mini-Marts | −1.1 | −1.08 |
| Food & Alcohol | −5.1 | −5.08 | Food & Alcohol | −4.5 | −4.48 |
| Motor Vehicles, Parts & Accessories | +1.4 | +1.35 | Motor Vehicles | +2.1 | +2.06 |
| Petrol Service Stations | −1.1 | −1.05 | Petrol | −7.2 | −7.17 |
| Cosmetics, Toiletries & Medical Goods | +4.5 | +4.49 | Cosmetics | −2.7 | −2.68 |
| Wearing Apparel & Footwear | +2.3 | +2.28 | Wearing Apparel | +1.6 | +1.59 |
| Furniture & Household Equipment | +1.3 | +1.26 | Furniture | +0.2 | +0.15 |
| Recreational Goods | +13.9 | +13.92 | Recreational Goods | +7.5 | +7.51 |
| Watches & Jewellery | +11.1 | +11.15 | Watches & Jewellery | +4.0 | +4.03 |
| F&B Total | −1.9 | −1.86 | F&B Total | +0.6 | +0.63 |
| F&B Restaurants | −0.3 | −0.26 | F&B Restaurants | +0.4 | +0.41 |
| F&B Fast Food Outlets | +4.6 | +4.56 | F&B Fast Food | +5.8 | +5.78 |
| F&B Food Caterers | +0.3 | +0.27 | F&B Caterers | +1.4 | +1.45 |
| F&B Cafes | −6.4 | −6.42 | F&B Cafes | −0.1 | −0.14 |
| F&B Food Courts & Other Eating Places | −6.6 | −6.56 | F&B Food Courts | −1.3 | −1.30 |

Not recomputable from Table Builder monthly exports (release-only rows, quoted as context):
Computer & Telecommunications Equipment (+5.1 / −4.7), Optical Goods & Books (−2.2 / +0.3),
Others (−4.0 / −0.1). The machine-readable version of this table is
[`../outputs/release_check.csv`](../outputs/release_check.csv).

**Also cross-checked:** value levels — retail **S$4,419M** in Jul 2026 (release: "$4.4 billion";
excl-MV **S$3,679M** vs "$3.7 billion"); F&B **S$1,607M** vs "$1.6 billion"; online shares —
retail 15.4% (release: 15.4%), F&B 20.9% (release: 20.9%).

## Contribution reconciliation (weights × index moves)

The published index formula is I = Σ wᵢ·Lᵢ (weights × industry indices). Recomputing the
July 2026 total move from the 11 monthly-published industries: **Σ contributions = +1.443 index
pts vs the published total move +1.460 pts — residual +0.017 pts** (the three industries not
published monthly + rounding). This is what makes the contribution view defensible on current
prices; the chained-volume series is chain-linked (previous years' weights) and its 11-industry
sum differs by ~0.1 pts — so volume stays a growth-rate split, stated as such.

## Rules chosen, before analysis (from the profile above)

1. **Latest month = 2026 Jul** (the newest published); YoY = Jul 2026 vs Jul 2025 (original
   series); MoM = Jul vs Jun 2026 (SA series only). Nothing hardcoded — the month is derived
   from the data; the refresh recipe re-derives it.
2. **Chained volume is the analytical headline**; current prices (the release basis) shown
   beside it — never mixed, both labelled.
3. **Contribution view on current prices only** (formula exact, residual +0.017 pts); the
   volume split is labelled a growth-rate split (chain-linked weights).
4. **Retail and F&B never combined**; F&B analysed separately with its own weights.
5. **No outlier rules** — official aggregates; nothing to trim. **No forecasts.**
6. Monthly split covers the 11 industries with current monthly data; the three release-only /
   quarterly-only industries are named, never silently dropped.
