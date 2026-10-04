"""Data audit — stdlib only, independent of the DuckDB pipeline by design.

Reads data/raw/tb-*.json + data/reference/*.csv and:
  1. profiles the 14 tables (rows, coverage, cells, numeric integrity),
  2. recomputes the July 2026 release cross-check (release Table 1/2 vs raw tables),
  3. reconciles contributions against the published total (weights x index moves),
  4. writes outputs/release_check.csv (committed receipt).

Run (repo root): python src/audit.py    -> exit 1 if any comparable row drifts beyond tolerance.
"""
import csv
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
REF = ROOT / "data/reference"
OUT = ROOT / "outputs"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NUM = re.compile(r"^-?\d+(\.\d+)?$")
# Percentage points: half of 0.1 pp release rounding plus 0.001 pp allowance
# for the published indices' three-decimal precision. Compare BEFORE rounding.
TOL = 0.051

RELEASE_REFERENCE = "release-2026-07-tables.csv"  # intentionally pinned; never guess a new release
_year, _month = map(int, RELEASE_REFERENCE.removeprefix("release-").removesuffix("-tables.csv").split("-"))
LATEST = f"{_year} {MONTHS[_month - 1]}"
PREV = f"{_year - 1} {MONTHS[_month - 1]}"


def midx(label):
    """'2026 Jul' -> 2026*12 + 7."""
    y, m = label.split()
    return int(y) * 12 + MONTHS.index(m) + 1


def mlabel(idx):
    return f"{(idx - 1) // 12:04d} {MONTHS[(idx - 1) % 12]}"


def load(tid):
    return json.loads((RAW / f"tb-{tid}.json").read_text(encoding="utf-8"))["Data"]


def series(d, name):
    for r in d["row"]:
        if r["rowText"] == name:
            return {c["key"]: float(c["value"]) for c in r["columns"]}
    raise KeyError(name)


def yoy(s, label=LATEST):
    return (s[label] / s[mlabel(midx(label) - 12)] - 1) * 100


def mom(s, label=LATEST):
    return (s[label] / s[mlabel(midx(label) - 1)] - 1) * 100


def profile():
    print("== profile (managed tables, per pull_manifest.json) ==")
    manifest = json.loads((RAW / "pull_manifest.json").read_text(encoding="utf-8"))
    total_cells = 0
    for fname in sorted(manifest["files"]):
        d = json.loads((RAW / fname).read_text(encoding="utf-8"))["Data"]
        rows = d["row"]
        cells = sum(len(r["columns"]) for r in rows)
        bad = sum(1 for r in rows for c in r["columns"] if not NUM.match(str(c["value"])))
        total_cells += cells
        if bad:
            raise ValueError(f"{fname}: {bad} non-numeric cells")
        if d["frequency"] == "Monthly":
            last = max((c["key"] for r in rows for c in r["columns"]), key=midx)
            if last != LATEST:
                raise ValueError(f"{fname}: raw reaches {last}; explicit release snapshot for that month required "
                                 f"(audit is pinned to {RELEASE_REFERENCE})")
        else:
            last = max(r["columns"][-1]["key"] for r in rows)
        print(f"  {d['id']}: {len(rows):2d} rows · {cells:5d} cells · latest {last:8s} · "
              f"{d['frequency']:9s} · {d['adjustmentType'] or 'n/a':24s} · updated {d['dataLastUpdated']} · non-numeric {bad}")
    print(f"  TOTAL: {total_cells} cells, 0 expected non-numeric")


def cross_check():
    print(f"\n== release cross-check — {LATEST} (release rounds to 0.1 pt; tolerance ±{TOL}) ==")
    with (REF / RELEASE_REFERENCE).open(encoding="utf-8") as f:
        rel_rows = list(csv.DictReader(f))
    prices = load("M602121")
    prices_sa = load("M602122")
    vol = load("M602201")
    vol_sa = load("M602202")
    val = load("M602171")
    fb_prices = load("M602131")
    fb_prices_sa = load("M602132")
    fb_vol = load("M602211")

    out_rows, mismatches = [], 0
    for r in rel_rows:
        group, name = r["series_group"], r["row"]
        src, cy, cm = "", None, None
        if group == "retail":
            if name == "Total (Excluding Motor Vehicles, Parts & Accessories)":
                src = "M602171 (value, excl-MV row)"
                s = series(val, "Retail Sales Value (Excluding Motor Vehicles, Parts & Accessories) - Estimated")
                cy = yoy(s)
            elif name in ("Computer & Telecommunications Equipment", "Optical Goods & Books", "Others"):
                src = "not in monthly Table Builder tables (release only)"
            else:
                src = "M602121/M602122"
                cy, cm = yoy(series(prices, name)), mom(series(prices_sa, name))
        else:
            src = "M602131/M602132"
            cy, cm = yoy(series(fb_prices, name)), mom(series(fb_prices_sa, name))
        ry, rm = float(r["rel_yoy_jul26_pct"]), float(r["rel_sa_mom_jul26_pct"])
        dy = None if cy is None else cy - ry
        dm = None if cm is None else cm - rm
        ok = (dy is None or abs(dy) <= TOL) and (dm is None or abs(dm) <= TOL)
        if not ok:
            mismatches += 1
        out_rows.append({
            "series_group": group, "row": name,
            "rel_yoy_jul26_pct": ry, "calc_yoy_jul26_pct": "" if cy is None else cy,
            "diff_yoy_pct": "" if dy is None else dy,
            "rel_sa_mom_jul26_pct": rm, "calc_sa_mom_jul26_pct": "" if cm is None else cm,
            "diff_sa_mom_pct": "" if dm is None else dm,
            "source_table": src, "status": ("not_recomputed" if cy is None and cm is None
                                             else "match" if ok else "MISMATCH"),
        })
        fmt = lambda v: f"{v:+7.2f}" if v is not None else "    n/a"
        print(f"  {group:6s} {name:56s} yoy rel {ry:+6.1f} calc {fmt(cy)} | mom rel {rm:+5.1f} calc {fmt(cm)}"
              f"  [{out_rows[-1]['status']}]")
    print(f"  comparable rows {sum(1 for r in out_rows if r['calc_yoy_jul26_pct'] != '')} "
          f"· mismatches {mismatches}")
    return out_rows, mismatches


def contributions():
    print("\n== contribution reconciliation (current prices, percentage points of growth) ==")
    with (REF / "rss-weights.csv").open(encoding="utf-8") as f:
        weights = list(csv.DictReader(f))
    bad = 0
    for group, tid in (("retail", "M602121"), ("fb", "M602131")):
        prices = load(tid)
        total = series(prices, "Total")
        group_weights = [r for r in weights if r["series_group"] == group]
        covered = [r for r in group_weights if group != "retail" or r["industry"] not in
                   ("Computer & Telecommunications Equipment", "Optical Goods & Books", "Others")]
        acc = 0.0
        for r in covered:
            s = series(prices, r["industry"])
            w = float(r["weight_2025_pct"])
            c = w * (s[LATEST] - s[PREV]) / total[PREV]
            if not math.isfinite(c) or w <= 0:
                bad += 1
            acc += c
            print(f"  {group} {r['industry']:46s} w {w:4.1f}% contribution {c:+.4f} pp")
        residual = (total[LATEST] / total[PREV] - 1) * 100 - acc
        print(f"  {group}: {len(covered)} industries sum {acc:+.4f} pp · residual {residual:+.4f} pp")
        if not math.isfinite(residual) or not covered:
            bad += 1
        if group == "fb":
            # Full F&B coverage can reconcile; the partial retail basket cannot.
            if len(covered) != 5 or abs(sum(float(r["weight_2025_pct"]) for r in covered) - 100) > 0.2:
                bad += 1
            if abs(residual) > 0.05:
                bad += 1
        else:
            if len(covered) != 11:
                bad += 1
            print("  retail residual: coverage, linking/aggregation and rounding; no near-zero bound")
    return bad


def headline_echo():
    vol, vol_sa, prices, prices_sa = load("M602201"), load("M602202"), load("M602121"), load("M602122")
    fb_vol, fb_prices = load("M602211"), load("M602131")
    t, ts = series(vol, "Total"), series(vol_sa, "Total")
    p, ps = series(prices, "Total"), series(prices_sa, "Total")
    ft = series(fb_vol, "Total")
    print(f"\n== headline echo ({LATEST}) ==")
    print(f"  volume (original): {t[LATEST]:.3f} vs {t[PREV]:.3f} -> YoY {yoy(t):+.2f}% · SA MoM {mom(ts):+.2f}%")
    print(f"  prices (original): {p[LATEST]:.3f} vs {p[PREV]:.3f} -> YoY {yoy(p):+.2f}% · SA MoM {mom(ps):+.2f}%")
    print(f"  F&B volume: YoY {yoy(ft):+.2f}% (kept separate)")


def levels_check():
    # Explicit July 2026 release snapshot (SGD million / percent), not dynamic constants.
    # A new release requires a new transcribed reference AND explicit levels below.
    if LATEST != "2026 Jul":
        raise ValueError("explicit levels snapshot required for the selected release")
    specs = [
        ("retail_sales", "SGD million", 4419.0, "M602171", "Retail Sales Value - Estimated"),
        ("retail_sales_excl_mv", "SGD million", 3679.0, "M602171",
         "Retail Sales Value (Excluding Motor Vehicles, Parts & Accessories) - Estimated"),
        ("fb_sales", "SGD million", 1607.0, "M602181", "Value Of Food & Beverage Sales - Estimated"),
        ("retail_online_share", "%", 15.4, "M602191", "Retail Trade"),
    ]
    rows, bad = [], 0
    for metric, unit, expected, tid, name in specs:
        calc = series(load(tid), name)[LATEST]
        diff = calc - expected
        # Release levels are rounded to a million dollars / 0.1 percent.
        ok = abs(diff) <= (0.5 if unit == "SGD million" else 0.05)
        bad += not ok
        rows.append(dict(metric=metric, period=f"{_year}-{_month:02d}-01", unit=unit,
                         release_value=expected, calc_value=calc, diff=diff,
                         status="match" if ok else "MISMATCH", source_table=tid))
        print(f"  {metric}: release {expected} vs raw {calc} {unit} [{rows[-1]['status']}]")
    return rows, bad


def main():
    profile()
    rows, bad = cross_check()
    levels, levels_bad = levels_check()
    bad += levels_bad + contributions()
    headline_echo()
    if not bad:
        OUT.mkdir(exist_ok=True)
        # Stage every receipt after ALL checks; validation failures preserve both files.
        staged = []
        try:
            for name, data in (("release_check.csv", rows), ("levels_check.csv", levels)):
                path = OUT / name
                tmp = path.with_suffix(".csv.tmp")
                staged.append((tmp, path))
                with tmp.open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
                    w.writeheader()
                    w.writerows(data)
            for tmp, path in staged:
                os.replace(tmp, path)
        finally:
            for tmp, _ in staged:
                tmp.unlink(missing_ok=True)
    print(f"\n{'ALL AUDIT CHECKS PASS' if bad == 0 else f'{bad} FAILURE(S)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
