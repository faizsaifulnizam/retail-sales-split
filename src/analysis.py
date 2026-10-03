"""The split — latest month: headline, industry split, contributions, rebase read, sensitivity.

Run (repo root): python src/analysis.py
Writes (atomic replace):
  outputs/latest_split.csv   (T1 — industry, latest YoY, prev YoY, weights, contributions)
  outputs/rebase_read.csv    (weight changes + weight-swap counterfactual + limits)
  outputs/sensitivity.csv    (basis / contribution-method / MoM-window / weight-set variants)
Receipts printed: contribution identity asserts, stdlib hand-checks, reconciliation.

Method notes (stated, not implied):
  - Contributions are exact on CURRENT PRICES: the published formula is I = Σ wᵢ·Lᵢ
    (weights × industry indices), so contributionᵢ = wᵢ·ΔLᵢ ÷ I_prev × 100 (pp of growth).
    The three industries without monthly Table Builder data (Computer, Optical, Others)
    leave a residual, printed and checked.
  - Chained volume is chain-linked with previous years' weights; the same arithmetic is
    an APPROXIMATION there — labelled, and never presented as exact.
"""
import csv
import json
import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
WEIGHTS = ROOT / "data/reference/rss-weights.csv"
NOT_MONTHLY = ("Computer & Telecommunications Equipment", "Optical Goods & Books", "Others")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def q(con, sql):
    return con.sql(sql).fetchall()


def r2(v):
    return None if v is None else round(float(v), 2)


def r3(v):
    return None if v is None else round(float(v), 3)


def write_csv(path, rows, cols):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    print(f"wrote {path.relative_to(ROOT).as_posix()}  ({len(rows)} rows)")


def midx(label):
    y, m = label.split()
    return int(y) * 12 + MONTHS.index(m) + 1


def mlabel(idx):
    return f"{(idx - 1) // 12:04d} {MONTHS[(idx - 1) % 12]}"


def load_raw(tid):
    d = json.loads((ROOT / f"data/raw/tb-{tid}.json").read_text(encoding="utf-8"))["Data"]
    return {r["rowText"]: {c["key"]: float(c["value"]) for c in r["columns"]} for r in d["row"]}


def main():
    os.chdir(ROOT)
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    for name, pq in (("monthly", "data/processed/monthly.parquet"),
                     ("quarterly", "data/processed/quarterly.parquet")):
        con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{pq}')")
    con.execute((ROOT / "sql/02_metrics.sql").read_text(encoding="utf-8"))

    weights = {}
    for r in csv.DictReader(WEIGHTS.open(encoding="utf-8")):
        weights[(r["series_group"], r["industry"])] = (float(r["weight_2017_pct"]), float(r["weight_2025_pct"]))

    latest = q(con, "SELECT max(period) FROM monthly")[0][0]
    prev12 = f"{(latest.year - 1):04d}-{latest.month:02d}-01"
    latest_s = str(latest)
    prev_s = prev12
    print(f"latest month: {latest_s} · YoY vs {prev_s} · SA MoM vs previous month")

    # ---- headline + split rows ----
    split = q(con, "SELECT * FROM latest_split ORDER BY series_group, industry")
    raw_idx = {}
    for row in q(con, f"""SELECT series_group, industry, period, prices_idx, volume_idx, prices_sa_idx, volume_sa_idx, value_sgd_m
                          FROM monthly WHERE period IN (DATE '{latest_s}', DATE '{prev_s}')"""):
        raw_idx[(row[0], row[1], str(row[2]))] = dict(prices=row[3], volume=row[4],
                                                      prices_sa=row[5], volume_sa=row[6], value=row[7])

    # totals for normalisation (the published totals, both bases)
    I_prev = raw_idx[("retail", "Total", prev_s)]["prices"]
    V_prev = raw_idx[("retail", "Total", prev_s)]["volume"]
    Ifb_prev = raw_idx[("fb", "Total", prev_s)]["prices"]
    Vfb_prev = raw_idx[("fb", "Total", prev_s)]["volume"]

    out_rows = []
    full = {}
    sums = {"retail": dict(cp=0.0, cv=0.0, n=0), "fb": dict(cp=0.0, cv=0.0, n=0)}
    for r in split:
        g, industry = r[0], r[1]
        w17, w25 = weights.get((g, industry), (None, None))
        cp = cv = None
        if industry not in NOT_MONTHLY and r[2] == latest:
            a = raw_idx[(g, industry, latest_s)]
            b = raw_idx[(g, industry, prev_s)]
            base_p = I_prev if g == "retail" else Ifb_prev
            base_v = V_prev if g == "retail" else Vfb_prev
            if a["prices"] is not None and b["prices"] is not None and w25:
                cp = (w25 / 100.0) * (a["prices"] - b["prices"]) / base_p * 100
                sums[g]["cp"] += cp
                sums[g]["n"] += 1
            if a["volume"] is not None and b["volume"] is not None and w25:
                cv = (w25 / 100.0) * (a["volume"] - b["volume"]) / base_v * 100
                sums[g]["cv"] += cv
        note = ""
        yoy_p, prev_yoy_p = r[4], r[8]
        if industry == "Computer & Telecommunications Equipment":
            note = "monthly index series ends 1996-08 (publisher gap); quarterly tables carry it to 2026 Q2; release quotes +5.1% YoY (current prices)"
        elif industry in ("Optical Goods & Books", "Others"):
            note = "not in monthly Table Builder exports — quarterly only; release quotes its monthly YoY (current prices)"
        elif industry == "Total (Excluding Motor Vehicles, Parts & Accessories)":
            a = raw_idx.get((g, industry, latest_s), {})
            b = raw_idx.get((g, industry, prev_s), {})
            if a.get("value") and b.get("value"):
                yoy_p = (a["value"] / b["value"] - 1) * 100
            # prior-month YoY: Jun 2026 vs Jun 2025
            vm = q(con, f"""SELECT value_sgd_m FROM monthly WHERE series_group='{g}'
                            AND industry='{industry}' AND period IN (DATE '{latest_s}' - INTERVAL 1 MONTH,
                                                                     DATE '{latest_s}' - INTERVAL 13 MONTH)
                            ORDER BY period""")
            if len(vm) == 2 and vm[0][0] and vm[1][0]:
                prev_yoy_p = (vm[1][0] / vm[0][0] - 1) * 100
            note = "value series (S$M per month) — YoY at current prices; no SA series (release quotes SA MoM +0.7)"
        elif g == "fb" and industry == "Total":
            note = "F&B services — a separate index, never combined with retail"
        full[(g, industry)] = (cp, cv)
        out_rows.append({
            "series_group": g, "industry": industry, "latest_period": r[2],
            "yoy_volume_pct": r2(r[3]), "yoy_prices_pct": r2(yoy_p),
            "sa_mom_volume_pct": r2(r[5]), "sa_mom_prices_pct": r2(r[6]),
            "prev_yoy_volume_pct": r2(r[7]), "prev_yoy_prices_pct": r2(prev_yoy_p),
            "weight_2017_pct": w17, "weight_2025_pct": w25,
            "contrib_prices_pp": r3(cp), "contrib_volume_approx_pp": r3(cv), "note": note,
        })

    # ---- receipts: contribution identity ----
    tot_p = (raw_idx[("retail", "Total", latest_s)]["prices"] - I_prev) / I_prev * 100
    tot_v = (raw_idx[("retail", "Total", latest_s)]["volume"] - V_prev) / V_prev * 100
    res_p = tot_p - sums["retail"]["cp"]
    res_v = tot_v - sums["retail"]["cv"]
    print(f"\ncontribution reconciliation (retail, {sums['retail']['n']} industries):")
    print(f"  current prices (exact formula):  Σ {sums['retail']['cp']:+.3f} pp vs total {tot_p:+.3f} pp -> residual {res_p:+.3f} pp")
    print(f"  chained volume (approximate):    Σ {sums['retail']['cv']:+.3f} pp vs total {tot_v:+.3f} pp -> residual {res_v:+.3f} pp")
    assert abs(res_p) <= 0.05, f"prices contribution identity off by {res_p:.3f} pp"
    assert abs(res_v) <= 0.20, f"volume contribution approx off by {res_v:.3f} pp"
    ftot_p = (raw_idx[("fb", "Total", latest_s)]["prices"] - Ifb_prev) / Ifb_prev * 100
    fres_p = ftot_p - sums["fb"]["cp"]
    print(f"  F&B (separate, current prices): Σ {sums['fb']['cp']:+.3f} pp vs total {ftot_p:+.3f} pp -> residual {fres_p:+.3f} pp")
    assert abs(fres_p) <= 0.05, f"F&B contribution identity off by {fres_p:.3f} pp"

    # ---- stdlib hand-checks (independent of DuckDB) ----
    pr = load_raw("M602121")
    vo = load_raw("M602201")
    latest_label = f"{latest.year} {MONTHS[latest.month - 1]}"
    lw = latest_label
    prev_l = mlabel(midx(latest_label) - 12)
    wj_prev, wj_now = pr["Watches & Jewellery"][prev_l], pr["Watches & Jewellery"][lw]
    hand_wj = (11.6 / 100) * (wj_now - wj_prev) / pr["Total"][prev_l] * 100
    hand_tot = (pr["Total"][lw] / pr["Total"][prev_l] - 1) * 100
    hand_vol = (vo["Total"][lw] / vo["Total"][prev_l] - 1) * 100
    pipeline_wj = full[("retail", "Watches & Jewellery")][0]
    print("\nstdlib hand-checks (raw JSON, independent of DuckDB):")
    print(f"  W&J contribution: hand {hand_wj:+.6f} vs pipeline {pipeline_wj:+.6f} pp")
    print(f"  total prices YoY: hand {hand_tot:+.6f}% vs pipeline {tot_p:+.6f}%")
    print(f"  total volume YoY: hand {hand_vol:+.6f}% vs pipeline {tot_v:+.6f}%")
    assert abs(hand_wj - pipeline_wj) < 1e-6
    assert abs(hand_tot - tot_p) < 1e-6
    assert abs(hand_vol - tot_v) < 1e-6

    # ---- rebase read ----
    w17_mv, w25_mv = weights[("retail", "Motor Vehicles, Parts & Accessories")]
    mv_d = raw_idx[("retail", "Motor Vehicles, Parts & Accessories", latest_s)]["prices"] - \
           raw_idx[("retail", "Motor Vehicles, Parts & Accessories", prev_s)]["prices"]
    mv_old = (w17_mv / 100) * mv_d / I_prev * 100
    mv_new = (w25_mv / 100) * mv_d / I_prev * 100
    g_new = sum(w25 * raw_idx[("retail", i, latest_s)]["prices"]
                for (gr, i), (w17, w25) in weights.items()
                if gr == "retail" and i not in NOT_MONTHLY) / \
            sum(w25 * raw_idx[("retail", i, prev_s)]["prices"]
                for (gr, i), (w17, w25) in weights.items()
                if gr == "retail" and i not in NOT_MONTHLY) * 100 - 100
    g_old = sum(w17 * raw_idx[("retail", i, latest_s)]["prices"]
                for (gr, i), (w17, w25) in weights.items()
                if gr == "retail" and i not in NOT_MONTHLY) / \
            sum(w17 * raw_idx[("retail", i, prev_s)]["prices"]
                for (gr, i), (w17, w25) in weights.items()
                if gr == "retail" and i not in NOT_MONTHLY) * 100 - 100
    print(f"\nrebase read (11-industry basket, same indices, different weights):")
    print(f"  basket YoY under 2025 weights {g_new:+.2f}% vs 2017 weights {g_old:+.2f}% -> weight effect {g_new - g_old:+.2f} pp")
    print(f"  Motor Vehicles contribution: old weight {mv_old:+.3f} pp -> new weight {mv_new:+.3f} pp")
    rebase_rows = [
        {"metric": "basket_yoy_2025_weights_pct", "value": r2(g_new), "note": "11 monthly industries, same indices, 2025-based weights"},
        {"metric": "basket_yoy_2017_weights_pct", "value": r2(g_old), "note": "same basket re-aggregated under 2017-based weights"},
        {"metric": "weight_effect_pp", "value": r2(g_new - g_old), "note": "weights only, holding industry indices fixed"},
        {"metric": "motor_vehicles_weight_2017_pct", "value": w17_mv, "note": "info paper Chart 1"},
        {"metric": "motor_vehicles_weight_2025_pct", "value": w25_mv, "note": "info paper Chart 1 (share fell 3.3pp)"},
        {"metric": "motor_vehicles_contrib_old_weight_pp", "value": r3(mv_old), "note": "MV contribution to +1.46% under old weight"},
        {"metric": "motor_vehicles_contrib_new_weight_pp", "value": r3(mv_new), "note": "MV contribution under new weight"},
        {"metric": "limit", "value": None, "note": "SSIC 2025 definitional moves (motorcycles into MV; musical instruments into Rec; Cafes split in FSI) are not reversible from published data; pre-2026 values are linked, not recalculated"},
    ]

    # ---- sensitivity ----
    vol_sa = {str(r[0]): r[1] for r in q(con, f"""SELECT period, volume_sa_idx FROM monthly
                                                   WHERE series_group='retail' AND industry='Total'
                                                     AND period >= DATE '{latest_s}' - INTERVAL 3 MONTH""")}
    pr_sa = {str(r[0]): r[1] for r in q(con, f"""SELECT period, prices_sa_idx FROM monthly
                                                   WHERE series_group='retail' AND industry='Total'
                                                     AND period >= DATE '{latest_s}' - INTERVAL 3 MONTH""")}
    labels = sorted(vol_sa)
    sa_3m_vol = (vol_sa[labels[-1]] / vol_sa[labels[0]] - 1) * 100
    sa_3m_pr = (pr_sa[labels[-1]] / pr_sa[labels[0]] - 1) * 100
    # 1-month SA changes straight from the SA table (previous month = latest - 1)
    m1 = q(con, f"""SELECT volume_sa_idx, prices_sa_idx FROM monthly
                    WHERE series_group='retail' AND industry='Total' AND period = DATE '{latest_s}' - INTERVAL 1 MONTH""")[0]
    m0 = q(con, f"""SELECT volume_sa_idx, prices_sa_idx FROM monthly
                    WHERE series_group='retail' AND industry='Total' AND period = DATE '{latest_s}'""")[0]
    sa_1m_vol = (m0[0] / m1[0] - 1) * 100
    sa_1m_pr = (m0[1] / m1[1] - 1) * 100
    sens_rows = [
        {"variant": "headline basis — chained volume", "window": "latest month", "metric": "yoy_pct", "value": r2(tot_v), "note": "the repo's analytical headline"},
        {"variant": "headline basis — current prices", "window": "latest month", "metric": "yoy_pct", "value": r2(tot_p), "note": "the release's basis"},
        {"variant": "headline basis — chained volume", "window": "latest month", "metric": "sa_mom_pct", "value": r2(sa_1m_vol), "note": "seasonally adjusted"},
        {"variant": "headline basis — current prices", "window": "latest month", "metric": "sa_mom_pct", "value": r2(sa_1m_pr), "note": "seasonally adjusted (release rounds to +0.9)"},
        {"variant": "SA MoM window — 3-month change", "window": f"{labels[0]} to {labels[-1]}", "metric": "sa_3m_pct", "value": r2(sa_3m_vol), "note": "chained volume, SA; longer window smooths single-month noise"},
        {"variant": "SA MoM window — 3-month change", "window": f"{labels[0]} to {labels[-1]}", "metric": "sa_3m_pct_prices", "value": r2(sa_3m_pr), "note": "current prices, SA"},
        {"variant": "contribution method — exact (prices)", "window": "latest month", "metric": "sum_pp_vs_total_pp", "value": r2(sums["retail"]["cp"]), "note": f"vs total {tot_p:+.2f} pp; residual {res_p:+.3f} pp (3 industries not monthly)"},
        {"variant": "contribution method — approx (volume)", "window": "latest month", "metric": "sum_pp_vs_total_pp", "value": r2(sums["retail"]["cv"]), "note": f"vs total {tot_v:+.2f} pp; chain-linked -> approximation, residual {res_v:+.3f} pp"},
        {"variant": "weight set — 2025-based", "window": "latest month", "metric": "basket_yoy_pct", "value": r2(g_new), "note": "11-industry basket"},
        {"variant": "weight set — 2017-based", "window": "latest month", "metric": "basket_yoy_pct", "value": r2(g_old), "note": "same indices, old weights"},
    ]

    write_csv(OUT / "latest_split.csv", out_rows,
              ["series_group", "industry", "latest_period", "yoy_volume_pct", "yoy_prices_pct",
               "sa_mom_volume_pct", "sa_mom_prices_pct", "prev_yoy_volume_pct", "prev_yoy_prices_pct",
               "weight_2017_pct", "weight_2025_pct", "contrib_prices_pp", "contrib_volume_approx_pp", "note"])
    write_csv(OUT / "rebase_read.csv", rebase_rows, ["metric", "value", "note"])
    write_csv(OUT / "sensitivity.csv", sens_rows, ["variant", "window", "metric", "value", "note"])

    # ---- dashboard-ready extract (monthly industry series + contributions over time) ----
    totals = {g: {str(p): v for p, v in q(con, f"""SELECT period, prices_idx FROM monthly
                    WHERE series_group='{g}' AND industry='Total'""")} for g in ("retail", "fb")}
    ext_rows = []
    for row in q(con, """SELECT m.series_group, m.industry, m.period, m.volume_idx, m.volume_sa_idx,
                                m.prices_idx, m.prices_sa_idx, mm.yoy_volume_pct, mm.yoy_prices_pct
                         FROM monthly m JOIN monthly_metrics mm
                           ON mm.series_group = m.series_group AND mm.industry = m.industry
                          AND mm.period = m.period
                         WHERE m.period >= DATE '2016-01-01'
                         ORDER BY m.series_group, m.industry, m.period"""):
        g, industry, period = row[0], row[1], str(row[2])
        w17, w25 = weights.get((g, industry), (None, None))
        contrib = None
        if w25 and row[5] is not None:
            prev12 = q(con, f"""SELECT prices_idx FROM monthly WHERE series_group='{g}' AND industry='{industry}'
                                AND period = DATE '{period}' - INTERVAL 12 MONTH""")
            base = totals[g].get(str(q(con, f"SELECT (DATE '{period}' - INTERVAL 12 MONTH)::DATE")[0][0]))
            if prev12 and prev12[0][0] and base:
                contrib = (w25 / 100.0) * (row[5] - prev12[0][0]) / base * 100
        ext_rows.append({"month": period, "series_group": g, "industry": industry,
                         "volume_idx": row[3], "volume_sa_idx": row[4],
                         "prices_idx": row[5], "prices_sa_idx": row[6],
                         "yoy_volume_pct": r2(row[7]), "yoy_prices_pct": r2(row[8]),
                         "contrib_prices_pp": r3(contrib)})
    write_csv(OUT / "tableau_extract.csv", ext_rows,
              ["month", "series_group", "industry", "volume_idx", "volume_sa_idx", "prices_idx",
               "prices_sa_idx", "yoy_volume_pct", "yoy_prices_pct", "contrib_prices_pp"])

    # top movers receipt
    ranked = sorted([r for r in out_rows if r["series_group"] == "retail" and r["contrib_prices_pp"] is not None],
                    key=lambda r: r["contrib_prices_pp"])
    print("\ntop contributors to the +%.2f%% (current prices):" % tot_p)
    for r in ranked[:3] + [{"industry": "...", "contrib_prices_pp": None}] + ranked[-3:]:
        if r["contrib_prices_pp"] is None:
            print("   ...")
        else:
            print(f"   {r['industry']:46s} {r['contrib_prices_pp']:+.3f} pp (weight {r['weight_2025_pct']}%)")
    print("\nanalysis done.")


if __name__ == "__main__":
    sys.exit(main())
