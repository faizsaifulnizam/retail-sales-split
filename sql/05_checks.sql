-- Staged checks run BEFORE parquet writes. Dataset-wide latest is validated,
-- not min(series latest): a lagging/missing series must fail, not disappear.
WITH latest AS (SELECT max(period) AS p FROM long WHERE freq = 'M'),
weights AS (SELECT * FROM read_csv_auto('data/reference/rss-weights.csv')),
expected_industries AS (
    SELECT series_group, industry FROM weights
    WHERE NOT (series_group = 'retail' AND industry IN
        ('Computer & Telecommunications Equipment', 'Optical Goods & Books', 'Others'))
    UNION ALL SELECT 'retail', 'Total'
    UNION ALL SELECT 'fb', 'Total'
), index_measures AS (
    SELECT * FROM (VALUES ('volume_idx'), ('volume_sa_idx'), ('prices_idx'), ('prices_sa_idx')) t(measure)
), index_coverage AS (
    SELECT e.series_group, e.industry, m.measure,
           count(l.idx_value) FILTER (l.period = latest.p) AS n_latest,
           count(l.idx_value) FILTER (l.period = latest.p - INTERVAL 12 MONTH) AS n_prior
    FROM expected_industries e CROSS JOIN index_measures m CROSS JOIN latest
    LEFT JOIN long l ON l.freq = 'M' AND l.series_group = e.series_group
                    AND l.industry = e.industry AND l.measure = m.measure
    GROUP BY 1,2,3
)
SELECT 'raw cells non-numeric (expected 0)' AS check_name,
       (SELECT count(*) FROM long WHERE idx_value IS NULL OR NOT isfinite(idx_value)) AS violations
UNION ALL
SELECT 'all expected original and SA indices reach common latest',
       (SELECT count(*) FROM index_coverage WHERE n_latest <> 1)
UNION ALL
SELECT 'all expected original and SA indices cover prior-year month',
       (SELECT count(*) FROM index_coverage WHERE n_prior <> 1)
UNION ALL
-- STATIC gap is intentional: publisher monthly Computer index gap, not freshness.
-- Its online-share row remains current.
SELECT 'documented stale gap unchanged: Computer monthly indices end 1996-08',
       (SELECT count(*) FROM (
           SELECT m.measure, max(l.period) AS last_p
           FROM index_measures m LEFT JOIN long l ON l.freq = 'M'
             AND l.series_group = 'retail' AND l.industry = 'Computer & Telecommunications Equipment'
             AND l.measure = m.measure
           GROUP BY 1 HAVING max(l.period) IS NULL OR max(l.period) <> DATE '1996-08-01') x)
UNION ALL
SELECT 'quarterly series cover the last complete quarter',
       (SELECT count(*) FROM (
           SELECT series_group, measure, industry, max(period) AS last_p
           FROM long WHERE freq = 'Q'
           GROUP BY 1,2,3 HAVING max(period) < (SELECT date_trunc('quarter', p) - INTERVAL 3 MONTH FROM latest)) x)
UNION ALL
SELECT 'monthly series contiguous (no gaps)',
       (SELECT count(*) FROM (
            SELECT period, lag(period) OVER w AS prev_p
            FROM long WHERE freq = 'M'
            WINDOW w AS (PARTITION BY series_group, measure, industry ORDER BY period)
        ) x WHERE prev_p IS NOT NULL AND period <> prev_p + INTERVAL 1 MONTH)
UNION ALL
SELECT 'no duplicate (group, industry, period) in monthly',
       (SELECT count(*) FROM (
            SELECT series_group, industry, period FROM monthly GROUP BY 1,2,3 HAVING count(*) > 1) x)
UNION ALL
SELECT 'monthly index values within (0, 500)',
       (SELECT count(*) FROM monthly
        WHERE (volume_idx    IS NOT NULL AND (volume_idx    <= 0 OR volume_idx    >= 500))
           OR (volume_sa_idx IS NOT NULL AND (volume_sa_idx <= 0 OR volume_sa_idx >= 500))
           OR (prices_idx    IS NOT NULL AND (prices_idx    <= 0 OR prices_idx    >= 500))
           OR (prices_sa_idx IS NOT NULL AND (prices_sa_idx <= 0 OR prices_sa_idx >= 500)))
UNION ALL
SELECT 'S$M value series within (100, 20000)',
       (SELECT count(*) FROM monthly WHERE value_sgd_m IS NOT NULL AND (value_sgd_m < 100 OR value_sgd_m > 20000))
UNION ALL
SELECT 'online proportions within [0, 100]',
       (SELECT count(*) FROM monthly WHERE online_pct IS NOT NULL AND (online_pct < 0 OR online_pct > 100))
UNION ALL
SELECT '2025-based weights sum to 100 per group (±0.2)',
       (SELECT count(*) FROM (
            SELECT series_group, sum(weight_2025_pct) AS s FROM weights
            GROUP BY 1 HAVING abs(s - 100) > 0.2) x)
UNION ALL
SELECT 'excl-MV value series covers latest and prior-year month',
       (SELECT CASE WHEN count(value_sgd_m) = 2 THEN 0 ELSE 1 END
        FROM monthly CROSS JOIN latest
        WHERE series_group = 'retail'
          AND industry = 'Total (Excluding Motor Vehicles, Parts & Accessories)'
          AND period IN (latest.p, latest.p - INTERVAL 12 MONTH));
