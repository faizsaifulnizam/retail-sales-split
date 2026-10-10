"""Smoke tests for the committed artifacts — stdlib only, no network.

Run (repo root):  python tests/smoke_test.py
In CI:            same command, on every push + PR (.github/workflows/ci.yml)

These do NOT re-run the pipeline (that needs the raw download); they check the
repo's committed outputs, figures and assets are present, parse, and keep their
expected shape. Regenerating the outputs should still keep these green:
required-column SUBSETS, historical July anchors (not fixed latest), and validation gates.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NOT_MONTHLY = {"Computer & Telecommunications Equipment", "Optical Goods & Books", "Others"}
RELEASE_TOL_PP = 0.051  # 0.05 pp release rounding + 0.001 pp published-index precision
LEVELS_CSV = ROOT / "outputs" / "levels_check.csv"
RECON_CSV = ROOT / "outputs" / "contribution_reconciliation.csv"

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


def _number(value):
    n = float(value)
    assert math.isfinite(n), f"non-finite value: {value}"
    return n


def _july_anchors(rows):
    total = [r for r in rows if r["series_group"] == "retail" and r["industry"] == "Total"]
    watches = [r for r in rows if r["series_group"] == "retail" and r["industry"] == "Watches & Jewellery"]
    assert len(total) == len(watches) == 1, "missing/duplicate July anchor rows"
    assert math.isclose(_number(total[0]["yoy_volume_pct"]), -1.28, abs_tol=0.005)
    assert math.isclose(_number(total[0]["yoy_prices_pct"]), 1.46, abs_tol=0.005)
    assert math.isclose(_number(watches[0]["contrib_prices_pp"]), 1.207, abs_tol=0.0005)


def test_latest_split() -> None:
    rows = _load_csv(SPLIT_CSV)
    assert rows and SPLIT_REQUIRED_COLS <= rows[0].keys(), "missing split data/columns"
    weights = _load_csv(ROOT / "data/reference/rss-weights.csv")
    expected = {(r["series_group"], r["industry"]) for r in weights} | {
        ("retail", "Total"), ("fb", "Total"),
        ("retail", "Total (Excluding Motor Vehicles, Parts & Accessories)")}
    actual = {(r["series_group"], r["industry"]) for r in rows}
    assert actual == expected and len(rows) == len(expected), "missing/unexpected/duplicate split industries"
    assert len({r["latest_period"] for r in rows}) == 1, "mixed latest periods"
    for r in rows:
        numeric = [k for k in r if k.endswith(("_pct", "_pp"))]
        for k in numeric:
            if r[k]:
                _number(r[k])
        if r["series_group"] == "retail" and r["industry"] in NOT_MONTHLY:
            assert all(not r[k] for k in numeric if not k.startswith("weight_")), "unavailable monthly metrics populated"
            assert "unavailable" in r["note"]
        elif r["industry"].startswith("Total (Excluding"):
            assert r["yoy_prices_pct"], "missing excl-MV value YoY"
        else:
            assert all(r[k] for k in ("yoy_prices_pct", "yoy_volume_pct", "sa_mom_volume_pct", "sa_mom_prices_pct")), "unexpected empty monthly metrics"
            if r["industry"] != "Total":
                assert r["contrib_prices_pp"], "missing industry contribution"
    if rows[0]["latest_period"] == "2026-07-01":
        _july_anchors(rows)  # Historical lock, not a permanently pinned latest month.


def test_release_check() -> None:
    rows = _load_csv(RELEASE_CSV)
    assert rows and RELEASE_REQUIRED_COLS <= rows[0].keys(), "missing release data/columns"
    assert len(rows) == 22
    assert sum(r["status"] == "match" for r in rows) == 19
    assert sum(r["status"] == "not_recomputed" for r in rows) == 3
    assert len({(r["series_group"], r["row"]) for r in rows}) == len(rows), "duplicate release rows"
    for r in rows:
        unavailable = r["series_group"] == "retail" and r["row"] in NOT_MONTHLY
        assert r["status"] == ("not_recomputed" if unavailable else "match"), "release validation failed"
        for calc, rel, diff in (("calc_yoy_jul26_pct", "rel_yoy_jul26_pct", "diff_yoy_pct"),
                                ("calc_sa_mom_jul26_pct", "rel_sa_mom_jul26_pct", "diff_sa_mom_pct")):
            if unavailable:
                assert not r[calc] and not r[diff]
            elif r[calc]:
                d = _number(r[calc]) - _number(r[rel])
                assert math.isclose(d, _number(r[diff]), abs_tol=1e-10), "inconsistent release difference"
                assert abs(d) <= RELEASE_TOL_PP, "release difference outside rounding/precision gate"
            else:
                assert calc.startswith("calc_sa") and r["row"].startswith("Total (Excluding"), "unexpected uncomputed release row"
                assert not r[diff]


def test_rebase_and_sensitivity() -> None:
    # Independent stdlib/Decimal oracle from calendar-keyed committed index levels.
    from decimal import Decimal as D
    extract = _load_csv(EXTRACT_CSV)
    history = {(r['series_group'], r['industry'], r['month']): r for r in extract}
    assert len(history) == len(extract), 'duplicate extract keys'
    latest = max(r['month'] for r in extract)
    year, month = map(int, latest[:7].split('-'))
    def prior(months):
        index = year * 12 + month - 1 - months
        return f'{index // 12:04d}-{index % 12 + 1:02d}-01'
    def level(name, field, when=latest):
        value = D(history[('retail', name, when)][field])
        assert value.is_finite() and value > 0, 'invalid oracle level'
        return value
    def growth(field, lag):
        return (level('Total', field) / level('Total', field, prior(lag)) - 1) * 100
    weights = {r['industry']: (D(r['weight_2017_pct']), D(r['weight_2025_pct']))
               for r in _load_csv(ROOT / 'data/reference/rss-weights.csv') if r['series_group'] == 'retail'}
    covered = set(weights) - NOT_MONTHLY
    assert len(covered) == 11
    def basket(index):
        current = sum(weights[name][index] * level(name, 'prices_idx') for name in covered)
        previous = sum(weights[name][index] * level(name, 'prices_idx', prior(12)) for name in covered)
        return (current / previous - 1) * 100
    def contribution(name, field, index=1):
        return weights[name][index] * (level(name, field) - level(name, field, prior(12))) / level('Total', field, prior(12))
    old, new = basket(0), basket(1)
    motor = 'Motor Vehicles, Parts & Accessories'
    rebase = {
        'basket_yoy_2025_weights_pct': (new, .005),
        'basket_yoy_2017_weights_pct': (old, .005),
        'weight_effect_pp': (new - old, .005),
        'motor_vehicles_weight_2017_pct': (weights[motor][0], 1e-10),
        'motor_vehicles_weight_2025_pct': (weights[motor][1], 1e-10),
        'motor_vehicles_contrib_old_weight_pp': (contribution(motor, 'prices_idx', 0), .0005),
        'motor_vehicles_contrib_new_weight_pp': (contribution(motor, 'prices_idx'), .0005),
    }
    rows = _load_csv(REBASE_CSV)
    assert rows and REBASE_REQUIRED_COLS <= rows[0].keys()
    assert len(rows) == 8 and {r['metric'] for r in rows} == set(rebase) | {'limit'}, 'rebase key coverage'
    assert len({r['metric'] for r in rows}) == len(rows), 'duplicate rebase keys'
    for row in rows:
        if row['metric'] == 'limit':
            assert not row['value'] and row['note']
        else:
            value, tolerance = rebase[row['metric']]
            assert abs(_number(row['value']) - float(value)) <= tolerance + 1e-10, row['metric']
    sensitivity = {
        ('headline basis — chained volume', 'latest month', 'yoy_pct'): (growth('volume_idx', 12), .005),
        ('headline basis — current prices', 'latest month', 'yoy_pct'): (growth('prices_idx', 12), .005),
        ('headline basis — chained volume', 'latest month', 'sa_mom_pct'): (growth('volume_sa_idx', 1), .005),
        ('headline basis — current prices', 'latest month', 'sa_mom_pct'): (growth('prices_sa_idx', 1), .005),
        ('SA MoM window — 3-month change', f'{prior(3)} to {latest}', 'sa_3m_pct'): (growth('volume_sa_idx', 3), .005),
        ('SA MoM window — 3-month change', f'{prior(3)} to {latest}', 'sa_3m_pct_prices'): (growth('prices_sa_idx', 3), .005),
        ('contribution method — fixed-weight (prices)', 'latest month', 'sum_pp_vs_total_pp'):
            (sum(contribution(n, 'prices_idx') for n in covered), .00005),
        ('contribution method — approx (volume)', 'latest month', 'sum_pp_vs_total_pp'):
            (sum(contribution(n, 'volume_idx') for n in covered), .00005),
        ('weight set — 2025-based', 'latest month', 'basket_yoy_pct'): (new, .005),
        ('weight set — 2017-based', 'latest month', 'basket_yoy_pct'): (old, .005),
    }
    rows = _load_csv(SENS_CSV)
    assert rows and SENS_REQUIRED_COLS <= rows[0].keys()
    keys = [(r['variant'], r['window'], r['metric']) for r in rows]
    assert len(keys) == len(set(keys)) == len(sensitivity) and set(keys) == set(sensitivity), 'sensitivity key coverage'
    for key, row in zip(keys, rows):
        value, tolerance = sensitivity[key]
        assert abs(_number(row['value']) - float(value)) <= tolerance + 1e-10, key



def test_tableau_extract() -> None:
    rows = _load_csv(EXTRACT_CSV)
    assert rows, f"{EXTRACT_CSV.name} has no data rows"
    missing = EXTRACT_REQUIRED_COLS - set(rows[0].keys())
    assert not missing, f"{EXTRACT_CSV.name} missing columns: {sorted(missing)}"
    assert len(rows) >= 2000, f"only {len(rows)} extract rows — expected the monthly history"
    months = {r["month"] for r in rows}
    assert min(months) >= "2016-01", f"extract starts before 2016: {min(months)}"
    _july_anchors([r for r in rows if r["month"] == "2026-07-01"])


def test_levels_check() -> None:
    rows = _load_csv(LEVELS_CSV)
    expected = {"retail_sales": (4419, "SGD million"), "retail_sales_excl_mv": (3679, "SGD million"),
                "fb_sales": (1607, "SGD million"), "retail_online_share": (15.4, "%")}
    assert len(rows) == len(expected) and {r["metric"] for r in rows} == expected.keys()
    for r in rows:
        value, unit = expected[r["metric"]]
        assert r["period"] == "2026-07-01" and r["unit"] == unit, "wrong levels snapshot/unit"
        assert _number(r["release_value"]) == value and r["status"] == "match"
        diff = _number(r["calc_value"]) - value
        assert math.isclose(diff, _number(r["diff"]), abs_tol=1e-10)
        assert abs(diff) <= (0.5 if unit == "SGD million" else 0.05)


def test_contribution_reconciliation() -> None:
    rows = _load_csv(RECON_CSV)
    assert rows, "empty reconciliation history"
    assert len({(r["month"], r["series_group"]) for r in rows}) == len(rows)
    for r in rows:
        total, covered, residual = (_number(r[k]) for k in
                                   ("total_yoy_pct", "covered_contrib_prices_pp", "residual_prices_pp"))
        assert math.isclose(total - covered, residual, abs_tol=1e-10)
        assert r["series_group"] in ("retail", "fb")
        assert 0 < int(r["covered_industries"]) <= (11 if r["series_group"] == "retail" else 5)
        assert 0 < _number(r["covered_weight_pct"]) <= 100.2
    latest = max(r["month"] for r in rows)
    for group, n, weight in (("retail", 11, 86.1), ("fb", 5, 100)):
        row = next(r for r in rows if r["month"] == latest and r["series_group"] == group)
        assert int(row["covered_industries"]) == n
        assert math.isclose(_number(row["covered_weight_pct"]), weight, abs_tol=1e-8)
        if group == "fb":
            assert abs(_number(row["residual_prices_pp"])) <= 0.05
    for month, residual in (("2026-07-01", .0174), ("2026-06-01", .7088),
                            ("2026-05-01", .3201), ("2025-07-01", .4390)):
        row = next(r for r in rows if r["month"] == month and r["series_group"] == "retail")
        assert math.isclose(_number(row["residual_prices_pp"]), residual, abs_tol=.00005)
    sens = next(r for r in _load_csv(SENS_CSV) if r["variant"].startswith("contribution method — fixed-weight"))
    row = next(r for r in rows if r["month"] == latest and r["series_group"] == "retail")
    assert math.isclose(_number(sens["value"]), _number(row["covered_contrib_prices_pp"]), abs_tol=.00005)


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
              test_tableau_extract, test_levels_check, test_contribution_reconciliation,
              test_figures_present, test_banner_and_docs_present]
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
