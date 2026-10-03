-- 01_staging.sql — raw SingStat Table Builder JSON -> staged tables.
-- Run by src/build_dataset.py (DuckDB reads data/raw/tb-*.json directly).
-- Produces: long (tidy), monthly, quarterly. No file is written until sql/05_checks.sql passes.

CREATE OR REPLACE VIEW spec AS
SELECT * FROM (VALUES
    ('M602201','retail','volume_idx','M'), ('M602202','retail','volume_sa_idx','M'),
    ('M602121','retail','prices_idx','M'), ('M602122','retail','prices_sa_idx','M'),
    ('M602171','retail','value_sgd_m','M'), ('M602191','retail','online_pct','M'),
    ('M602141','retail','prices_idx','Q'), ('M602221','retail','volume_idx','Q'),
    ('M602211','fb','volume_idx','M'),     ('M602212','fb','volume_sa_idx','M'),
    ('M602131','fb','prices_idx','M'),     ('M602132','fb','prices_sa_idx','M'),
    ('M602181','fb','value_sgd_m','M'),    ('M602271','fb','online_pct','M')
) AS t(table_id, series_group, measure, freq);

-- Special row labels (value / online tables) -> industry dimension.
CREATE OR REPLACE VIEW row_norm AS
SELECT * FROM (VALUES
    ('M602171','Retail Sales Value - Estimated','Total'),
    ('M602171','Retail Sales Value (Excluding Motor Vehicles, Parts & Accessories) - Estimated','Total (Excluding Motor Vehicles, Parts & Accessories)'),
    ('M602181','Value Of Food & Beverage Sales - Estimated','Total'),
    ('M602191','Retail Trade','Total'),
    ('M602191','Retail Trade (Excluding Motor Vehicles, Parts & Accessories)','Total (Excluding Motor Vehicles, Parts & Accessories)'),
    ('M602271','Food & Beverage Services','Total')
) AS t(table_id, row_label, industry);

CREATE OR REPLACE VIEW long AS
WITH raw AS (
    SELECT
        regexp_extract(t.filename, 'tb-(M[0-9]+)\.json', 1) AS table_id,
        json_extract_string(r.val, '$.rowText') AS row_label,
        json_extract_string(r.val, '$.uoM') AS uom,
        json_extract_string(c.val, '$.key') AS period_label,
        json_extract_string(c.val, '$.value') AS value_txt
    FROM read_json('data/raw/tb-*.json', columns={Data: 'JSON'}, filename=true) t,
         unnest(CAST(json_extract(t.Data, '$.row') AS JSON[])) AS r(val),
         unnest(CAST(json_extract(r.val, '$.columns') AS JSON[])) AS c(val)
)
SELECT
    raw.table_id, spec.series_group, spec.measure, spec.freq,
    COALESCE(n.industry, raw.row_label) AS industry,
    raw.row_label,
    CASE WHEN spec.freq = 'M'
         THEN strptime(raw.period_label, '%Y %b')::DATE
         ELSE make_date(CAST(regexp_extract(raw.period_label, '^(\d{4})', 1) AS INT),
                        (CAST(regexp_extract(raw.period_label, '([1-4])Q', 1) AS INT) - 1) * 3 + 1, 1)
    END AS period,
    raw.period_label,
    TRY_CAST(raw.value_txt AS DOUBLE) AS idx_value
FROM raw
JOIN spec ON spec.table_id = raw.table_id
LEFT JOIN row_norm n ON n.table_id = raw.table_id AND n.row_label = raw.row_label;

-- One row per (group, industry, period); measures side by side.
CREATE OR REPLACE TABLE monthly AS
SELECT series_group, industry, period,
       max(idx_value) FILTER (measure = 'volume_idx')    AS volume_idx,
       max(idx_value) FILTER (measure = 'volume_sa_idx') AS volume_sa_idx,
       max(idx_value) FILTER (measure = 'prices_idx')    AS prices_idx,
       max(idx_value) FILTER (measure = 'prices_sa_idx') AS prices_sa_idx,
       max(idx_value) FILTER (measure = 'value_sgd_m')   AS value_sgd_m,
       max(idx_value) FILTER (measure = 'online_pct')    AS online_pct
FROM long WHERE freq = 'M' GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE quarterly AS
SELECT series_group, industry, period,
       max(idx_value) FILTER (measure = 'volume_idx') AS volume_idx,
       max(idx_value) FILTER (measure = 'prices_idx') AS prices_idx
FROM long WHERE freq = 'Q' GROUP BY 1, 2, 3;
