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
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
REF = ROOT / "data/reference"
OUT = ROOT / "outputs"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NUM = re.compile(r"^-?\d+(\.\d+)?$")
TOL = 0.06  # release rounds to 0.1 pt; recomputation tolerance

LATEST = "2026 Jul"
PREV = "2025 Jul"


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
        last = max(r["columns"][-1]["key"] for r in rows)
        print(f"  {d['id']}: {len(rows):2d} rows · {cells:5d} cells · latest {last:8s} · "
              f"{d['frequency']:9s} · {d['adjustmentType'] or 'n/a':24s} · updated {d['dataLastUpdated']} · non-numeric {bad}")
    print(f"  TOTAL: {total_cells} cells, 0 expected non-numeric")


def cross_check():
    print(f"\n== release cross-check — {LATEST} (release rounds to 0.1 pt; tolerance ±{TOL}) ==")
    rel_rows = list(csv.DictReader((REF / "release-2026-07-tables.csv").open(encoding="utf-8")))
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
        dy = None if cy is None else round(cy - ry, 3)
        dm = None if cm is None else round(cm - rm, 3)
        ok = (dy is None or abs(dy) <= TOL) and (dm is None or abs(dm) <= TOL)
        if not ok:
            mismatches += 1
        out_rows.append({
            "series_group": group, "row": name,
            "rel_yoy_jul26_pct": ry, "calc_yoy_jul26_pct": "" if cy is None else round(cy, 2),
            "diff_yoy_pct": "" if dy is None else dy,
            "rel_sa_mom_jul26_pct": rm, "calc_sa_mom_jul26_pct": "" if cm is None else round(cm, 2),
            "diff_sa_mom_pct": "" if dm is None else dm,
            "source_table": src, "status": "match" if ok else "MISMATCH",
        })
        fmt = lambda v: f"{v:+7.2f}" if v is not None else "    n/a"
        print(f"  {group:6s} {name:56s} yoy rel {ry:+6.1f} calc {fmt(cy)} | mom rel {rm:+5.1f} calc {fmt(cm)}"
              f"  [{'ok' if ok else 'MISMATCH'}]")
    OUT.mkdir(exist_ok=True)
    with (OUT / "release_check.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"  wrote outputs/release_check.csv · comparable rows {sum(1 for r in out_rows if r['calc_yoy_jul26_pct'] != '')} "
          f"· mismatches {mismatches}")
    return mismatches


def contributions():
    print("\n== contribution reconciliation (current prices, weights x index moves) ==")
    prices = load("M602121")
    weights = {}
    for r in csv.DictReader((REF / "rss-weights.csv").open(encoding="utf-8")):
        if r["series_group"] == "retail":
            weights[r["industry"]] = float(r["weight_2025_pct"])
    total = series(prices, "Total")
    d_total = total[LATEST] - total[PREV]
    acc = 0.0
    for name, w in weights.items():
        if name in ("Computer & Telecommunications Equipment", "Optical Goods & Books", "Others"):
            continue
        s = series(prices, name)
        c = (w / 100.0) * (s[LATEST] - s[PREV])
        acc += c
        print(f"  {name:46s} w {w:4.1f}%  contrib {c:+6.3f} pts")
    residual = d_total - acc
    print(f"  11 industries sum {acc:+.3f} pts · total move {d_total:+.3f} pts · residual {residual:+.3f} pts")
    ok = abs(residual) <= 0.05
    print(f"  [{'PASS' if ok else 'FAIL'}] residual within ±0.05 pts (three industries not published monthly)")
    return 0 if ok else 1


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


def main():
    profile()
    bad = cross_check()
    bad += contributions()
    headline_echo()
    print(f"\n{'ALL AUDIT CHECKS PASS' if bad == 0 else f'{bad} FAILURE(S)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
