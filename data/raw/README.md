# data/raw — raw files are never edited or committed

**Source:** Retail Sales Index & Food & Beverage Services Index (2025=100) — Singapore Department of Statistics, via the SingStat Table Builder public API (`https://tablebuilder.singstat.gov.sg/api/table/tabledata/<id>`, no key).
**Licence:** Singapore Open Data Licence / SingStat terms. This is an independent, unofficial analysis.
**Fetched by:** `src/download.py` (structure-validated before replace; SHA-256 + coverage + `dataLastUpdated` in `pull_manifest.json`).

**The 14 managed tables (all 2025=100):**

| Table | Content | Role |
|---|---|---|
| `M602201` | RSI, chained volume, monthly | **primary headline + industry split** |
| `M602202` | RSI, chained volume, monthly, seasonally adjusted | SA MoM |
| `M602121` | RSI, current prices, monthly | release basis (cross-check) |
| `M602122` | RSI, current prices, monthly, SA | release SA MoM |
| `M602171` | Retail sales value, S$M, monthly | levels; excl-MV value series |
| `M602191` | Online retail sales proportion, monthly | context |
| `M602141` / `M602221` | RSI, current prices / chained volume, quarterly | Optical, Others, excl-MV detail |
| `M602211` / `M602212` | F&B services, chained volume, monthly (+SA) | F&B (kept separate) |
| `M602131` / `M602132` | F&B services, current prices, monthly (+SA) | F&B (kept separate) |
| `M602181` | F&B sales value, S$M, monthly | F&B levels |
| `M602271` | Online F&B sales proportion, monthly | context |

**Pull (2026-10-04):** all 14 tables report publisher stamp **Data Last Updated 07/09/2026** (the July 2026 monthly release; releases continue on the 5th of each month). Latest month in the data: **2026 Jul**. To refresh: `python src/download.py --force` then re-run the pipeline (see README → Reproduce).
**Published constants** used by the analysis (weights, the release's own tables) live in `../reference/` (committed, with provenance).
