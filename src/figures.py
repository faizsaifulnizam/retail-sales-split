"""S3 figures — code-generated, series style, light + dark (theme-adaptive). Run: python src/figures.py (repo root).

Produces (reports/figures/), each as a light/dark pair for `<picture>` README embeds:
  f1_headline[-dark].png   — stat cards + YoY and SA MoM history (volume vs current prices)
  f2_split[-dark].png      — ranked industry split (volume vs prices dumbbell) + contributions
  f3_watch[-dark].png      — small multiples: three industries to watch

Reads the parquet via DuckDB; re-runs sql/02 so figures always match the SQL. Long titles and
footnotes are width-checked at render size by pixel extent (not eyeballed); QA asserts cover
in-bounds text, suptitle clearance and pairwise annotation overlaps. Run twice and hash-compare
before commit (determinism receipt).
"""
import json
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.style import use_series_style  # noqa: E402

use_series_style()

import duckdb  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.textpath import TextPath  # noqa: E402

PARQUET_M = (ROOT / "data/processed/monthly.parquet").as_posix()
PARQUET_Q = (ROOT / "data/processed/quarterly.parquet").as_posix()
FIGDIR = ROOT / "reports/figures"
DPI = 200
MARGIN_PX = 40

LIGHT = dict(ink="#14293D", petrol="#22607B", burnt="#C0552B", teal="#2E7D6B",
             violet="#8A6EAF", brass="#B9975B", muted="#5C6B79", light="#C9C6BF",
             edge="white", face="#FBFBF9", suffix="")
DARK = dict(ink="#E7E3DC", petrol="#4C93B5", burnt="#D97E4F", teal="#45A08B",
            violet="#A78FC8", brass="#D4B87A", muted="#8B98A5", light="#435D73",
            edge="#14293D", face="#14293D", suffix="-dark")
T = LIGHT


def use_palette(p):
    global T
    T = p


MANIFEST = ROOT / "data/raw/pull_manifest.json"


def _source_date():
    try:
        ts = json.loads(MANIFEST.read_text(encoding="utf-8")).get("retrieved_at", "")
        return ts[:10] or None
    except Exception:
        return None


SRC = f"Source: SingStat Table Builder — Retail Sales Index (2025=100), pulled {_source_date() or 'n/a'}"


def q(con, sql):
    return con.sql(sql).fetchall()


def foot(fig, text):
    return fig.text(0.01, 0.012, text, fontsize=7.5, color=T["muted"], va="bottom")


def assert_clear(fig, pairs, label):
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    for a, b in pairs:
        ba, bb = a.get_window_extent(r), b.get_window_extent(r)
        ok = not ba.overlaps(bb)
        print(f"   [{'PASS' if ok else 'FAIL'}] clearance {label}")
        assert ok, f"{label}: text boxes overlap"


def assert_inbounds(fig, label, pad=3):
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    w, h = fig.canvas.get_width_height()
    bad = []
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_text().strip() or not t.get_visible():
            continue
        bb = t.get_window_extent(r)
        if bb.x0 < pad or bb.y0 < pad - 2 or bb.x1 > w - pad or bb.y1 > h - pad:
            bad.append((t.get_text()[:44].replace("\n", " / "), round(bb.x0), round(bb.y0), round(bb.x1), round(bb.y1)))
    ok = not bad
    print(f"   [{'PASS' if ok else 'FAIL'}] in-bounds {label} ({len(bad)} clipped)")
    for b in bad[:6]:
        print("       clipped:", b)
    assert ok, f"{label}: {len(bad)} text artist(s) clipped"


def assert_texts_clear(fig, label):
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    bad = []
    for ax in fig.axes:
        texts = [t for t in ax.texts if t.get_text().strip() and t.get_visible()]
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                if texts[i].get_window_extent(r).overlaps(texts[j].get_window_extent(r)):
                    bad.append((texts[i].get_text()[:32], texts[j].get_text()[:32]))
    ok = not bad
    print(f"   [{'PASS' if ok else 'FAIL'}] annotation overlaps {label} ({len(bad)})")
    for b in bad[:6]:
        print("       overlap:", b)
    assert ok, f"{label}: {len(bad)} annotation overlap(s)"


def save(fig, name):
    p = FIGDIR / name.replace(".png", T["suffix"] + ".png")
    fig.savefig(p)
    plt.close(fig)
    print(f"wrote {p.as_posix()}  ({p.stat().st_size} bytes)")


def text_px(s, size_pt):
    fp = FontProperties(family="Inter", size=size_pt)
    return TextPath((0, 0), s, prop=fp).get_extents().width / 72 * DPI


def assert_fits(s, size_pt, label, canvas_in):
    px = max(text_px(line, size_pt) for line in s.split("\n"))
    limit = canvas_in * DPI - MARGIN_PX
    ok = px <= limit
    print(f"   [{'PASS' if ok else 'FAIL'}] width {label}: {px:.0f}px vs {limit:.0f}px limit")
    assert ok, f"{label} too wide: {px:.0f}px > {limit:.0f}px"


def stat_card(fig, x, y, big, label, sub, color):
    fig.text(x, y, big, fontsize=25, color=color, ha="left", va="top", fontweight="semibold")
    fig.text(x, y - 0.075, label, fontsize=10.5, color=T["ink"], ha="left", va="top")
    fig.text(x, y - 0.112, sub, fontsize=8.5, color=T["muted"], ha="left", va="top")


def load_split():
    """Derived numbers live in one home: outputs/latest_split.csv (audited; memo = CSV = README)."""
    import csv as _csv
    with (ROOT / "outputs/latest_split.csv").open(encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    out = {}
    for r in rows:
        out[(r["series_group"], r["industry"])] = r
    return out


def latest_row(con, series_group, industry):
    r = q(con, f"""SELECT m.period, m.volume_idx, m.prices_idx, m.volume_sa_idx, m.prices_sa_idx
                   FROM monthly m
                   WHERE m.series_group = '{series_group}' AND m.industry = '{industry}'
                   ORDER BY m.period DESC LIMIT 1""")[0]
    return r


def fig1_headline(con, canvas_in=9.0):
    total = latest_row(con, "retail", "Total")
    split = load_split()
    tr = split[("retail", "Total")]
    period = total[0]
    plabel = f"{period:%B %Y}"
    title = f"Singapore retail sales, {plabel}: the value headline rose while real volumes fell"
    foottext = (f"{SRC} · release basis = current prices; analytical headline = chained volume (price effects removed)\n"
                "Retail trade only — F&B services are a separate index, never mixed in · SA MoM from the SA tables")
    assert_fits(title, 12.5, "F1 title", canvas_in)
    assert_fits(foottext, 7.5, "F1 footnote", canvas_in)

    fig = plt.figure(figsize=(canvas_in, 5.9))
    st = fig.suptitle(title, x=0.012, y=0.982, ha="left", fontsize=12.5, color=T["ink"])
    stat_card(fig, 0.035, 0.80, f"{float(tr['yoy_volume_pct']):+.1f}%", "Chained volume · YoY (original)",
              "the real-activity read", T["violet"])
    stat_card(fig, 0.28, 0.80, f"{float(tr['yoy_prices_pct']):+.1f}%", "Current prices · YoY (original)",
              "the release's basis", T["petrol"])
    stat_card(fig, 0.535, 0.80, f"{float(tr['sa_mom_volume_pct']):+.1f}%", "Chained volume · MoM (SA)",
              "one-month print", T["violet"])
    stat_card(fig, 0.78, 0.80, f"{float(tr['sa_mom_prices_pct']):+.1f}%", "Current prices · MoM (SA)",
              "release rounds to +0.9", T["petrol"])

    hist = q(con, """SELECT m.period, mm.yoy_volume_pct, mm.yoy_prices_pct, mm.sa_mom_volume_pct, mm.sa_mom_prices_pct
                     FROM monthly m JOIN monthly_metrics mm
                       ON mm.series_group = m.series_group AND mm.industry = m.industry AND mm.period = m.period
                     WHERE m.series_group = 'retail' AND m.industry = 'Total'
                     ORDER BY m.period""")
    xs = [r[0] for r in hist]

    ax0 = fig.add_axes([0.06, 0.10, 0.40, 0.475])
    yv = [r[1] for r in hist][-37:]
    yp = [r[2] for r in hist][-37:]
    x0 = xs[-37:]
    ax0.axhline(0, color=T["light"], lw=0.8)
    ax0.plot(x0, yv, color=T["violet"], lw=2.0)
    ax0.plot(x0, yp, color=T["petrol"], lw=2.0)
    ax0.annotate(f"volume {yv[-1]:+.1f}%", (x0[-1], yv[-1]), xytext=(-6, -12), textcoords="offset points",
                 fontsize=8.5, color=T["violet"], ha="right", va="top")
    ax0.annotate(f"prices {yp[-1]:+.1f}%", (x0[-1], yp[-1]), xytext=(-6, 8), textcoords="offset points",
                 fontsize=8.5, color=T["petrol"], ha="right", va="bottom")
    ax0.set_title("Year-on-year change, last 3 years (%)", fontsize=10, color=T["muted"])
    ax0.set_ylim(min(yv + yp) - 2.5, max(yv + yp) + 2.5)
    ax0.set_xlim(mdates.date2num(x0[0]) - 30, mdates.date2num(x0[-1]) + 40)
    ax0.set_xticks([date(y, 1, 1) for y in range(2024, 2027)])
    ax0.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ax1 = fig.add_axes([0.565, 0.10, 0.40, 0.475])
    mv = [r[3] for r in hist][-25:]
    mp = [r[4] for r in hist][-25:]
    x1 = xs[-25:]
    ax1.axhline(0, color=T["light"], lw=0.8)
    ax1.plot(x1, mv, color=T["violet"], lw=2.0)
    ax1.plot(x1, mp, color=T["petrol"], lw=2.0)
    ax1.annotate(f"volume {mv[-1]:+.1f}%", (x1[-1], mv[-1]), xytext=(-6, -12), textcoords="offset points",
                 fontsize=8.5, color=T["violet"], ha="right", va="top")
    ax1.annotate(f"prices {mp[-1]:+.1f}%", (x1[-1], mp[-1]), xytext=(-6, 8), textcoords="offset points",
                 fontsize=8.5, color=T["petrol"], ha="right", va="bottom")
    ax1.set_title("Month-on-month change, seasonally adjusted (%)", fontsize=10, color=T["muted"])
    ax1.set_ylim(min(mv + mp) - 1.5, max(mv + mp) + 1.5)
    ax1.set_xlim(mdates.date2num(x1[0]) - 30, mdates.date2num(x1[-1]) + 40)
    ax1.set_xticks([date(2025, 1, 1), date(2026, 1, 1)])
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    ftxt = foot(fig, foottext)
    assert_clear(fig, [(st, ax0.title), (ftxt, ax0.get_xticklabels()[-1]), (ftxt, ax1.get_xticklabels()[-1])],
                 "F1 suptitle/titles + footnote/ticks")
    assert_inbounds(fig, "F1")
    assert_texts_clear(fig, "F1")
    print(f"F1: {plabel} volume {float(tr['yoy_volume_pct']):+.2f}% · prices {float(tr['yoy_prices_pct']):+.2f}% · "
          f"vol SA MoM {float(tr['sa_mom_volume_pct']):+.2f}% · prices SA MoM {float(tr['sa_mom_prices_pct']):+.2f}%")
    save(fig, "f1_headline.png")


def fig2_split(con, canvas_in=9.0):
    split = load_split()
    rows = []
    for (g, name), r in split.items():
        if g != "retail" or name in ("Total", "Total (Excluding Motor Vehicles, Parts & Accessories)",
                                     "Computer & Telecommunications Equipment", "Optical Goods & Books", "Others"):
            continue
        if r["yoy_volume_pct"]:
            rows.append((name, float(r["yoy_volume_pct"]), float(r["yoy_prices_pct"]), float(r["contrib_prices_pp"])))
    rows.sort(key=lambda r: r[1])
    contrib_map = {r[0]: r[3] for r in rows}
    order = [r[0] for r in rows]
    labels = order[::-1]
    tot_p = float(split[("retail", "Total")]["yoy_prices_pct"])

    title = f"Who carried the latest print, who dragged it — {q(con, 'SELECT max(period) FROM monthly')[0][0]:%B %Y} retail split by industry"
    foottext = (f"Left: year-on-year change per industry — ● chained volume vs ● current prices (2025=100)\n"
                f"Right: contribution to the +{tot_p:.2f}% headline (current prices; published formula: weight × move ÷ prior-year total)\n"
                "Contributions exact on prices; the volume basis is a growth-rate split · 3 industries not published monthly (residual +0.017 pp)\n"
                f"{SRC}")
    assert_fits(title, 12.5, "F2 title", canvas_in)
    assert_fits(foottext, 7.5, "F2 footnote", canvas_in)

    fig = plt.figure(figsize=(canvas_in, 6.2))
    st = fig.suptitle(title, x=0.012, y=0.985, ha="left", fontsize=12.5, color=T["ink"])

    axl = fig.add_axes([0.315, 0.155, 0.42, 0.75])
    ys = list(range(len(labels)))
    for y, name in zip(ys, labels):
        v = next(r[1] for r in rows if r[0] == name)
        p = next(r[2] for r in rows if r[0] == name)
        axl.plot([v, p], [y, y], color=T["light"], lw=1.6, zorder=2)
        axl.scatter([v], [y], color=T["violet"], s=46, zorder=3)
        axl.scatter([p], [y], color=T["petrol"], s=46, zorder=3)
        # value labels flank the pair on the OUTER sides at dot height — no vertical stacking, no cross-row collisions
        if v <= p:
            axl.annotate(f"{v:+.1f}", (v, y), xytext=(-7, 0), textcoords="offset points",
                         ha="right", va="center", fontsize=7.5, color=T["violet"])
            axl.annotate(f"{p:+.1f}", (p, y), xytext=(7, 0), textcoords="offset points",
                         ha="left", va="center", fontsize=7.5, color=T["petrol"])
        else:
            axl.annotate(f"{v:+.1f}", (v, y), xytext=(7, 0), textcoords="offset points",
                         ha="left", va="center", fontsize=7.5, color=T["violet"])
            axl.annotate(f"{p:+.1f}", (p, y), xytext=(-7, 0), textcoords="offset points",
                         ha="right", va="center", fontsize=7.5, color=T["petrol"])
    axl.axvline(0, color=T["muted"], lw=0.9, ls=(0, (4, 3)))
    axl.set_yticks(ys)
    axl.set_yticklabels(labels, fontsize=8.5)
    axl.set_xlim(-17.5, 17.5)
    axl.set_xticks([-15, -10, -5, 0, 5, 10, 15])
    axl.set_ylim(-0.8, len(labels) - 0.2)
    axl.xaxis.grid(True)
    axl.yaxis.grid(False)
    axl.set_xlabel("year-on-year change, %", fontsize=9)
    axl.set_title("Year-on-year change — ● volume   ● current prices", fontsize=10, color=T["muted"], loc="left")

    axr = fig.add_axes([0.79, 0.155, 0.195, 0.75])
    cvals = [contrib_map.get(name, 0.0) for name in labels]
    colors = [T["petrol"] if c >= 0 else T["burnt"] for c in cvals]
    axr.barh(ys, cvals, color=colors, height=0.55)
    for y, c in zip(ys, cvals):
        off = 4 if c >= 0 else -4
        axr.annotate(f"{c:+.2f}", (c, y), xytext=(off, 0), textcoords="offset points",
                     ha="left" if c >= 0 else "right", va="center", fontsize=7.5, color=T["ink"])
    axr.axvline(0, color=T["muted"], lw=0.9)
    axr.set_yticks([])
    axr.set_xlim(-1.75, 1.75)
    axr.set_xticks([-1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5])
    axr.set_ylim(-0.8, len(labels) - 0.2)
    axr.xaxis.grid(True)
    axr.yaxis.grid(False)
    axr.set_xlabel("contribution, pp", fontsize=9)
    axr.set_title(f"Contribution to +{tot_p:.2f}%", fontsize=10, color=T["muted"], loc="left")

    fig.subplots_adjust()
    ftxt = foot(fig, foottext)
    assert_clear(fig, [(st, axl.title), (ftxt, axl.get_xticklabels()[-1]), (ftxt, axr.get_xticklabels()[-1])],
                 "F2 suptitle/titles + footnote/ticks")
    assert_inbounds(fig, "F2")
    assert_texts_clear(fig, "F2")
    print("F2: " + " · ".join(f"{n} vol {next(r[1] for r in rows if r[0] == n):+.1f}" for n in labels[:3]))
    save(fig, "f2_split.png")


def fig3_watch(con, canvas_in=9.0):
    watch = ["Supermarkets & Hypermarkets", "Watches & Jewellery", "Petrol Service Stations"]
    split = load_split()
    title = "Three industries to watch next month — the heavyweight, the carrier, and the diverging one"
    foottext = ("Chained volume vs current prices (2025=100), last 4 years · Supermarkets & Hypermarkets: 16.0% weight, the biggest drag\n"
                "Watches & Jewellery: carried the +1.5% headline · Petrol Service Stations: largest volume decline while its value held\n"
                f"{SRC}")
    assert_fits(title, 12.5, "F3 title", canvas_in)
    assert_fits(foottext, 7.5, "F3 footnote", canvas_in)

    fig = plt.figure(figsize=(canvas_in, 3.9))
    st = fig.suptitle(title, x=0.012, y=0.975, ha="left", fontsize=12.5, color=T["ink"])
    for i, name in enumerate(watch):
        ax = fig.add_axes([0.055 + i * 0.315, 0.20, 0.27, 0.60])
        hist = q(con, f"""SELECT m.period, m.volume_idx, m.prices_idx
                          FROM monthly m
                          WHERE m.series_group = 'retail' AND m.industry = '{name}'
                          ORDER BY m.period""")
        x = [r[0] for r in hist][-49:]
        v = [r[1] for r in hist][-49:]
        p = [r[2] for r in hist][-49:]
        yv = float(split[("retail", name)]["yoy_volume_pct"])
        yp = float(split[("retail", name)]["yoy_prices_pct"])
        ax.plot(x, v, color=T["violet"], lw=1.9)
        ax.plot(x, p, color=T["petrol"], lw=1.9)
        ax.annotate(f"vol {yv:+.1f}%", (x[-1], v[-1]), xytext=(-5, -11), textcoords="offset points",
                    ha="right", va="top", fontsize=7.5, color=T["violet"],
                    bbox=dict(facecolor=T["face"], edgecolor="none", pad=0.6, alpha=0.85))
        ax.annotate(f"pr {yp:+.1f}%", (x[-1], p[-1]), xytext=(-5, 6), textcoords="offset points",
                    ha="right", va="bottom", fontsize=7.5, color=T["petrol"],
                    bbox=dict(facecolor=T["face"], edgecolor="none", pad=0.6, alpha=0.85))
        short = name.replace("Service Stations", "Stations")
        ax.set_title(short, fontsize=9.5, color=T["muted"], loc="left")
        lo = min(v + p)
        hi = max(v + p)
        pad = (hi - lo) * 0.18 + 2
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xlim(mdates.date2num(x[0]) - 30, mdates.date2num(x[-1]) + 30)
        ax.set_xticks([date(2023, 1, 1), date(2025, 1, 1)])
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ftxt = foot(fig, foottext)
    assert_clear(fig, [(st, fig.axes[0].title), (ftxt, fig.axes[0].get_xticklabels()[-1]),
                       (ftxt, fig.axes[1].get_xticklabels()[-1]), (ftxt, fig.axes[2].get_xticklabels()[-1])],
                 "F3 suptitle/titles + footnote/ticks")
    assert_inbounds(fig, "F3")
    assert_texts_clear(fig, "F3")
    print("F3: " + " · ".join(f"{n}: vol {float(split[('retail', n)]['yoy_volume_pct']):+.1f} / pr {float(split[('retail', n)]['yoy_prices_pct']):+.1f}" for n in watch))
    save(fig, "f3_watch.png")


def main():
    import os

    os.chdir(ROOT)
    FIGDIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW monthly AS SELECT * FROM read_parquet('{PARQUET_M}')")
    con.execute(f"CREATE OR REPLACE VIEW quarterly AS SELECT * FROM read_parquet('{PARQUET_Q}')")
    con.execute((ROOT / "sql/02_metrics.sql").read_text(encoding="utf-8"))
    for palette in (LIGHT, DARK):
        use_palette(palette)
        use_series_style(dark=(palette is DARK))
        print(f"-- rendering {'dark' if palette['suffix'] else 'light'} set --")
        fig1_headline(con)
        fig2_split(con)
        fig3_watch(con)
    print("figures done — light + dark")


if __name__ == "__main__":
    main()
