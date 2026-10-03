"""Smoke tests for the committed artifacts — stdlib only, no network.

Run (repo root):  python tests/smoke_test.py
In CI:            same command, on every push + PR (.github/workflows/ci.yml)

These do NOT re-run the pipeline (that needs the raw download); they check the
repo's committed outputs, figures and assets are present, parse, and keep their
expected shape. Regenerating the outputs should still keep these green:
required-column SUBSETS only, no headline numbers, figures = existence + size floor.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPLIT_CSV = ROOT / "outputs" / "latest_split.csv"
RELEASE_CSV = ROOT / "outputs" / "release_check.csv"
REBASE_CSV = ROOT / "outputs" / "rebase_read.csv"
SENS_CSV = ROOT / "outputs" / "sensitivity.csv"
EXTRACT_CSV = ROOT / "outputs" / "tableau_extract.csv"

SPLIT_REQUIRED_COLS = {
    "series_group", "industry", "latest_period", "yoy_volume_pct", "yoy_prices_pct",
    "sa_mom_volume_pct", "sa_mom_prices_pct", "weight_2025_pct", "contrib_prices_pp", "note",
}
RELEASE_REQUIRED_COLS = {"series_group", "row", "rel_yoy_jul26_pct", "calc_yoy_jul26_pct", "status"}
REBASE_REQUIRED_COLS = {"metric", "value", "note"}
SENS_REQUIRED_COLS = {"variant", "window", "metric", "value", "note"}
EXTRACT_REQUIRED_COLS = {"month", "series_group", "industry", "volume_idx", "prices_idx",
                         "yoy_volume_pct", "contrib_prices_pp"}

EXPECTED_FIGURES = [
    "f1_headline.png", "f1_headline-dark.png",
    "f2_split.png", "f2_split-dark.png",
    "f3_watch.png", "f3_watch-dark.png",
]

MIN_FIGURE_BYTES = 5000


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_latest_split() -> None:
    rows = _load_csv(SPLIT_CSV)
    assert rows, f"{SPLIT_CSV.name} has no data rows"
    missing = SPLIT_REQUIRED_COLS - set(rows[0].keys())
    assert not missing, f"{SPLIT_CSV.name} missing columns: {sorted(missing)}"
    groups = {r["series_group"] for r in rows}
    assert groups == {"retail", "fb"}, f"unexpected series groups: {groups}"
    assert any(r["series_group"] == "retail" and r["industry"] == "Total" for r in rows), "no retail Total row"
    for r in rows:
        if r["yoy_volume_pct"]:
            float(r["yoy_volume_pct"])
        if r["contrib_prices_pp"]:
            float(r["contrib_prices_pp"])


def test_release_check() -> None:
    rows = _load_csv(RELEASE_CSV)
    assert rows, f"{RELEASE_CSV.name} has no data rows"
    missing = RELEASE_REQUIRED_COLS - set(rows[0].keys())
    assert not missing, f"{RELEASE_CSV.name} missing columns: {sorted(missing)}"
    assert len(rows) >= 19, f"only {len(rows)} release rows — expected the full set"
    for r in rows:
        assert r["status"] in ("match", "MISMATCH"), f"unexpected status {r['status']!r}"


def test_rebase_and_sensitivity() -> None:
    for path, cols, min_rows in ((REBASE_CSV, REBASE_REQUIRED_COLS, 6), (SENS_CSV, SENS_REQUIRED_COLS, 8)):
        rows = _load_csv(path)
        assert rows, f"{path.name} has no data rows"
        missing = cols - set(rows[0].keys())
        assert not missing, f"{path.name} missing columns: {sorted(missing)}"
        assert len(rows) >= min_rows, f"{path.name}: only {len(rows)} rows (expected >= {min_rows})"


def test_tableau_extract() -> None:
    rows = _load_csv(EXTRACT_CSV)
    assert rows, f"{EXTRACT_CSV.name} has no data rows"
    missing = EXTRACT_REQUIRED_COLS - set(rows[0].keys())
    assert not missing, f"{EXTRACT_CSV.name} missing columns: {sorted(missing)}"
    assert len(rows) >= 2000, f"only {len(rows)} extract rows — expected the monthly history"
    months = {r["month"] for r in rows}
    assert min(months) >= "2016-01", f"extract starts before 2016: {min(months)}"


def test_figures_present() -> None:
    fig_dir = ROOT / "reports" / "figures"
    missing = [n for n in EXPECTED_FIGURES if not (fig_dir / n).is_file()]
    assert not missing, f"missing figures: {missing}"
    small = [n for n in EXPECTED_FIGURES if (fig_dir / n).stat().st_size < MIN_FIGURE_BYTES]
    assert not small, f"suspiciously small figures: {small}"


def test_banner_and_docs_present() -> None:
    for name in ("banner.svg", "banner-dark.svg"):
        p = ROOT / "assets" / name
        assert p.is_file(), f"missing asset: {name}"
        assert p.stat().st_size > 500, f"{name} suspiciously small"
    for name in ("data_audit.md", "decision_memo.md", "sensitivity.md"):
        assert (ROOT / "docs" / name).is_file(), f"missing doc: {name}"


def main() -> int:
    checks = [test_latest_split, test_release_check, test_rebase_and_sensitivity,
              test_tableau_extract, test_figures_present, test_banner_and_docs_present]
    failed = 0
    for fn in checks:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 — report, don't crash the runner
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
