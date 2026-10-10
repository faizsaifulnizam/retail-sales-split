"""Offline stdlib regressions; raw/DuckDB integration skips when unavailable."""
import contextlib
import csv
import io
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

if os.environ.get('TMPDIR'):
    tempfile.tempdir = os.environ['TMPDIR']

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import audit, download


def resign_fixture(raw):
    path = raw / 'pull_manifest.json'
    manifest = json.loads(path.read_text())
    for name, entry in manifest['files'].items():
        entry['sha256'] = hashlib.sha256((raw / name).read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))


class DownloadRegressionTests(unittest.TestCase):
    def test_manifest_release_slug_uses_year_month_labels(self):
        infos = {s['id']: dict(coverage_max='2026 Jul', coverage_min='2025 Jul',
                              bytes=1, sha256='a', current_rows=1) for s in download.TABLES}
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp) / 'manifest.json'
            with patch.object(download, 'MANIFEST', path):
                download.write_manifest(infos, '2026-10-04T00:00:00+08:00')
            self.assertTrue(json.loads(path.read_text())['release_page'].endswith('-jul2026'))


class AuditRegressionTests(unittest.TestCase):
    def cross_check(self, difference):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            raw, ref, out = (root / p for p in ('raw', 'ref', 'out'))
            for p in (raw, ref, out):
                p.mkdir()
            (ref / 'release-2026-07-tables.csv').write_text(
                'series_group,row,rel_yoy_jul26_pct,rel_sa_mom_jul26_pct\nretail,Total,0,0\n')
            for tid in ('M602121', 'M602122', 'M602201', 'M602202', 'M602171',
                        'M602131', 'M602132', 'M602211'):
                now = 100 + difference if tid == 'M602121' else 100
                data = {'Data': {'row': [{'rowText': 'Total', 'columns': [
                    {'key': k, 'value': v} for k, v in
                    [('2025 Jul', 100), ('2026 Jun', 100), ('2026 Jul', now)]]}]}}
                (raw / f'tb-{tid}.json').write_text(json.dumps(data))
            with patch.object(audit, 'RAW', raw), patch.object(audit, 'REF', ref), patch.object(audit, 'OUT', out):
                result = audit.cross_check()
            return result[1] if isinstance(result, tuple) else result

    def test_release_gate_rejects_0055_pp_unrounded_difference(self):
        self.assertEqual(self.cross_check(0.055), 1)

    def test_release_gate_accepts_published_index_precision(self):
        self.assertEqual(self.cross_check(0.0500437), 0)


@unittest.skipUnless((ROOT / 'data/raw/tb-M602121.json').exists(), 'local raw snapshot absent')
class AuditSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.raw, self.ref, self.out = (root / p for p in ('raw', 'ref', 'out'))
        shutil.copytree(ROOT / 'data/raw', self.raw)
        shutil.copytree(ROOT / 'data/reference', self.ref)
        self.out.mkdir()
        for attr, value in [('RAW', self.raw), ('REF', self.ref), ('OUT', self.out)]:
            p = patch.object(audit, attr, value)
            p.start()
            self.addCleanup(p.stop)
        p = contextlib.redirect_stdout(io.StringIO())
        p.__enter__()
        self.addCleanup(p.__exit__, None, None, None)

    def test_cached_download_repairs_release_url_without_refreshing_raw(self):
        path = self.raw / 'pull_manifest.json'
        manifest = json.loads(path.read_text())
        retrieved = manifest['retrieved_at']
        manifest['release_page'] = 'https://example.invalid/2026Jul'
        path.write_text(json.dumps(manifest))
        raw_before = {p.name: p.read_bytes() for p in self.raw.glob('tb-*.json')}
        with patch.object(download, 'RAW', self.raw), patch.object(download, 'MANIFEST', path), \
                patch.object(sys, 'argv', ['download.py']):
            download.main()
        new = json.loads(path.read_text())
        self.assertTrue(new['release_page'].endswith('-jul2026'))
        self.assertEqual(new['retrieved_at'], retrieved)
        self.assertEqual({p.name: p.read_bytes() for p in self.raw.glob('tb-*.json')}, raw_before)

    def test_success_labels_only_recomputed_rows_as_match(self):
        self.assertEqual(audit.main(), 0)
        with (self.out / 'release_check.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(sum(r['status'] == 'match' for r in rows), 19)
        self.assertEqual(sum(r['status'] == 'not_recomputed' for r in rows), 3)
        for r in rows:
            if r['status'] == 'not_recomputed':
                self.assertEqual(r['calc_yoy_jul26_pct'], '')

    def test_newer_raw_without_explicit_release_snapshot_is_rejected(self):
        path = self.raw / 'tb-M602121.json'
        data = json.loads(path.read_text())
        data['Data']['row'][0]['columns'].append({'key': '2026 Aug', 'value': '100'})
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            resign_fixture(self.raw)
            audit.main()
        self.assertFalse(list(self.out.iterdir()))

    def test_incomplete_retail_residual_is_not_a_failure(self):
        with patch.object(audit, 'LATEST', '2026 Jun'), patch.object(audit, 'PREV', '2025 Jun'):
            self.assertEqual(audit.contributions(), 0)

    def test_complete_fb_contribution_failure_is_rejected(self):
        weights = self.ref / 'rss-weights.csv'
        weights.write_text(weights.read_text().replace('fb,Restaurants,41.2,47.3', 'fb,Restaurants,41.2,0.0'))
        self.assertNotEqual(audit.contributions(), 0)

    def test_levels_receipt_checks_the_explicit_july_snapshot(self):
        self.assertEqual(audit.main(), 0)
        path = self.out / 'levels_check.csv'
        self.assertTrue(path.exists(), 'missing independently audited levels receipt')
        with path.open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual({r['metric']: float(r['release_value']) for r in rows},
                         {'retail_sales': 4419, 'retail_sales_excl_mv': 3679,
                          'fb_sales': 1607, 'retail_online_share': 15.4})
        self.assertTrue(all(r['status'] == 'match' and float(r['diff']) == 0 for r in rows))
        self.assertNotIn(b'\r', path.read_bytes())

    def test_corrupt_levels_preserve_both_existing_receipts(self):
        for name in ('release_check.csv', 'levels_check.csv'):
            (self.out / name).write_bytes(b'old\n')
        path = self.raw / 'tb-M602171.json'
        data = json.loads(path.read_text())
        for c in data['Data']['row'][0]['columns']:
            if c['key'] == '2026 Jul':
                c['value'] = '4429'
        path.write_text(json.dumps(data))
        resign_fixture(self.raw)
        self.assertEqual(audit.main(), 1)
        self.assertTrue(all(p.read_bytes() == b'old\n' for p in self.out.iterdir()))

    def test_failed_release_validation_preserves_existing_outputs(self):
        receipt = self.out / 'release_check.csv'
        receipt.write_bytes(b'existing receipt\n')
        ref = self.ref / 'release-2026-07-tables.csv'
        ref.write_text(ref.read_text().replace('retail,Total,4.0,1.5,', 'retail,Total,4.0,9.5,'))
        self.assertEqual(audit.main(), 1)
        self.assertEqual(receipt.read_bytes(), b'existing receipt\n')
        self.assertEqual({p.name for p in self.out.iterdir()}, {'release_check.csv'})


try:
    import duckdb
except ImportError:
    duckdb = None


@unittest.skipUnless(duckdb and (ROOT / 'data/raw/tb-M602121.json').exists(),
                     'DuckDB/local raw integration unavailable')
class SQLCoverageTests(unittest.TestCase):
    def test_future_latest_sa_cannot_lag_behind_other_series(self):
        old_cwd = Path.cwd()
        self.addCleanup(os.chdir, old_cwd)
        os.chdir(ROOT)
        con = duckdb.connect()
        self.addCleanup(con.close)
        con.execute((ROOT / 'sql/01_staging.sql').read_text())
        con.execute('CREATE TABLE saved_long AS SELECT * FROM long')
        con.execute('DROP VIEW long')
        con.execute('ALTER TABLE saved_long RENAME TO long')
        con.execute("INSERT INTO long SELECT table_id, series_group, measure, freq, industry, row_label, "
                    "period + INTERVAL 1 MONTH, '2026 Aug', idx_value FROM long "
                    "WHERE freq='M' AND period=DATE '2026-07-01'")
        con.execute("INSERT INTO monthly SELECT series_group, industry, period + INTERVAL 1 MONTH, "
                    "volume_idx,volume_sa_idx,prices_idx,prices_sa_idx,value_sgd_m,online_pct "
                    "FROM monthly WHERE period=DATE '2026-07-01'")
        checks = (ROOT / 'sql/05_checks.sql').read_text()
        self.assertEqual(sum(v for _, v in con.execute(checks).fetchall()), 0)
        con.execute("DELETE FROM long WHERE series_group='retail' AND industry='Department Stores' "
                    "AND measure='volume_sa_idx' AND period=DATE '2026-08-01'")
        con.execute("UPDATE monthly SET volume_sa_idx=NULL WHERE series_group='retail' "
                    "AND industry='Department Stores' AND period=DATE '2026-08-01'")
        self.assertGreater(sum(v for _, v in con.execute(checks).fetchall()), 0)


@unittest.skipUnless(duckdb and (ROOT / 'data/processed/monthly.parquet').exists(),
                     'DuckDB/processed snapshot integration unavailable')
class AnalysisSnapshotTests(unittest.TestCase):
    def setUp(self):
        from src import analysis
        self.analysis = analysis
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ('data/raw', 'data/reference', 'data/processed', 'sql'):
            shutil.copytree(ROOT / folder, self.root / folder)
        self.out = self.root / 'outputs'
        self.out.mkdir()
        for attr, value in [('ROOT', self.root), ('OUT', self.out),
                            ('WEIGHTS', self.root / 'data/reference/rss-weights.csv')]:
            p = patch.object(analysis, attr, value)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(os.chdir, Path.cwd())
        p = contextlib.redirect_stdout(io.StringIO())
        p.__enter__()
        self.addCleanup(p.__exit__, None, None, None)

    def rows(self, name):
        with (self.out / name).open() as f:
            return list(csv.DictReader(f))

    def test_reconciliation_history_uses_full_precision_not_rounded_extract(self):
        self.analysis.main()
        path = self.out / 'contribution_reconciliation.csv'
        self.assertTrue(path.exists(), 'missing monthly reconciliation history')
        rows = self.rows(path.name)
        retail = {r['month']: r for r in rows if r['series_group'] == 'retail'}
        for month, residual in [('2026-07-01', .0174), ('2026-06-01', .7088),
                                ('2026-05-01', .3201), ('2025-07-01', .4390)]:
            self.assertAlmostEqual(float(retail[month]['residual_prices_pp']), residual, places=4)
            self.assertEqual(int(retail[month]['covered_industries']), 11)
            self.assertAlmostEqual(float(retail[month]['covered_weight_pct']), 86.1)
        sens = next(r for r in self.rows('sensitivity.csv') if r['variant'].startswith('contribution method — fixed-weight'))
        self.assertAlmostEqual(float(sens['value']), float(retail['2026-07-01']['covered_contrib_prices_pp']), places=4)
        self.assertIn('coverage', sens['note'])
        self.assertIn('rounding', sens['note'])

    def test_june_incomplete_retail_basket_does_not_fail_validation(self):
        # Coherent older snapshot: move both raw and processed, never just parquet.
        from src import build_dataset
        for spec in download.TABLES:
            if spec['freq'] != 'M':
                continue
            path = self.root / 'data/raw' / f"tb-{spec['id']}.json"
            data = json.loads(path.read_text())
            for row in data['Data']['row']:
                row['columns'] = [c for c in row['columns'] if c['key'] != '2026 Jul']
            path.write_text(json.dumps(data))
        resign_fixture(self.root / 'data/raw')
        with patch.object(download, 'FLOOR_M', 2026 * 12 + 6), \
             patch.object(build_dataset, 'ROOT', self.root), \
             patch.object(build_dataset, 'STAGING', self.root / 'sql/01_staging.sql'), \
             patch.object(build_dataset, 'CHECKS', self.root / 'sql/05_checks.sql'), \
             patch.object(build_dataset, 'OUT_DIR', self.root / 'data/processed'):
            build_dataset.main()
            self.analysis.main()
        self.assertTrue(self.rows('latest_split.csv'))

    def test_missing_latest_volume_preserves_existing_outputs(self):
        (self.out / 'latest_split.csv').write_bytes(b'old\n')
        path = self.root / 'data/processed/monthly.parquet'
        con = duckdb.connect()
        con.execute(f"CREATE TABLE m AS SELECT * FROM read_parquet('{path.as_posix()}')")
        con.execute("UPDATE m SET volume_idx=NULL WHERE series_group='retail' "
                    "AND industry='Department Stores' AND period=DATE '2026-07-01'")
        path.unlink()
        con.execute(f"COPY m TO '{path.as_posix()}' (FORMAT PARQUET)")
        con.close()
        with self.assertRaisesRegex(ValueError, 'lineage'):
            self.analysis.main()
        self.assertEqual((self.out / 'latest_split.csv').read_bytes(), b'old\n')

    def test_missing_history_cell_preserves_existing_analysis_outputs(self):
        for name in ('latest_split.csv', 'sensitivity.csv', 'rebase_read.csv',
                     'tableau_extract.csv', 'contribution_reconciliation.csv'):
            (self.out / name).write_bytes(b'old\n')
        path = self.root / 'data/processed/monthly.parquet'
        con = duckdb.connect()
        con.execute(f"CREATE TABLE m AS SELECT * FROM read_parquet('{path.as_posix()}')")
        con.execute("UPDATE m SET prices_idx=NULL WHERE series_group='retail' "
                    "AND industry='Watches & Jewellery' AND period=DATE '2016-07-01'")
        path.unlink()
        con.execute(f"COPY m TO '{path.as_posix()}' (FORMAT PARQUET)")
        con.close()
        with self.assertRaisesRegex(ValueError, 'lineage'):
            self.analysis.main()
        self.assertTrue(all(p.read_bytes() == b'old\n' for p in self.out.iterdir()))

    def test_missing_monthly_industries_have_current_empty_rows(self):
        self.analysis.main()
        rows = self.rows('latest_split.csv')
        missing = [r for r in rows if r['series_group'] == 'retail' and
                   r['industry'] in self.analysis.NOT_MONTHLY]
        self.assertEqual({r['industry'] for r in missing}, set(self.analysis.NOT_MONTHLY))
        for r in missing:
            self.assertEqual(r['latest_period'], '2026-07-01')
            self.assertTrue(all(r[k] == '' for k in ('yoy_prices_pct', 'yoy_volume_pct',
                                                    'contrib_prices_pp', 'sa_mom_prices_pct')))
            self.assertNotIn('+5.1', r['note'])
        self.assertNotIn('+0.7', next(r['note'] for r in rows if r['industry'].startswith('Total (')))
        self.assertNotIn(b'\r', (self.out / 'latest_split.csv').read_bytes())


class SmokeCorruptionTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('retail_smoke', ROOT / 'tests/smoke_test.py')
        self.smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.smoke)

    def corrupt(self, attr, mutate, check, exit_code=False):
        path = getattr(self.smoke, attr)
        with path.open() as f:
            rows = list(csv.DictReader(f))
        mutate(rows)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / path.name
            with target.open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            with patch.object(self.smoke, attr, target):
                if exit_code:
                    self.assertEqual(check(), 1)
                else:
                    with self.assertRaises(AssertionError):
                        check()

    def test_smoke_rejects_corrupt_level_receipt(self):
        def check():
            with contextlib.redirect_stdout(io.StringIO()):
                return self.smoke.main()
        self.corrupt('LEVELS_CSV', lambda rows: rows[0].update(calc_value='4429'), check, exit_code=True)

    def test_smoke_rejects_corrupt_reconciliation_receipt(self):
        def check():
            with contextlib.redirect_stdout(io.StringIO()):
                return self.smoke.main()
        def mutate(rows):
            next(r for r in rows if r['month'] == '2026-07-01' and r['series_group'] == 'retail')['residual_prices_pp'] = '0.5'
        self.corrupt('RECON_CSV', mutate, check, exit_code=True)

    def test_smoke_rejects_release_mismatch(self):
        self.corrupt('RELEASE_CSV', lambda rows: rows[0].update(status='MISMATCH'), self.smoke.test_release_check)

    def test_smoke_rejects_corrupt_historical_headline(self):
        def mutate(rows):
            next(r for r in rows if r['month'] == '2026-07-01' and r['series_group'] == 'retail'
                 and r['industry'] == 'Total')['yoy_volume_pct'] = '12.8'
        self.corrupt('EXTRACT_CSV', mutate, self.smoke.test_tableau_extract)

    def test_smoke_rejects_missing_industry(self):
        self.corrupt('SPLIT_CSV', lambda rows: rows.__setitem__(slice(None),
                     [r for r in rows if r['industry'] != 'Watches & Jewellery']), self.smoke.test_latest_split)

    def test_smoke_rejects_nonfinite_metrics(self):
        self.corrupt('SPLIT_CSV', lambda rows: rows[0].update(yoy_volume_pct='nan'), self.smoke.test_latest_split)


class CIConfigurationTests(unittest.TestCase):
    def test_ci_keeps_stdlib_smoke_separate_from_dependency_backed_acceptance(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        smoke, offline = workflow.split('  offline:', 1)
        self.assertIn('python tests/smoke_test.py', smoke)
        self.assertNotIn('pip install', smoke)
        self.assertIn('python -m pip install -r requirements.txt', offline)
        self.assertIn('python tests/offline_ci.py', offline)

    def test_csv_attributes_pin_lf(self):
        attrs = ROOT / '.gitattributes'
        self.assertTrue(attrs.exists(), 'CSV checkout line endings are not pinned')
        self.assertIn('*.csv text eol=lf', attrs.read_text())


if __name__ == '__main__':
    unittest.main()
