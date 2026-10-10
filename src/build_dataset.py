"""Build the processed dataset: raw Table Builder JSON -> staging (sql/01) -> checks (sql/05) -> parquet.

Run (repo root): python src/build_dataset.py
Receipts printed: raw/staged cell reconciliation, per-check results. Exit 1 if any check fails.

Order matters: DuckDB reads the raw JSON directly; every check runs BEFORE the parquet is
written, and files are written to temp paths then atomically replaced — a failing run never
touches the existing outputs.
"""
import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.publication import promote
from src.lineage import verify_raw
STAGING = ROOT / "sql/01_staging.sql"
CHECKS = ROOT / "sql/05_checks.sql"
OUT_DIR = ROOT / "data/processed"


def q(con, sql):
    return con.sql(sql).fetchall()


def main():
    os.chdir(ROOT)  # sql/01 references data/raw and data/reference relatively
    verify_raw(ROOT / 'data/raw')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    con.execute(STAGING.read_text(encoding="utf-8"))

    raw_cells = q(con, "SELECT count(*) FROM long")[0][0]
    excluded = q(con, "SELECT count(*) FROM long WHERE idx_value IS NULL")[0][0]
    m_cells = q(con, """SELECT count(volume_idx) + count(volume_sa_idx) + count(prices_idx)
                             + count(prices_sa_idx) + count(value_sgd_m) + count(online_pct)
                        FROM monthly""")[0][0]
    q_cells = q(con, "SELECT count(volume_idx) + count(prices_idx) FROM quarterly")[0][0]
    staged = m_cells + q_cells
    m_rows = q(con, "SELECT count(*) FROM monthly")[0][0]
    q_rows = q(con, "SELECT count(*) FROM quarterly")[0][0]

    print(f"raw cells:    {raw_cells}  (14 tables, unnest of row x column)")
    print(f"staged cells: {staged}  (monthly {m_cells} across {m_rows} rows; quarterly {q_cells} across {q_rows} rows)")
    print("exclusion rules (per-rule counts):")
    print(f"    rule [value not numeric]: {excluded}")
    ok_recon = (staged + excluded) == raw_cells
    print(f"    [{'PASS' if ok_recon else 'FAIL'}] retained + excluded == raw cells "
          f"({staged} + {excluded} vs {raw_cells})")

    print("checks:")
    failed = not ok_recon
    for name, v in con.execute(CHECKS.read_text(encoding="utf-8")).fetchall():
        status = "PASS" if v == 0 else "FAIL"
        print(f"    [{status}] {name}  (violations: {v})")
        if v:
            failed = True

    if failed:
        print("checks failed — parquet NOT written (existing files left untouched)")
        sys.exit(1)

    staged = []
    for table, fname in (("monthly", "monthly.parquet"), ("quarterly", "quarterly.parquet")):
        out = OUT_DIR / fname
        tmp = OUT_DIR / (fname + ".tmp")
        con.table(table).write_parquet(str(tmp))
        staged.append((tmp, out))
    promote(staged)

    cov = q(con, """SELECT max(period), count(DISTINCT industry)
                    FROM monthly WHERE series_group = 'retail' AND volume_idx IS NOT NULL""")[0]
    print(f"coverage: latest month {cov[0]} · {cov[1]} retail industries with volume data")


if __name__ == "__main__":
    main()
