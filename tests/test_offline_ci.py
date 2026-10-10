"""Fail-closed acceptance at the unittest result boundary."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class OfflineGateTests(unittest.TestCase):
    def test_gate_rejects_empty_skipped_and_failed_runs(self):
        path = ROOT / 'tests/offline_ci.py'
        self.assertTrue(path.exists(), 'dependency-backed offline acceptance runner missing')
        spec = importlib.util.spec_from_file_location('offline_ci', path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for count, skipped, failures in ((0, [], []), (43, [('case', 'absent')], []),
                                         (43, [], [('case', 'failure')])):
            result = unittest.TestResult()
            result.testsRun, result.skipped, result.failures = count, skipped, failures
            with self.subTest(count=count, skipped=skipped, failures=failures):
                with self.assertRaises(RuntimeError):
                    runner.require_tests(result)
        result = unittest.TestResult()
        result.testsRun = 43
        runner.require_tests(result)

    def test_csv_gate_rejects_changed_missing_extra_and_empty_artifacts(self):
        import tempfile
        spec = importlib.util.spec_from_file_location('offline_ci', ROOT / 'tests/offline_ci.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as tmp:
            outputs = Path(tmp)
            path = outputs / 'a.csv'
            path.write_bytes(b'x\n1\n')
            before = {'a.csv': path.read_bytes()}
            self.assertTrue(hasattr(runner, 'require_csv_parity'), 'CSV parity gate missing')
            runner.require_csv_parity(outputs, before)
            path.write_bytes(b'x\n2\n')
            with self.assertRaises(RuntimeError):
                runner.require_csv_parity(outputs, before)
            path.unlink()
            with self.assertRaises(RuntimeError):
                runner.require_csv_parity(outputs, before)
            path.write_bytes(before['a.csv'])
            (outputs / 'extra.csv').write_bytes(b'x\n3\n')
            with self.assertRaises(RuntimeError):
                runner.require_csv_parity(outputs, before)
            with self.assertRaises(RuntimeError):
                runner.require_csv_parity(outputs, {})

    def test_workflow_restores_before_dependency_suite_and_checks_csv_parity(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('python -m pip install -r requirements.txt', workflow)
        self.assertIn('python tests/offline_ci.py', workflow)
        self.assertIn('offline:', workflow)

if __name__ == '__main__':
    unittest.main()
