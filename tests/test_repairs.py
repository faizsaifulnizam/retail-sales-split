"""Offline caller-seam repairs. Network and promotion failures only are substituted."""
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if os.environ.get('TMPDIR'):
    tempfile.tempdir = os.environ['TMPDIR']
from src import download


class RawGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raw = Path(self.tmp.name) / 'raw'
        shutil.copytree(ROOT / 'data/raw', self.raw)
        self.manifest = self.raw / 'pull_manifest.json'
        self.before = {p.name: p.read_bytes() for p in self.raw.glob('*.json')}
        for attr, value in [('RAW', self.raw), ('MANIFEST', self.manifest)]:
            p = patch.object(download, attr, value)
            p.start()
            self.addCleanup(p.stop)
        redir = contextlib.redirect_stdout(io.StringIO())
        redir.__enter__()
        self.addCleanup(redir.__exit__, None, None, None)

    def test_late_download_failure_preserves_all_raw_and_manifest(self):
        def get(url, **kwargs):
            if url.endswith(download.TABLES[0]['id']):
                data = json.loads(self.before['tb-' + download.TABLES[0]['id'] + '.json'])
                data['Data']['dateGenerated'] = 'offline changed canary'
                return json.dumps(data).encode()
            raise TimeoutError('offline late failure')
        with patch.object(download, 'get', side_effect=get), patch.object(download.time, 'sleep'), \
                patch.object(sys, 'argv', ['download.py', '--force']):
            with self.assertRaises(SystemExit):
                download.main()
        for name, old in self.before.items():
            self.assertTrue((self.raw / name).read_bytes() == old, name + ' changed')

    def test_cache_rejects_changed_bytes_without_reauthenticating(self):
        path = self.raw / 'tb-M602121.json'
        data = json.loads(path.read_text())
        data['Data']['row'][0]['columns'][-1]['value'] = '101.607'
        path.write_text(json.dumps(data))
        previous = self.manifest.read_bytes()
        with patch.object(sys, 'argv', ['download.py']), patch.object(download, 'get', side_effect=AssertionError('network')):
            with self.assertRaisesRegex((ValueError, SystemExit), 'manifest|hash|identity'):
                download.main()
        self.assertEqual(self.manifest.read_bytes(), previous)


class PromotionTests(unittest.TestCase):
    def fixture(self, root):
        for folder in ('data', 'sql', 'outputs', 'docs/img', 'reports/figures'):
            shutil.copytree(ROOT / folder, root / folder)

    def run_stage(self, module, root):
        with contextlib.ExitStack() as stack:
            for attr in ('ROOT', 'RAW', 'REF', 'OUT', 'OUT_DIR', 'STAGING', 'CHECKS', 'WEIGHTS', 'MANIFEST', 'FIGDIR', 'PARQUET_M', 'PARQUET_Q'):
                if hasattr(module, attr):
                    original = getattr(module, attr)
                    if attr == 'ROOT':
                        value = root
                    else:
                        value = root / Path(original).relative_to(ROOT)
                        if isinstance(original, str):
                            value = value.as_posix()
                    stack.enter_context(patch.object(module, attr, value))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.callback(os.chdir, Path.cwd())
            return module.main()

    def test_late_promotions_preserve_previous_generation_at_every_stage(self):
        from src import audit, analysis, build_dataset, figures
        real_replace = os.replace
        for module, folder, ordinal in ((download, 'data/raw', 15), (build_dataset, 'data/processed', 2),
                                        (audit, 'outputs', 2), (analysis, 'outputs', 5), (figures, 'reports/figures', 10)):
            with self.subTest(stage=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root)
                targets = [p for p in (root / folder).iterdir() if p.is_file() and p.suffix in ('.json', '.csv', '.parquet', '.png')]
                if module is figures:
                    targets += list((root / 'docs/img').glob('f*.png'))
                before = {p: p.read_bytes() for p in targets}
                # A different prior generation makes early promotion observable.
                if module in (build_dataset, audit, analysis, figures):
                    for p in targets:
                        if folder == 'data/processed':
                            p.write_bytes(b'previous generation')
                        elif module is not analysis or p.name != 'latest_split.csv':
                            p.write_bytes(b'previous generation')
                    before = {p: p.read_bytes() for p in targets}
                calls = 0
                def fail_once(source, target):
                    nonlocal calls
                    if str(source).endswith(('.tmp', '.part')):
                        calls += 1
                        if calls == ordinal:
                            raise OSError('late promotion canary')
                    return real_replace(source, target)
                def get(url, **kwargs):
                    name = 'tb-' + url.rsplit('/', 1)[-1] + '.json'
                    data = json.loads((root / 'data/raw' / name).read_text())
                    data['Data']['dateGenerated'] = 'offline changed canary'
                    return json.dumps(data).encode()
                with patch('os.replace', side_effect=fail_once), patch.object(sys, 'argv', ['stage.py', '--force'] if module is download else ['stage.py']), \
                     patch.object(download, 'get', side_effect=get):
                    with self.assertRaisesRegex(OSError, 'late promotion'):
                        self.run_stage(module, root)
                for p, old in before.items():
                    self.assertTrue(p.read_bytes() == old, str(p.relative_to(root)) + ' changed')


class PathTests(PromotionTests):
    # Inherit only the fixture helper, not the promotion test.
    test_late_promotions_preserve_previous_generation_at_every_stage = None

    def test_apostrophe_paths_build_and_render_from_unrelated_cwd(self):
        from src import build_dataset, figures
        for module in (build_dataset, figures):
            with self.subTest(stage=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "analyst's retail tree"
                self.fixture(root)
                cwd = Path.cwd()
                os.chdir(Path(tmp))
                try:
                    self.run_stage(module, root)
                finally:
                    os.chdir(cwd)


class NumericTests(PromotionTests):
    test_late_promotions_preserve_previous_generation_at_every_stage = None

    def test_snapshot_late_promotion_preserves_previous_raw_generation(self):
        from src import download
        real_replace = os.replace
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            raw = root / 'data/raw'
            targets = list(raw.glob('*.json'))
            for path in targets:
                path.write_bytes(b'previous generation')
            before = {path: path.read_bytes() for path in targets}
            calls = 0
            def fail_once(source, target):
                nonlocal calls
                if str(source).endswith('.part'):
                    calls += 1
                    if calls == 15:
                        raise OSError('snapshot late promotion')
                return real_replace(source, target)
            with patch('os.replace', side_effect=fail_once), patch.object(sys, 'argv', ['download.py', '--snapshot']):
                with self.assertRaisesRegex(OSError, 'snapshot late promotion'):
                    self.run_stage(download, root)
            self.assertEqual(calls, 15)
            self.assertTrue(all(path.read_bytes() == old for path, old in before.items()))
            self.assertFalse(list(raw.glob('*.part')))

    def test_quarterly_same_period_drift_rejects_analysis_and_figures_before_publication(self):
        from src import analysis, figures
        import duckdb
        for module in (analysis, figures):
            with self.subTest(stage=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root)
                path = root / 'data/processed/quarterly.parquet'
                with duckdb.connect() as con:
                    con.read_parquet(str(path)).create_view('original')
                    con.execute('CREATE TABLE altered AS SELECT * FROM original')
                    con.execute("UPDATE altered SET prices_idx=prices_idx+1 WHERE series_group='retail' AND industry='Total' AND period=DATE '2026-04-01'")
                    con.table('altered').write_parquet(str(path.with_suffix('.tmp')))
                os.replace(path.with_suffix('.tmp'), path)
                before = {p: p.read_bytes() for folder in ('outputs', 'reports/figures', 'docs/img')
                          for p in (root / folder).iterdir() if p.is_file()}
                with self.assertRaisesRegex(ValueError, 'lineage mismatch: quarterly'):
                    self.run_stage(module, root)
                self.assertTrue(all(p.read_bytes() == old for p, old in before.items()))

    def test_same_month_numeric_corruptions_reject_before_any_chart_save(self):
        from src import figures as f
        con = f.duckdb.connect()
        self.addCleanup(con.close)
        con.read_parquet(f.PARQUET_M).create_view('monthly')
        con.execute((ROOT / 'sql/02_metrics.sql').read_text())
        with (ROOT / 'outputs/latest_split.csv').open() as stream:
            original = list(csv.DictReader(stream))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'outputs').mkdir()
            shutil.copytree(ROOT / 'data/reference', root / 'data/reference')
            target = root / 'outputs/latest_split.csv'
            def write(rows):
                with target.open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(original[0]))
                    writer.writeheader()
                    writer.writerows(rows)
            with patch.object(f, 'ROOT', root), patch.object(f, 'save') as save:
                write(original[::-1])
                self.assertEqual(len(f.load_split(con)), len(original))
                for column in ('yoy_volume_pct', 'yoy_prices_pct', 'sa_mom_volume_pct', 'sa_mom_prices_pct',
                               'prev_yoy_volume_pct', 'prev_yoy_prices_pct', 'weight_2017_pct', 'weight_2025_pct',
                               'contrib_prices_pp', 'contrib_volume_approx_pp'):
                    for index, row in enumerate(original):
                        if not row[column]:
                            continue
                        rows = [dict(r) for r in original]
                        rows[index][column] = '99.21'
                        write(rows)
                        with self.subTest(industry=row['industry'], field=column):
                            with self.assertRaisesRegex(ValueError, 'numeric|identity|snapshot'):
                                f.load_split(con)
                for rows in (original + [original[0]], original[1:],
                             [dict(original[0], yoy_prices_pct='nan'), *original[1:]]):
                    write(rows)
                    with self.assertRaises(ValueError):
                        f.load_split(con)
                save.assert_not_called()

    def test_unmanifested_raw_bytes_rejected_by_build_and_audit(self):
        from src import audit, build_dataset
        for module in (audit, build_dataset):
            with self.subTest(stage=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root)
                path = root / 'data/raw/tb-M602121.json'
                data = json.loads(path.read_text())
                data['Data']['dateGenerated'] = 'unmanifested canary'
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, 'source.*identity'):
                    self.run_stage(module, root)

    def test_changed_same_month_source_cannot_reuse_old_processed_generation(self):
        import hashlib
        from src import analysis, figures
        for module in (analysis, figures):
            with self.subTest(stage=module.__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root)
                path = root / 'data/raw/tb-M602121.json'
                data = json.loads(path.read_text())
                row = next(r for r in data['Data']['row'] if r['rowText'] == 'Department Stores')
                next(c for c in row['columns'] if c['key'] == '2026 Jul')['value'] = '102.123'
                path.write_text(json.dumps(data))
                mp = root / 'data/raw/pull_manifest.json'
                manifest = json.loads(mp.read_text())
                manifest['files'][path.name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                manifest['files'][path.name]['bytes'] = path.stat().st_size
                mp.write_text(json.dumps(manifest))
                before = {p: p.read_bytes() for folder in ('outputs', 'reports/figures', 'docs/img')
                          for p in (root / folder).iterdir() if p.is_file()}
                with self.assertRaisesRegex(ValueError, 'lineage|generation|source'):
                    self.run_stage(module, root)
                for path, old in before.items():
                    self.assertTrue(path.read_bytes() == old, path.name)


class RoundingTests(unittest.TestCase):
    def test_actual_split_and_watch_labels_round_primary_rates_once_in_both_palettes(self):
        from src import figures as f
        con = f.duckdb.connect()
        self.addCleanup(con.close)
        con.read_parquet(f.PARQUET_M).create_view('monthly')
        con.execute((ROOT / 'sql/02_metrics.sql').read_text())
        for palette in (f.LIGHT, f.DARK):
            f.use_palette(palette)
            f.use_series_style(dark=palette is f.DARK)
            captured = []
            try:
                with patch.object(f, 'save', side_effect=lambda fig, name: captured.append((fig, name))), contextlib.redirect_stdout(io.StringIO()):
                    f.fig2_split(con)
                    f.fig3_watch(con)
                split = captured[0][0]
                labels = [t.get_text() for t in split.axes[0].texts]
                self.assertIn('+11.1', labels)
                self.assertIn('-1.5', labels)
                watch = captured[1][0]
                self.assertIn('pr +11.1%', [t.get_text() for t in watch.axes[1].texts])
            finally:
                for fig, _ in captured:
                    f.plt.close(fig)


class SmokeNumericsTests(unittest.TestCase):
    def test_all_seventeen_rebase_and_sensitivity_value_corruptions_fail(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('smoke', ROOT / 'tests/smoke_test.py')
        smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smoke)
        for attr in ('REBASE_CSV', 'SENS_CSV'):
            original_path = getattr(smoke, attr)
            with original_path.open() as stream:
                original = list(csv.DictReader(stream))
            for index, row in enumerate(original):
                if not row['value']:
                    continue
                with self.subTest(file=attr, row=index), tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / original_path.name
                    rows = [dict(r) for r in original]
                    rows[index]['value'] = '99.21'
                    with path.open('w', newline='') as stream:
                        writer = csv.DictWriter(stream, fieldnames=list(original[0]))
                        writer.writeheader()
                        writer.writerows(rows)
                    with patch.object(smoke, attr, path):
                        with self.assertRaises(AssertionError):
                            smoke.test_rebase_and_sensitivity()
        smoke.test_rebase_and_sensitivity()


class PresentationTests(unittest.TestCase):
    def test_report_semantics_and_nominal_value_wording(self):
        from html.parser import HTMLParser
        class Parser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []
                self.stack = []
                self.bad_caption = False
            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)
                if tag == 'figcaption' and (not self.stack or self.stack[-1] != 'figure'):
                    self.bad_caption = True
                if tag not in ('meta', 'link', 'img', 'source', 'br'):
                    self.stack.append(tag)
            def handle_endtag(self, tag):
                if self.stack and self.stack[-1] == tag:
                    self.stack.pop()
        text = (ROOT / 'docs/index.html').read_text(encoding='utf-8')
        parser = Parser()
        parser.feed(text)
        with self.subTest(contract='nominal sales wording'):
            self.assertNotIn('(prices) for July', text)
            self.assertIn('(current-price sales value) for July', text)
        with self.subTest(contract='visible title and landmark'):
            self.assertEqual(parser.tags.count('main'), 1)
            self.assertEqual(parser.tags.count('h1'), 1)
            self.assertLess(parser.tags.index('h1'), parser.tags.index('h2'))
        with self.subTest(contract='caption semantics'):
            self.assertFalse(parser.bad_caption)
        with self.subTest(contract='staging count mirror'):
            self.assertNotIn('13/13', text)
            self.assertNotIn('13 assertions', text)
            self.assertNotIn('13 checks', text)


class SnapshotTests(unittest.TestCase):
    def test_download_snapshot_route_restores_original_generation_without_network(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / 'data/raw'
            raw.mkdir(parents=True)
            archive = root / 'data/snapshots/2026-07.zip'
            archive.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / 'data/snapshots/2026-07.zip', archive)
            with patch.object(download, 'ROOT', root), patch.object(download, 'RAW', raw), \
                 patch.object(download, 'MANIFEST', raw / 'pull_manifest.json'), \
                 patch.object(sys, 'argv', ['download.py', '--snapshot']), \
                 patch.object(download, 'get', side_effect=AssertionError('network')), contextlib.redirect_stdout(io.StringIO()):
                download.main()
            with zipfile.ZipFile(archive) as bundle:
                for name in bundle.namelist():
                    self.assertTrue((raw / name).read_bytes() == bundle.read(name), name)

    def test_frozen_archive_contains_exact_fourteen_sources_and_original_manifest(self):
        import hashlib
        import zipfile
        archive = ROOT / 'data/snapshots/2026-07.zip'
        self.assertTrue(archive.exists(), 'licensed exact-byte replay archive missing')
        with zipfile.ZipFile(archive) as bundle:
            manifest_bytes = bundle.read('pull_manifest.json')
            self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), '5f964018f2063ced3077e5663c75bd3d59c2de7e749492559c9a3895080dad77')
            manifest = json.loads(manifest_bytes)
            self.assertEqual(len(manifest['files']), 14)
            self.assertEqual(set(bundle.namelist()), set(manifest['files']) | {'pull_manifest.json'})
            self.assertEqual(len(bundle.namelist()), 15)
            for name, entry in manifest['files'].items():
                self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), entry['sha256'])
                self.assertTrue(bundle.read(name) == (ROOT / 'data/raw' / name).read_bytes())
            self.assertLess(sum(i.file_size for i in bundle.infolist()), 50_000_000)


if __name__ == '__main__':
    unittest.main()
