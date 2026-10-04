"""Real chart regressions; run with the pinned chart environment."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import figures as f


class FigureRegressionTests(unittest.TestCase):
    def test_split_labels_clear_footnote_and_legend_identifies_bases(self):
        con = f.duckdb.connect()
        con.execute("CREATE TABLE monthly AS SELECT DATE '2026-07-01' AS period")
        captured = []
        try:
            with patch.object(f, "save", side_effect=lambda fig, name: captured.append(fig)):
                f.fig2_split(con)
            fig = captured[0]
            fig.set_dpi(f.DPI)
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            foot = next(t for t in fig.texts if t.get_text().startswith("Left:"))
            for ax in fig.axes:
                for label in [ax.xaxis.label, *ax.get_xticklabels()]:
                    if label.get_text():
                        self.assertFalse(foot.get_window_extent(renderer).overlaps(
                            label.get_window_extent(renderer)), label.get_text())
            legend = fig.axes[0].get_legend()
            self.assertIsNotNone(legend, "a grey title is not a colour key")
            self.assertEqual([t.get_text() for t in legend.get_texts()],
                             ["chained volume", "current prices"])
            self.assertNotEqual(str(legend.legend_handles[0].get_color()),
                                str(legend.legend_handles[1].get_color()))
        finally:
            for fig in captured:
                f.plt.close(fig)
            con.close()
    def test_all_charts_reject_csv_from_a_different_month_before_save(self):
        con = f.duckdb.connect()
        con.execute("CREATE TABLE monthly AS SELECT * FROM read_parquet(?) "
                    "WHERE period < DATE '2026-07-01'", [f.PARQUET_M])
        con.execute((ROOT / "sql/02_metrics.sql").read_text(encoding="utf-8"))
        try:
            with patch.object(f, "save") as save:
                for render in (f.fig1_headline, f.fig2_split, f.fig3_watch):
                    with self.subTest(chart=render.__name__):
                        with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
                            render(con)
                save.assert_not_called()
        finally:
            f.plt.close("all")
            con.close()

    def test_failed_render_preserves_existing_report_and_site(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports/figures"
            site = root / "docs/img"
            report.mkdir(parents=True)
            site.mkdir(parents=True)
            for folder in (report, site):
                (folder / "fixture.png").write_bytes(b"previous image")
            fig = f.plt.figure()
            def fail(path, **kwargs):
                Path(path).write_bytes(b"partial render")
                raise OSError("render failure")
            try:
                with patch.object(f, "ROOT", root), patch.object(f, "FIGDIR", report), \
                     patch.object(fig, "savefig", side_effect=fail):
                    with self.assertRaisesRegex(OSError, "render failure"):
                        f.save(fig, "fixture.png")
                for folder in (report, site):
                    self.assertEqual((folder / "fixture.png").read_bytes(), b"previous image")
            finally:
                f.plt.close(fig)

    def test_future_chart_ticks_follow_the_data_window(self):
        if not Path(f.PARQUET_M).exists():
            self.skipTest("requires local processed data")
        con = f.duckdb.connect()
        con.execute(f"CREATE TABLE monthly AS SELECT * REPLACE ((period + INTERVAL 4 YEAR)::DATE AS period) FROM read_parquet('{f.PARQUET_M}')")
        con.execute((ROOT / "sql/02_metrics.sql").read_text(encoding="utf-8"))
        captured = []
        try:
            import csv
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "outputs").mkdir()
                with (ROOT / "outputs/latest_split.csv").open(encoding="utf-8") as source:
                    rows = list(csv.DictReader(source))
                for row in rows:
                    stamp = f.date.fromisoformat(row["latest_period"])
                    row["latest_period"] = str(stamp.replace(year=stamp.year + 4))
                with (root / "outputs/latest_split.csv").open("w", encoding="utf-8", newline="") as target:
                    writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
                    writer.writeheader()
                    writer.writerows(rows)
                with patch.object(f, "ROOT", root), patch.object(f, "save", side_effect=lambda fig, name: captured.append(fig)):
                    f.fig1_headline(con)
                    f.fig3_watch(con)
            for fig in captured:
                for ax in fig.axes:
                    dates = ax.lines[-1].get_xdata()
                    lo = f.mdates.date2num(dates[0]) - 40
                    hi = f.mdates.date2num(dates[-1]) + 40
                    for tick in ax.get_xticks():
                        self.assertGreaterEqual(tick, lo)
                        self.assertLessEqual(tick, hi)
        finally:
            for fig in captured:
                f.plt.close(fig)
            con.close()

    def test_headline_title_uses_current_signs_not_july_prose(self):
        if not Path(f.PARQUET_M).exists():
            self.skipTest("requires local processed data")
        import csv
        con = f.duckdb.connect()
        con.execute(f"CREATE VIEW monthly AS SELECT * FROM read_parquet('{f.PARQUET_M}')")
        con.execute((ROOT / "sql/02_metrics.sql").read_text(encoding="utf-8"))
        captured = []
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "outputs").mkdir()
                with (ROOT / "outputs/latest_split.csv").open(encoding="utf-8") as source:
                    rows = list(csv.DictReader(source))
                for row in rows:
                    if row["series_group"] == "retail" and row["industry"] == "Total":
                        row["yoy_prices_pct"], row["yoy_volume_pct"] = "-1.46", "1.28"
                with (root / "outputs/latest_split.csv").open("w", encoding="utf-8", newline="") as target:
                    writer = csv.DictWriter(target, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                with patch.object(f, "ROOT", root), patch.object(f, "save", side_effect=lambda fig, name: captured.append(fig)):
                    f.fig1_headline(con)
                title = captured[0]._suptitle.get_text()
                self.assertIn("value -1.5%", title)
                self.assertIn("volume +1.3%", title)
        finally:
            for fig in captured:
                f.plt.close(fig)
            con.close()

    def test_pull_date_is_singapore_date_even_with_utc_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"retrieved_at": "2026-10-03T23:30:00+00:00"}),
                                encoding="utf-8")
            with patch.object(f, "MANIFEST", manifest):
                self.assertEqual(f._source_date(), "2026-10-04")


if __name__ == "__main__":
    unittest.main()
