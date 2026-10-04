# data/reference — transcribed publication inputs (committed)

These files are **manual transcriptions**, not fresh API observations. They make the calculation and local release comparison inspectable. Time-series data lives in `data/raw/` (gitignored; see `data/raw/README.md`). Recorded source provenance is retained below; **the source PDFs were not freshly retrieved or authenticated during this local remediation**.

## `rss-weights.csv` — industry weights, 2017-based vs 2025-based

Recorded source: SingStat Information Paper *"Rebasing of the Retail Sales and Food & Beverage Services Indices (2025=100)"*, March 2026 — Charts 1–2 (values transcribed) and ¶23–24. The paper records the Annual Industry Survey reference year as **2024**. Both weight columns sum to 100.0 (allow ±0.1 for published rounding). "Others" is "Other Retail Trade" in the paper.

- Info paper page: https://www.singstat.gov.sg/publication-resources/re-basing-of-the-retail-sales-and-food-and-beverage-services-indices-2025-100
- PDF retrieval recorded as 2026-10-04; recorded sha256 `064588390b3dd598e3009ac05f6a31386e46ba9c4ef26beb309ef46774269659`

Using these two weight sets with the **same current indices** is a renormalized 11-industry subset sensitivity, not a reconstruction of the 2017-base headline or a measured effect on the published 2025-base total. The subset excludes 13.9% of new weight; linked history and classification changes remain limits.

## `release-2026-07-tables.csv` — dated release-table transcription

Recorded source: SingStat press release *"Monthly Retail Sales Index and Food & Beverage Services Index, Jul 2026"*, published **7 September 2026** — Table 1 (RSI, p.4) and Table 2 (FSI, p.4). All at **current prices**; MoM is seasonally adjusted. `src/audit.py` compares this July transcription with raw Table Builder recomputations; that is a local consistency check, not independent authentication of the release.

- Release page: https://www.singstat.gov.sg/news/monthly-retail-sales-index-and-food-beverage-services-index-jul2026
- PDF retrieval recorded as 2026-10-04; recorded sha256 `9161a2b80e8ff24bb686ddbe30a18ead75893cecb0eba6b95e6cc21bcd266719`

The audit compares full-precision differences with **0.05 pp publication rounding + 0.001 pp index-precision allowance**. Three release-only rows have no current monthly index recomputation and must be `not_recomputed`, not matches. Excl-MV YoY is checked from the value series; its SA MoM is not recomputable here.

The four **transcribed expected July levels/share** checked by the audit are retail S$4,419M, retail excl-MV S$3,679M, F&B S$1,607M and retail online share 15.4%. Their receipt is `outputs/levels_check.csv` (`metric,period,unit,release_value,calc_value,diff,status,source_table`). This check verifies those expectations against Table Builder, not the PDF itself.

## Refresh responsibility

The audit is tied to a `release-YYYY-MM-tables.csv` snapshot, currently July 2026. For a new month, transcribe the matching release, explicitly update the audit's reference selection and level/share expectations, then review narrative, figures and snapshot locks. Latest calculations can advance after a re-pull while this transcription stays July; do not describe that as a fully automatic report refresh. Preserve the July historical test anchor unless the publisher restates it.
