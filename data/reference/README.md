# data/reference — published constants used by the analysis (committed)

These are *published constants* (not pulled time series), transcribed from SingStat
publications so the pipeline and the release cross-check stay auditable. Time-series
data lives in `data/raw/` (gitignored; see `data/raw/README.md`).

## `rss-weights.csv` — industry weights, 2017-based vs 2025-based

Source: SingStat Information Paper *"Rebasing of the Retail Sales and Food & Beverage
Services Indices (2025=100)"*, March 2026 — Charts 1–2 (published as charts; values
transcribed) and ¶23–24 (text confirms the significant moves). The paper states the
weights are computed from the Annual Industry Survey for reference year **2024**.
Both columns sum to 100.0 (±0.1 from publisher rounding). "Others" is labelled
"Other Retail Trade" in the paper.

- Info paper page: https://www.singstat.gov.sg/publication-resources/re-basing-of-the-retail-sales-and-food-and-beverage-services-indices-2025-100
- PDF (retrieved 2026-10-04): sha256 `064588390b3dd598e3009ac05f6a31386e46ba9c4ef26beb309ef46774269659`

## `release-2026-07-tables.csv` — the July 2026 release's own tables (cross-check)

Source: SingStat press release *"Monthly Retail Sales Index and Food & Beverage
Services Index, Jul 2026"*, published **7 September 2026** — Table 1 (RSI, p.4) and
Table 2 (FSI, p.4). All at **current prices**; MoM is seasonally adjusted. Transcribed
for the release cross-check (`src/audit.py` recomputes these from the raw tables and
compares).

- Release page: https://www.singstat.gov.sg/news/monthly-retail-sales-index-and-food-beverage-services-index-jul2026
- PDF (retrieved 2026-10-04): sha256 `9161a2b80e8ff24bb686ddbe30a18ead75893cecb0eba6b95e6cc21bcd266719`
