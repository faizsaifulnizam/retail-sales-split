"""Download the 14 SingStat Table Builder tables into data/raw/.

Source: Singapore Department of Statistics, Table Builder public API
(https://tablebuilder.singstat.gov.sg/api/table/tabledata/<id> — no key required).

The set (retail and F&B services kept strictly separate):

  RSI (retail)  M602201  chained volume, monthly            (primary headline)
                M602202  chained volume, monthly, SA        (SA MoM)
                M602121  current prices, monthly            (release basis)
                M602122  current prices, monthly, SA        (release SA MoM)
                M602171  retail sales value, S$M, monthly   (levels / excl-MV)
                M602191  online retail proportion, monthly  (context)
                M602141  current prices, quarterly          (Optical/Others detail)
                M602221  chained volume, quarterly          (Optical/Others detail)
  F&B (separate) M602211  chained volume, monthly
                M602212  chained volume, monthly, SA
                M602131  current prices, monthly
                M602132  current prices, monthly, SA
                M602181  F&B sales value, S$M, monthly
                M602271  online F&B proportion, monthly

Flow: GET tabledata -> .part file -> STRUCTURAL validation (series set, month/quarter
labels parse and are contiguous, values numeric, freshness floor) -> atomic replace.
A failed pull leaves the existing file untouched. On success writes
data/raw/pull_manifest.json (sha256, rows, coverage, series, dataLastUpdated, retrieval
time, derived release-page URL). Run: python src/download.py [--force]

Notes:
  - 'Computer & Telecommunications Equipment' is published monthly only for 1993–1996
    (a publisher gap; recent quarters exist in the quarterly tables). The validator
    asserts this stale row still ends before 2000 — if that changes, fail loudly.
  - Freshness floor: latest month must be >= 2026 Jul (quarterly >= 2026 2Q). A later
    re-pull moving past the floor is fine; a truncated/stale pull fails.
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request as u
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
MANIFEST = RAW / "pull_manifest.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
API = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MREG = re.compile(r"^(\d{4}) (" + "|".join(MONTHS) + r")$")
QREG = re.compile(r"^(\d{4}) ([1-4])Q$")
NUM = re.compile(r"^-?\d+(\.\d+)?$")

FLOOR_M = 2026 * 12 + 7   # 2026 Jul (build-time latest month)
FLOOR_Q = 2026 * 4 + 2    # 2026 2Q
STALE_END = 2000 * 12 + 12  # stale monthly rows must end at/before 2000

RSI_MONTHLY_SERIES = [
    "Total", "Department Stores", "Supermarkets & Hypermarkets",
    "Mini-Marts & Convenience Stores", "Food & Alcohol",
    "Motor Vehicles, Parts & Accessories", "Petrol Service Stations",
    "Cosmetics, Toiletries & Medical Goods", "Wearing Apparel & Footwear",
    "Furniture & Household Equipment", "Recreational Goods",
    "Watches & Jewellery", "Computer & Telecommunications Equipment",
]
RSI_QUARTERLY_SERIES = RSI_MONTHLY_SERIES + [
    "Optical Goods & Books", "Others",
    "Total (Excluding Motor Vehicles, Parts & Accessories)",
]
FB_MONTHLY_SERIES = [
    "Total", "Restaurants", "Fast Food Outlets", "Food Caterers", "Cafes",
    "Food Courts & Other Eating Places",
]
# In the four RSI index tables the Computer row is published monthly only for 1993–1996
# (recent quarters live in the quarterly tables); the online-share table's Computer row is current.
STALE_MONTHLY = {"Computer & Telecommunications Equipment"}

TABLES = [
    dict(id="M602201", group="retail", measure="volume_idx", freq="M", uom="Index",
         adj="Non-seasonally Adjusted", series=RSI_MONTHLY_SERIES, role="primary — chained volume headline",
         stale=STALE_MONTHLY),
    dict(id="M602202", group="retail", measure="volume_sa_idx", freq="M", uom="Index",
         adj="Seasonally Adjusted", series=RSI_MONTHLY_SERIES, role="SA MoM", stale=STALE_MONTHLY),
    dict(id="M602121", group="retail", measure="prices_idx", freq="M", uom="Index",
         adj="Non-seasonally Adjusted", series=RSI_MONTHLY_SERIES, role="release basis (current prices)",
         stale=STALE_MONTHLY),
    dict(id="M602122", group="retail", measure="prices_sa_idx", freq="M", uom="Index",
         adj="Seasonally Adjusted", series=RSI_MONTHLY_SERIES, role="release SA MoM", stale=STALE_MONTHLY),
    dict(id="M602171", group="retail", measure="value_sgd_m", freq="M", uom="Million Dollars",
         adj="", role="levels, S$M",
         series=["Retail Sales Value - Estimated",
                 "Retail Sales Value (Excluding Motor Vehicles, Parts & Accessories) - Estimated"]),
    dict(id="M602191", group="retail", measure="online_pct", freq="M", uom="Percentage",
         adj="", role="online share (context)",
         series=["Retail Trade", "Supermarkets & Hypermarkets",
                 "Computer & Telecommunications Equipment",
                 "Furniture & Household Equipment",
                 "Retail Trade (Excluding Motor Vehicles, Parts & Accessories)"]),
    dict(id="M602141", group="retail", measure="prices_idx", freq="Q", uom="Index",
         adj="Non-seasonally Adjusted", series=RSI_QUARTERLY_SERIES, role="quarterly detail"),
    dict(id="M602221", group="retail", measure="volume_idx", freq="Q", uom="Index",
         adj="Non-seasonally Adjusted", series=RSI_QUARTERLY_SERIES, role="quarterly detail"),
    dict(id="M602211", group="fb", measure="volume_idx", freq="M", uom="Index",
         adj="Non-seasonally Adjusted", series=FB_MONTHLY_SERIES, role="F&B chained volume"),
    dict(id="M602212", group="fb", measure="volume_sa_idx", freq="M", uom="Index",
         adj="Seasonally Adjusted", series=FB_MONTHLY_SERIES, role="F&B SA MoM"),
    dict(id="M602131", group="fb", measure="prices_idx", freq="M", uom="Index",
         adj="Non-seasonally Adjusted", series=FB_MONTHLY_SERIES, role="F&B current prices"),
    dict(id="M602132", group="fb", measure="prices_sa_idx", freq="M", uom="Index",
         adj="Seasonally Adjusted", series=FB_MONTHLY_SERIES, role="F&B SA MoM (prices)"),
    dict(id="M602181", group="fb", measure="value_sgd_m", freq="M", uom="Million Dollars",
         adj="", series=["Value Of Food & Beverage Sales - Estimated"], role="F&B levels, S$M"),
    dict(id="M602271", group="fb", measure="online_pct", freq="M", uom="Percentage",
         adj="", series=["Food & Beverage Services"], role="F&B online share (context)"),
]


def get(url, ref="https://tablebuilder.singstat.gov.sg/"):
    r = u.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Referer": ref})
    with u.urlopen(r, timeout=180) as resp:
        return resp.read()


def _fmt_month(idx):
    return f"{(idx - 1) // 12:04d} {MONTHS[(idx - 1) % 12]}"


def _fmt_quarter(idx):
    return f"{(idx - 1) // 4} Q{((idx - 1) % 4) + 1}"


def validate(text, spec):
    """Structural validation for one table. Returns (info, problems)."""
    problems = []
    try:
        j = json.loads(text)
    except Exception as e:  # noqa: BLE001
        return None, [f"not valid JSON: {e}"]
    if j.get("StatusCode") != 200 or not j.get("Data"):
        return None, [f"StatusCode {j.get('StatusCode')} / missing Data"]

    d = j["Data"]
    freq = "Monthly" if spec["freq"] == "M" else "Quarterly"
    if d.get("frequency") != freq:
        problems.append(f"frequency is {d.get('frequency')!r}, expected {freq!r}")
    if d.get("adjustmentType", "") != spec["adj"]:
        problems.append(f"adjustmentType is {d.get('adjustmentType')!r}, expected {spec['adj']!r}")
    rows = d.get("row") or []
    names = [r.get("rowText") for r in rows]
    if sorted(names) != sorted(spec["series"]):
        problems.append(f"series set mismatch: got {names}")

    regex = MREG if spec["freq"] == "M" else QREG
    per_row, current_rows, stale_rows = {}, 0, 0
    for r in rows:
        name = r.get("rowText")
        if r.get("uoM") != spec["uom"]:
            problems.append(f"row {name!r} uoM {r.get('uoM')!r}, expected {spec['uom']!r}")
        idxs, bad_keys, bad_vals = [], [], []
        for c in r.get("columns") or []:
            m = regex.match(c.get("key", ""))
            if not m:
                bad_keys.append(c.get("key"))
                continue
            if spec["freq"] == "M":
                idx = int(m.group(1)) * 12 + MONTHS.index(m.group(2)) + 1
            else:
                idx = int(m.group(1)) * 4 + int(m.group(2))
            idxs.append(idx)
            if not NUM.match(str(c.get("value", ""))):
                bad_vals.append((c.get("key"), c.get("value")))
        if bad_keys:
            problems.append(f"row {name!r}: unparseable labels {bad_keys[:4]}")
        if bad_vals:
            problems.append(f"row {name!r}: non-numeric values {bad_vals[:4]}")
        if not idxs:
            problems.append(f"row {name!r}: no usable columns")
            continue
        idxs.sort()
        if len(set(idxs)) != len(idxs):
            problems.append(f"row {name!r}: duplicate labels")
        if any(b - a != 1 for a, b in zip(idxs, idxs[1:])):
            problems.append(f"row {name!r}: labels not contiguous")
        fmt = _fmt_month if spec["freq"] == "M" else _fmt_quarter
        per_row[name] = {"n": len(idxs), "first": fmt(idxs[0]), "last": fmt(idxs[-1])}
        if name in spec.get("stale", ()) and spec["freq"] == "M":
            stale_rows += 1
            if idxs[-1] > STALE_END:
                problems.append(f"row {name!r} now reaches {per_row[name]['last']} — the stale-gap note must be re-examined")
        else:
            floor = FLOOR_M if spec["freq"] == "M" else FLOOR_Q
            if idxs[-1] < floor:
                problems.append(f"row {name!r}: latest {per_row[name]['last']} is below the freshness floor")
            else:
                current_rows += 1

    if problems:
        return None, problems
    all_first = min(v["first"] for v in per_row.values())
    all_last = max(v["last"] for v in per_row.values())
    return {
        "bytes": len(text),
        "sha256": hashlib.sha256(text).hexdigest(),
        "rows": len(rows),
        "current_rows": current_rows,
        "stale_rows": stale_rows,
        "coverage_min": all_first,
        "coverage_max": all_last,
        "series": per_row,
        "data_last_updated": d.get("dataLastUpdated", ""),
        "date_generated": d.get("dateGenerated", ""),
        "title": d.get("title", ""),
        "group_title": d.get("groupTitle", ""),
    }, []


def _release_page(latest_month):
    """Derive the SingStat release-page slug from the latest month, e.g. 'Jul 2026' -> ...jul2026."""
    mon, year = latest_month.split()
    return ("https://www.singstat.gov.sg/news/monthly-retail-sales-index-"
            f"and-food-beverage-services-index-{mon.lower()}{year}")


def write_manifest(infos, retrieved_at):
    months = [info["coverage_max"] for info in infos.values() if MREG.match(info["coverage_max"])]
    latest = max(months, key=lambda s: int(s[:4]) * 12 + MONTHS.index(s.split()[1]))
    m = {
        "source": "SingStat Table Builder — tablebuilder.singstat.gov.sg public API (no key)",
        "retrieved_at": retrieved_at,
        "release_page": _release_page(latest),
        "release_note": "RSI/FSI releases on the 5th of each month (or next working day); dataLastUpdated is the publisher's stamp",
        "files": {},
    }
    for spec in TABLES:
        info = infos[spec["id"]]
        m["files"][f"tb-{spec['id']}.json"] = {
            "table_id": spec["id"],
            "table_url": f"https://tablebuilder.singstat.gov.sg/table/TS/{spec['id']}",
            "group": spec["group"],
            "measure": spec["measure"],
            "role": spec["role"],
            **info,
        }
    MANIFEST.write_text(json.dumps(m, indent=2), encoding="utf-8")
    print("manifest:", MANIFEST.as_posix())
    for fname, info in m["files"].items():
        print(f"    {fname}: {info['bytes']} bytes · sha256 {info['sha256'][:12]}… · "
              f"{info['current_rows']} current rows · coverage {info['coverage_min']} → {info['coverage_max']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download even if the files exist")
    args = ap.parse_args()

    present = {spec["id"]: (RAW / f"tb-{spec['id']}.json") for spec in TABLES}
    if all(p.exists() for p in present.values()) and not args.force:
        print("raw files already present — use --force to refresh")
        for p in present.values():
            print("  ", p.as_posix())
        if not MANIFEST.exists():
            infos, ok = {}, True
            for spec in TABLES:
                info, problems = validate(present[spec["id"]].read_bytes(), spec)
                if problems:
                    ok = False
                    print(f"  [FAIL] existing tb-{spec['id']}.json: {problems}")
                infos[spec["id"]] = info
            if ok:
                mtime = datetime.fromtimestamp(present["M602201"].stat().st_mtime).astimezone().isoformat(timespec="seconds")
                write_manifest(infos, mtime)
        return

    infos = {}
    for spec in TABLES:
        tid = spec["id"]
        out = present[tid]
        part = out.with_name(out.name + ".part")
        url = f"{API}{tid}"
        print(f"downloading {tid} ({spec['role']}) …")
        try:
            data = get(url, ref=f"https://tablebuilder.singstat.gov.sg/table/TS/{tid}")
        except Exception as e:  # noqa: BLE001 — one retry, then fail loudly
            time.sleep(2)
            try:
                data = get(url, ref=f"https://tablebuilder.singstat.gov.sg/table/TS/{tid}")
            except Exception as e2:  # noqa: BLE001
                raise SystemExit(f"tb-{tid}.json: download failed ({e2}) — existing files left untouched")
        part.write_bytes(data)
        info, problems = validate(part.read_bytes(), spec)
        if problems:
            part.unlink(missing_ok=True)
            raise SystemExit(f"tb-{tid}.json failed structure validation — kept existing file:\n  - "
                             + "\n  - ".join(problems))
        part.replace(out)
        infos[tid] = info
        print(f"  ok: {info['bytes']} bytes · {info['current_rows']}/{info['rows']} current rows · "
              f"coverage {info['coverage_min']} → {info['coverage_max']} · updated {info['data_last_updated']}")

    write_manifest(infos, datetime.now().astimezone().isoformat(timespec="seconds"))


if __name__ == "__main__":
    sys.exit(main())
