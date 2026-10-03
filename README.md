<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/banner.svg">
  <img src="assets/banner.svg" width="100%" alt="retail-sales-split — a six-repo series on Singapore's public data">
</picture>

# retail-sales-split

[![CI](https://github.com/faizsaifulnizam/retail-sales-split/actions/workflows/ci.yml/badge.svg)](https://github.com/faizsaifulnizam/retail-sales-split/actions/workflows/ci.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-8A6EAF.svg)](LICENSE) ![Python 3.12](https://img.shields.io/badge/Python-3.12-2E7D6B.svg) ![DuckDB](https://img.shields.io/badge/analytics-DuckDB-22607B.svg) [![data: SingStat Table Builder](https://img.shields.io/badge/data-SingStat%20Table%20Builder-14293D.svg)](https://tablebuilder.singstat.gov.sg/table/TS/M602201) [![dashboard-ready extract](https://img.shields.io/badge/dashboard--ready-extract%20included-8A6EAF.svg)](outputs/tableau_extract.csv)

> **Answer:** The July 2026 retail slowdown is **narrow, and the two lenses disagree**. Real (chained-volume) sales fell **−1.3% year-on-year** while the value headline (current prices, the release's basis) rose **+1.5%**. The split of that +1.5%: **Watches & Jewellery alone contributed +1.21 of the +1.46 points**, with Cosmetics (+0.29), Recreational Goods (+0.24) and Wearing Apparel (+0.24) behind it — against drags from **Supermarkets & Hypermarkets (−0.37; the 16.0% heavyweight is shrinking), Food & Alcohol (−0.23) and Department Stores (−0.14)**. The 2025 rebase cut **Motor Vehicles' weight 18.1% → 14.8%** and raised watches and food & alcohol; holding indices fixed, the weight change alone moves the basket **+0.21 pp** — the rebase nudges the headline *up*, and changes which industries can move it. Retail only; F&B services (−3.3% volume) stay separate.

**Status:** built 2026-10-04. Part of a six-repo series on Singapore's public data.

## Key numbers (all reproducible)

- **Headline (Jul 2026):** chained volume **−1.28% YoY** · SA MoM **+0.40%**; current prices **+1.46% YoY** (release: +1.5%) · SA MoM **+0.88%** (release: +0.9%).
- **The split (current prices, exact):** +1.46% = **Watches & Jewellery +1.21** + Cosmetics +0.29 + Recreational Goods +0.24 + Wearing Apparel +0.24 + Motor Vehicles +0.22 + Furniture +0.09 − Supermarkets −0.37 − Food & Alcohol −0.23 − Dept Stores −0.14 − Petrol −0.05 − Mini-Marts −0.05 (+0.02 residual from three industries not published monthly). Six of eleven industries fell **in volume**.
- **Rebase read:** Motor Vehicles weight **18.1% → 14.8%**; same-index basket under old weights **+1.45%** vs new weights **+1.66%** → **+0.21 pp** from weights alone ([`outputs/rebase_read.csv`](outputs/rebase_read.csv)).
- **Data quality:** 14 Table Builder tables, **35,271/35,271 cells**, 0 exclusions, 13/13 checks; **19/19 release-comparable rows recomputed within ±0.05 pt** of the July 2026 release ([`outputs/release_check.csv`](outputs/release_check.csv)).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="reports/figures/f1_headline-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="reports/figures/f1_headline.png">
  <img src="reports/figures/f1_headline.png" width="100%" alt="July 2026 retail sales: stat cards and history — chained volume vs current prices">
</picture>

*The two lenses side by side: volume fell while values rose, on both the year-on-year and the seasonally-adjusted month-on-month views — with three years of history so one month is not framed alone.*

### More views

| | |
|---|---|
| <a href="reports/figures/f2_split.png"><picture><source media="(prefers-color-scheme: dark)" srcset="reports/figures/f2_split-dark.png"><source media="(prefers-color-scheme: light)" srcset="reports/figures/f2_split.png"><img src="reports/figures/f2_split.png" alt="Ranked industry split — volume vs current prices — with contribution bars"></picture></a> | **The split** — every industry ranked by its volume move, with the exact contribution to the +1.5% beside it ([`docs/decision_memo.md`](docs/decision_memo.md)). |
| <a href="reports/figures/f3_watch.png"><picture><source media="(prefers-color-scheme: dark)" srcset="reports/figures/f3_watch-dark.png"><source media="(prefers-color-scheme: light)" srcset="reports/figures/f3_watch.png"><img src="reports/figures/f3_watch.png" alt="Small multiples — Supermarkets, Watches &amp; Jewellery, Petrol Service Stations"></picture></a> | **Three industries to watch** — the heavyweight (Supermarkets), the carrier (Watches & Jewellery), the diverging one (Petrol: volume −14.5% while its value held). |

*Full size in [`reports/figures/`](reports/figures/) · half-page write-up in [`docs/decision_memo.md`](docs/decision_memo.md) · dashboard-ready extract in [`outputs/tableau_extract.csv`](outputs/tableau_extract.csv) (Tableau Public build is a planned guided step, [`bi/README.md`](bi/README.md)).*

## The question

The monthly retail sales headline is a net number, and a net number hides very different stories: a broad slowdown, or one or two categories dragging the average — or a value number that flatters a shrinking real volume. This repo **splits the latest print by industry**, **quantifies the 2025 rebasing**, and keeps the two bases (chained volume vs current prices) side by side, never conflated. F&B services are a separate index and stay separate here.

## The data

- **Retail Sales Index & F&B Services Index (2025 = 100)** — SingStat Table Builder, 14 tables: RSI chained volume and current prices (monthly + seasonally adjusted), retail sales value (S$M), online-sales proportions, and the quarterly detail tables ([`M602201`](https://tablebuilder.singstat.gov.sg/table/TS/M602201) and friends; full map in [`data/raw/README.md`](data/raw/README.md)). Latest month: **2026 Jul** (publisher stamp 07/09/2026).
- **Weights and the release's own tables** are published constants — transcribed to [`data/reference/`](data/reference/) with provenance (the 2025=100 rebasing info paper, March 2026; the July 2026 release's Tables 1–2).
- **Units:** index 2025=100; value tables in **S$M per month** (retail Jul 2026: S$4,419M; F&B: S$1,607M); online proportions in **%**. A [script](src/download.py) pulls all 14 tables into `data/raw/` (gitignored, SHA-256 + coverage manifest, structure-validated before replace).

## Method

DuckDB reads the raw JSON directly; one tidy monthly table after staging. The pipeline, end to end:

1. **Pull** — 14 tables, structure-validated before replacing files, release-date-stamped manifest: [`src/download.py`](src/download.py)
2. **Audit** — profile, units, SA vs original, and every `[VERIFY]` resolved against live tables + the info paper *before* analysis: [`docs/data_audit.md`](docs/data_audit.md) · [`src/audit.py`](src/audit.py)
3. **Stage** — raw JSON → tidy long → monthly + quarterly tables; every cell accounted for: [`sql/01_staging.sql`](sql/01_staging.sql)
4. **Check** — 13 assertions (coverage, contiguity, ranges, the documented stale gap), run *before* the parquet is written: [`sql/05_checks.sql`](sql/05_checks.sql) — 13/13 pass, 35,271/35,271 cells
5. **Measure** — latest-month YoY + SA MoM per industry, both bases: [`sql/02_metrics.sql`](sql/02_metrics.sql)
6. **Split** — contributions, rebase read, sensitivity: [`src/analysis.py`](src/analysis.py) → [`outputs/latest_split.csv`](outputs/latest_split.csv)
7. **Draw · write** — figures are code, light + dark ([`src/figures.py`](src/figures.py)); the memo ([`docs/decision_memo.md`](docs/decision_memo.md))

### The split, made computable

Three choices make the question answerable. **Two bases, both shown:** the release quotes *current prices* (values, price × quantity); this repo's analytical headline is *chained volume* (price effect removed) — when they disagree (they do, −1.3% vs +1.5%), that disagreement is stated, not hidden. **Contributions where they are exact:** the published index formula is I = Σ wᵢ·Lᵢ (2025-based weights × industry indices), so each industry's contribution = wᵢ·ΔLᵢ ÷ prior-year total — exact on current prices (residual +0.017 pp from the three industries without monthly data). Chained volume re-weights annually (chain-linked), so the same arithmetic there is an **approximation** (~0.1 pp) — labelled a growth-rate split, never presented as exact. **The rebase, quantified:** with both weight sets published, the same industry indices are re-aggregated under 2017 vs 2025 weights — the weight effect alone, +0.21 pp, with the definitional limits stated.

### Rules chosen, and why

| Rule | Choice | Why |
|------|--------|-----|
| Comparison | latest month, **YoY (original) + SA MoM**, never mixed | YoY needs the seasonal pattern; MoM needs it removed — each series used for what it is for |
| Headline basis | **chained volume** primary, current prices beside it | volume answers "did activity fall?"; prices answer "what did the release say?" — both matter |
| Contributions | **exact on current prices**; volume labelled approximate | the published formula is a weighted average on prices; volume is chain-linked (previous-years' weights) |
| Motor Vehicles | called out; weight change quantified | the rebase's biggest weight move (18.1→14.8%) changes how much it can move the headline |
| Missing industries | named, not silently dropped | Computer & Telecom (monthly ends 1996), Optical & Books, Others (quarterly only) — 13.9% of weight; release numbers quoted |
| Retail vs F&B | never combined | two separate indices with separate weights; F&B reported separately, always labelled |
| Outliers | none applied | official aggregates have nothing to trim |
| Forecasts | none | no prediction ships without an error column — so none ships |

### Validation — receipts, not claims

- **13/13 checks** pass; **35,271/35,271 cells** retained, **0 exclusions** (reconciliation printed by [`src/build_dataset.py`](src/build_dataset.py)).
- **Release cross-check:** every recomputable row of the July 2026 release (Tables 1–2) matches within **±0.05 pt** — 19/19 rows (total +1.46 vs +1.5; watches +11.15 vs +11.1; F&B total −1.86 vs −1.9; …), including value levels (S$4,419M vs "$4.4 billion") and online shares (15.4%). Machine-readable: [`outputs/release_check.csv`](outputs/release_check.csv).
- **Contribution identity:** Σ contributions **+1.440 pp** vs published total move **+1.460 pp** — residual **+0.017** (the three industries not published monthly). F&B's own sum reconciles to **0.000 pp**.
- **Independent recompute:** three values recomputed from the raw JSON in plain stdlib — W&J contribution, total prices YoY, total volume YoY — match the pipeline to 1e-6.
- **Determinism:** figures re-render byte-identical; CSVs regenerate identical.
- **Stranger-rerun:** fresh clone → the commands below → reproduces the committed outputs for the 2026-10-04 pull (a later re-pull can move the newest month).

### Limits

**Not a forecast; not a shop; not a causal story.** Industry aggregates cannot name a company, cannot say why a category moved, and cannot separate online from in-store except where the online series says so. The newest month is provisional and can be revised; pre-2026 values are *linked* to the 2025 base (not recalculated), and the rebase's definitional moves (SSIC 2025) are not reversible from published data. The volume-vs-price gap is consistent with modest price growth — not proof of any specific price story. Full list under **Caveats**.

### Principles this repo follows

1. **One question per repo** — the method serves the question, not the reverse.
2. **Define before use** — both bases, the weights, and the contribution formula are defined (and reconciled to the release) before any chart shows them.
3. **SQL first** — the numbers live in `sql/`; Python glues, splits and draws.
4. **Nothing hand-edited** — raw data immutable; every number regenerates from code; the latest month is derived, never hardcoded.
5. **Limits are part of the deliverable.**

## Reproduce

```bash
git clone https://github.com/faizsaifulnizam/retail-sales-split && cd retail-sales-split
uv venv .venv --python 3.12          # or: python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt   # or: pip install -r requirements.txt

python src/download.py       # 14 Table Builder tables → data/raw/ (gitignored; --force to re-pull)
python src/build_dataset.py  # staging + 13 checks → data/processed/*.parquet
python src/audit.py          # profile + release cross-check → outputs/release_check.csv
python src/analysis.py       # the split + rebase read + sensitivity → outputs/
python src/figures.py        # re-renders reports/figures/ (light + dark)
```

Then check `outputs/latest_split.csv`: **Watches & Jewellery** reads contribution **+1.21 pp**, **Supermarkets & Hypermarkets −0.37 pp**, and the Total row **−1.28%** (volume) / **+1.46%** (prices) for July 2026. Data as of the 2026-10-04 pull — a later re-pull can move the newest month.

### Refreshing for next month's release

SingStat releases the RSI/FSI on the **5th of each month** (or the next working day). The refresh is the same four commands: `python src/download.py --force`, then `build_dataset → analysis → figures`. The latest month, all metrics, the extract and the figures re-derive from the data — nothing is hardcoded — and the checks fail loudly if the pull is stale or truncated. (If the publisher ever resumes the monthly Computer & Telecom series, the stale-gap check fires and the analysis note must be updated.)

## Caveats

- **Industry aggregates, not shops** — system totals from SingStat; no company-level reading is possible.
- The newest month is provisional; pre-2026 values are linked to the 2025 base (the info paper's linking coefficient), so pre-2026 levels are as-published under the current base, not as first published.
- Three industries (Computer & Telecom, Optical & Books, Others) have no current monthly Table Builder data; their monthly moves are quoted from the release and excluded from the split (residual +0.017 pp).
- Contributions are exact on current prices; the volume view is a growth-rate split (chain-linked weights, ≈0.1 pp approximation).
- Descriptive only — no forecast, no causal claim. Drivers (prices, tourism, promotions, e-commerce) are out of scope.

## Out of scope

A retail forecast, company-level analysis, a macro consumption model, and dashboards with more than one chart (the Tableau Public build is a planned, separate guided step).

## Licence

Code: MIT. Data: Singapore Open Data Licence — © Singapore Department of Statistics. This is an independent, unofficial analysis.

---

*Part of a six-repo series on Singapore's public data — the other five repos go live as they're built:* **[hdb-resale-mart](https://github.com/faizsaifulnizam/hdb-resale-mart)** · **[card-book-quality](https://github.com/faizsaifulnizam/card-book-quality)** · **coe-quota-premium · coe-category-break · hdb-lease-slope**

*If you found this useful, a star helps others find it.*
