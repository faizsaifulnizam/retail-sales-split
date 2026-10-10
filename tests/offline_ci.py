"""Frozen offline acceptance. Install requirements.txt first; no live data requests."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def require_tests(result):
    if result.testsRun < 43 or result.skipped or not result.wasSuccessful():
        raise RuntimeError(f'incomplete suite: {result.testsRun} run, {len(result.skipped)} skipped')


def require_csv_parity(outputs, before):
    after = {p.name: p.read_bytes() for p in outputs.glob('*.csv')}
    if not before or after != before:
        raise RuntimeError('CSV artifact coverage or bytes differ from committed snapshot')


def main():
    os.chdir(ROOT)
    outputs = ROOT / 'outputs'
    before = {p.name: p.read_bytes() for p in outputs.glob('*.csv')}
    if len(before) != 7:
        raise RuntimeError('expected seven committed CSV artifacts')
    subprocess.run([sys.executable, 'src/download.py', '--snapshot'], check=True)
    subprocess.run([sys.executable, 'src/build_dataset.py'], check=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_*.py')
    require_tests(unittest.TextTestRunner(verbosity=2).run(suite))
    for stage in ('audit', 'analysis', 'figures'):
        subprocess.run([sys.executable, f'src/{stage}.py'], check=True)
    require_csv_parity(outputs, before)
    for image in (ROOT / 'reports/figures').glob('f*.png'):
        if image.read_bytes() != (ROOT / 'docs/img' / image.name).read_bytes():
            raise RuntimeError(f'report/site mirror mismatch: {image.name}')
    subprocess.run([sys.executable, 'tests/smoke_test.py'], check=True)
    print('offline acceptance: substantive tests, zero skips, seven CSVs match, mirrors match')


if __name__ == '__main__':
    main()
