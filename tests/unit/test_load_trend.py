"""Load-test trend tracking: history file, per-endpoint comparison and the regression gate."""
import json

import pytest

from scripts import load_trend

pytestmark = pytest.mark.unit

CSV_HEADER = ("Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,"
              "Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,"
              "50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%")


def write_csv(path, issues_p95=170, total_p95=160):
    path.write_text("\n".join([
        CSV_HEADER,
        f"GET,GET /issues,375,0,110,119.7,76.5,236.2,22098.2,6.35,0.0,110,120,130,140,160,{issues_p95},210,230,240,240,240",
        "GET,GET /repo,199,1,31,33.9,22.7,108.9,2155.0,3.37,0.0,31,34,36,39,49,53,66,73,110,110,110",
        f",Aggregated,574,1,70,76.8,22.7,236.2,15418.6,14.67,0.0,70,100,110,120,140,{total_p95},180,200,240,240,240",
    ]))
    return path


def run(p95: float, label: str = "old") -> dict:
    return {"label": label, "stats": {"Aggregated": {"requests": 1, "failures": 0, "median": 1, "p95": p95},
                                      "GET /issues": {"requests": 1, "failures": 0, "median": 1, "p95": p95}}}


def test_read_stats(tmp_path):
    stats = load_trend.read_stats(write_csv(tmp_path / "s.csv"))
    assert stats["GET /repo"] == {"requests": 199, "failures": 1, "median": 31.0, "p95": 53.0}
    assert stats["Aggregated"]["p95"] == 160.0
    assert list(stats) == ["GET /issues", "GET /repo", "Aggregated"]


@pytest.mark.parametrize("content, expected", [
    (None, []), ("not json", []), ('{"a": 1}', []), ('[{"label": "x"}]', [{"label": "x"}]),
])
def test_load_history(tmp_path, content, expected):
    path = tmp_path / "h.json"
    if content is not None:
        path.write_text(content)
    assert load_trend.load_history(path) == expected


def test_baseline_is_the_median_of_runs_that_measured_the_endpoint():
    history = [run(100), run(300), run(200), {"label": "empty"}]
    assert load_trend.baseline(history, "Aggregated") == 200
    assert load_trend.baseline(history, "GET /missing") is None
    assert load_trend.baseline([], "Aggregated") is None


@pytest.mark.parametrize("current, base, shown", [(150, 100, "+50 %"), (300, 100, "+200 %"), (90, 100, "-10 %"), (100, 100, "+0 %"),
                                                  (100, None, "-"), (100, 0, "-")])
def test_change(current, base, shown):
    assert load_trend.change(current, base) == shown


@pytest.mark.parametrize("values, line", [
    ([], ""), ([5, 5], "▁▁"), ([0, 7], "▁█"), ([0, 1, 2, 3, 4, 5, 6, 7], "▁▂▃▄▅▆▇█"), ([10, 20, 15], "▁█▅"),
])
def test_sparkline(values, line):
    assert load_trend.sparkline(values) == line


@pytest.mark.parametrize("current, base, size, limit, expected", [
    (150, 100, 3, 50, False),      # exactly at the limit is allowed
    (151, 100, 3, 50, True),
    (151, 100, 2, 50, False),      # not enough history yet
    (999, None, 5, 50, False),
    (121, 100, 3, 20, True),
])
def test_regressed(current, base, size, limit, expected):
    assert load_trend.regressed(current, base, size, limit) is expected


def test_report_lists_every_endpoint_with_the_total_last(tmp_path):
    stats = load_trend.read_stats(write_csv(tmp_path / "s.csv"))
    text, failed = load_trend.report(stats, [run(100), run(150), run(200)], "abc123", 50)
    assert text == "\n".join([
        "## Load trend: ✅ p95 160 ms, within 50 % of the recent median (150 ms)", "",
        "Run `abc123` compared with the median of the previous 3 run(s).", "",
        "| Endpoint | Requests | Failures | p95 | Recent median p95 | Change |",
        "|---|---:|---:|---:|---:|---:|",
        "| GET /issues | 375 | 0 | 170 ms | 150 ms | +13 % |",
        "| GET /repo | 199 | 1 | 53 ms | - | - |",
        "| **Aggregated** | 574 | 1 | 160 ms | 150 ms | +7 % |", "",
        "Overall p95, oldest to newest (4 runs): `▁▅█▅` 100 → 150 → 200 → 160 ms", ""])
    lines = text.splitlines()
    assert lines[0] == "## Load trend: ✅ p95 160 ms, within 50 % of the recent median (150 ms)"
    assert "Run `abc123` compared with the median of the previous 3 run(s)." in lines
    assert "| GET /issues | 375 | 0 | 170 ms | 150 ms | +13 % |" in lines
    assert "| GET /repo | 199 | 1 | 53 ms | - | - |" in lines
    assert lines[-3] == "| **Aggregated** | 574 | 1 | 160 ms | 150 ms | +7 % |"
    assert lines[-1] == "Overall p95, oldest to newest (4 runs): `▁▅█▅` 100 → 150 → 200 → 160 ms"
    assert failed is False


def test_report_verdicts(tmp_path):
    stats = load_trend.read_stats(write_csv(tmp_path / "s.csv", total_p95=400))
    text, failed = load_trend.report(stats, [run(100)], "x", 50)
    assert text.startswith("## Load trend: ⏳ collecting history (1 of 3 previous runs)") and not failed
    text, failed = load_trend.report(stats, [run(100)] * 3, "x", 50)
    assert text.startswith("## Load trend: ❌ p95 400 ms is more than 50 % above the recent median (100 ms)")
    assert failed


def test_main_appends_to_history_and_gates(tmp_path, capsys):
    csv_path, history = write_csv(tmp_path / "s.csv", total_p95=400), tmp_path / "out" / "h.json"
    assert load_trend.main([str(csv_path), "--history", str(history), "--label", "r1"]) == 0
    assert [r["label"] for r in json.loads(history.read_text())] == ["r1"]
    history.write_text(json.dumps([run(100)] * 3))
    assert load_trend.main([str(csv_path), "--history", str(history), "--label", "r2", "--keep", "2"]) == 1
    saved = json.loads(history.read_text())
    assert [r["label"] for r in saved] == ["old", "r2"]
    assert saved[-1]["stats"]["Aggregated"]["p95"] == 400
    assert "❌" in capsys.readouterr().out
    assert load_trend.main([str(csv_path), "--history", str(history), "--max-regression", "400"]) == 0


def test_main_defaults(tmp_path, capsys):
    csv_path, history = write_csv(tmp_path / "s.csv", total_p95=150), tmp_path / "h.json"
    history.write_text(json.dumps([run(100, f"r{i}") for i in range(30)]))
    assert load_trend.main([str(csv_path), "--history", str(history)]) == 0      # +50 %: allowed by default
    out = capsys.readouterr().out
    assert "Run `local` compared with the median of the previous 30 run(s)." in out
    assert out.endswith(f"(31 runs): `{'▁' * 30}█` 100 → 100 → 100 → 100 → 150 ms\n")   # last five values
    saved = json.loads(history.read_text())
    assert len(saved) == 30 and saved[0]["label"] == "r1" and saved[-1]["label"] == "local"
    assert history.read_text().startswith('[\n {\n  "label": "r1"')         # indent=1 keeps diffs readable

    write_csv(csv_path, total_p95=151)                                           # +51 %: over the default
    assert load_trend.main([str(csv_path), "--history", str(history)]) == 1
    capsys.readouterr()
    assert load_trend.main([str(csv_path), "--history", str(history), "--max-regression", "60.5"]) == 0
    assert "within 60 % of the recent median" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        load_trend.main([str(csv_path)])                                         # --history is required
    with pytest.raises(SystemExit):
        load_trend.main(["--help"])
    assert "Track load-test results across runs" in capsys.readouterr().out


def test_main_without_total_row(tmp_path, capsys):
    path = tmp_path / "s.csv"
    path.write_text(CSV_HEADER + "\n")
    history = tmp_path / "h.json"
    assert load_trend.main([str(path), "--history", str(history)]) == 0
    assert "nothing to compare" in capsys.readouterr().out
    assert not history.exists()
