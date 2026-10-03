-- 02_metrics.sql — latest-month metrics per industry (run by src/analysis.py and src/figures.py
-- against data/processed/*.parquet, so figures always match the SQL).
-- Window note: series contiguity is asserted in sql/05_checks.sql, so positional lags
-- (12 = same month last year, 1 = previous month) are calendar-correct.

CREATE OR REPLACE VIEW monthly_metrics AS
SELECT series_group, industry, period,
       (volume_idx    / lag(volume_idx,    12) OVER w - 1) * 100 AS yoy_volume_pct,
       (prices_idx    / lag(prices_idx,    12) OVER w - 1) * 100 AS yoy_prices_pct,
       (volume_sa_idx / lag(volume_sa_idx,  1) OVER w - 1) * 100 AS sa_mom_volume_pct,
       (prices_sa_idx / lag(prices_sa_idx,  1) OVER w - 1) * 100 AS sa_mom_prices_pct
FROM monthly
WINDOW w AS (PARTITION BY series_group, industry ORDER BY period);

-- One row per (group, industry) at each series' own latest period, plus prior-month YoY.
CREATE OR REPLACE VIEW latest_split AS
WITH bounds AS (SELECT series_group, max(period) AS p FROM monthly GROUP BY 1)
SELECT mm.series_group, mm.industry, mm.period AS latest_period,
       mm.yoy_volume_pct, mm.yoy_prices_pct, mm.sa_mom_volume_pct, mm.sa_mom_prices_pct,
       pm.yoy_volume_pct AS prev_yoy_volume_pct, pm.yoy_prices_pct AS prev_yoy_prices_pct
FROM monthly_metrics mm
JOIN bounds b ON b.series_group = mm.series_group AND b.p = mm.period
LEFT JOIN monthly_metrics pm
       ON pm.series_group = mm.series_group AND pm.industry = mm.industry
      AND pm.period = mm.period - INTERVAL 1 MONTH;
