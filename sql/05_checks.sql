-- 05_checks.sql — assertions for the staged tables. Run BEFORE the parquet is written.
-- Returns one row per check: (check_name, violations); build_dataset.py fails on any violation.
-- Bounds are deliberately generous (official aggregates): they catch structural breakage, not outliers.

SELECT 'raw cells non-numeric (expected 0)' AS check_name,
       (SELECT count(*) FROM long WHERE idx_value IS NULL) AS violations
UNION ALL
SELECT 'monthly index series reach 2026-07 (non-stale rows)',
       (SELECT count(*) FROM (
            SELECT series_group, measure, industry, max(period) AS last_p
            FROM long WHERE freq = 'M' AND measure IN ('volume_idx','volume_sa_idx','prices_idx','prices_sa_idx')
              AND NOT (series_group = 'retail' AND industry = 'Computer & Telecommunications Equipment')
            GROUP BY 1,2,3 HAVING max(period) < DATE '2026-07-01') x)
UNION ALL
SELECT 'documented stale gap unchanged: Computer monthly index rows end 1996-08',
       (SELECT count(*) FROM (
            SELECT series_group, measure, industry, max(period) AS last_p
            FROM long WHERE freq = 'M' AND industry = 'Computer & Telecommunications Equipment'
              AND measure IN ('volume_idx','volume_sa_idx','prices_idx','prices_sa_idx')
            GROUP BY 1,2,3 HAVING max(period) <> DATE '1996-08-01') x)
UNION ALL
SELECT 'quarterly series reach 2026-04-01',
       (SELECT count(*) FROM (
            SELECT series_group, measure, industry, max(period) AS last_p
            FROM long WHERE freq = 'Q' GROUP BY 1,2,3 HAVING max(period) < DATE '2026-04-01') x)
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
            SELECT series_group, sum(weight_2025_pct) AS s FROM read_csv_auto('data/reference/rss-weights.csv')
            GROUP BY 1 HAVING abs(s - 100) > 0.2) x)
UNION ALL
SELECT 'latest month has original AND SA volume (non-stale industries)',
       (SELECT count(*) FROM monthly m
        WHERE m.period = DATE '2026-07-01'
          AND m.industry <> 'Computer & Telecommunications Equipment'
          AND m.volume_idx IS NOT NULL
          AND m.volume_sa_idx IS NULL)
UNION ALL
SELECT 'split coverage: prices at 2026-07 and 2025-07 (retail non-stale)',
       (SELECT count(*) FROM (
            SELECT industry, count(*) FILTER (period IN (DATE '2026-07-01', DATE '2025-07-01')) AS n
            FROM monthly
            WHERE series_group = 'retail' AND industry <> 'Computer & Telecommunications Equipment'
              AND industry <> 'Total (Excluding Motor Vehicles, Parts & Accessories)'
            GROUP BY 1 HAVING n < 2) x)
UNION ALL
SELECT 'excl-MV value series covers 2025-07 and 2026-07',
       (SELECT count(*) FROM (
            SELECT count(*) FILTER (period IN (DATE '2026-07-01', DATE '2025-07-01')) AS n
            FROM monthly
            WHERE series_group = 'retail'
              AND industry = 'Total (Excluding Motor Vehicles, Parts & Accessories)'
            HAVING n < 2) x);
