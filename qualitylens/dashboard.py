"""Static HTML dashboard of the test history: failures per run, suite time, flaky, failing and slow tests.

    qualitylens dashboard --history test-history/history.json --out site/trends.html

One self-contained file (inline CSS and SVG, no scripts or network), so it can be uploaded as a CI
artifact, published next to the Allure report, or opened from disk. Hovering a bar or point shows
its numbers; light and dark themes follow the viewer's system setting.
"""
from __future__ import annotations

from html import escape

from qualitylens import history

W, H, PAD_L, PAD_B, PAD_T = 720, 220, 44, 28, 12

CSS = """
:root { color-scheme: light; --surface: #fcfcfb; --card: #ffffff; --text: #0b0b0b; --muted: #52514e;
  --line: #e4e3df; --series: #2a78d6; --good: #0ca30c; --warning: #fab219; --critical: #d03b3b; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark;
  --surface: #1a1a19; --card: #232322; --text: #f0efec; --muted: #c3c2b7; --line: #3a3a37; --series: #3987e5; } }
:root[data-theme="dark"] { color-scheme: dark; --surface: #1a1a19; --card: #232322; --text: #f0efec;
  --muted: #c3c2b7; --line: #3a3a37; --series: #3987e5; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 16px; margin: 32px 0 8px; }
.sub { color: var(--muted); margin: 0 0 20px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; }
.tile b { display: block; font-size: 26px; font-variant-numeric: tabular-nums; }
.tile span { color: var(--muted); font-size: 13px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px; overflow-x: auto; }
svg { display: block; width: 100%; height: auto; min-width: 480px; }
svg text { fill: var(--muted); font-size: 11px; }
.grid { stroke: var(--line); stroke-width: 1; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; } td.n { text-align: right; font-variant-numeric: tabular-nums; }
code { font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; word-break: break-all; }
.empty { color: var(--muted); }
rect.hit:hover { fill: var(--line); opacity: .5; } circle:hover { opacity: .75; }
"""


def _x(i: int, n: int) -> float:
    return PAD_L + (W - PAD_L - 8) * (i + 0.5) / max(n, 1)


def failure_bars(runs: list[dict]) -> str:
    """Unexpected failures per run, as a count: at a 99 % pass rate a share-of-100 % bar hides them."""
    n = len(runs)
    fails = [sum(o == "failed" for o, _ in run["results"].values()) for run in runs]
    top = max([*fails, 1])
    plot_h = H - PAD_B - PAD_T
    slot = (W - PAD_L - 8) / max(n, 1)
    bar_w = max(2.0, min(28.0, slot - 4))
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Unexpected failures per run">']
    for value in sorted({0, top // 2, top}):
        y = PAD_T + plot_h * (1 - value / top)
        parts.append(f'<line class="grid" x1="{PAD_L}" x2="{W - 8}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
    for i, (run, count) in enumerate(zip(runs, fails, strict=True)):
        x = _x(i, n)
        tip = f"<title>{escape(run['label'])} ({escape(run.get('time', ''))}): {count} failed, " \
              f"{history.pass_rate(run):.1f}% as expected</title>"
        h = plot_h * count / top
        if h > 0:
            parts.append(f'<rect x="{x - bar_w / 2:.1f}" y="{PAD_T + plot_h - h:.1f}" width="{bar_w:.1f}" '
                         f'height="{h:.1f}" rx="2" fill="var(--critical)"/>')
        # the hover target is the whole column, so runs with no failures still show their numbers
        parts.append(f'<rect class="hit" x="{x - slot / 2:.1f}" y="{PAD_T}" width="{slot:.1f}" height="{plot_h}" '
                     f'fill="transparent">{tip}</rect>')
    parts += _run_labels(runs), "</svg>"
    return "".join(parts)


def duration_line(runs: list[dict]) -> str:
    """Total test time per run (sum of test durations, so parallel runs are comparable)."""
    totals = [sum(secs for _, secs in run["results"].values()) for run in runs]
    n, top = len(totals), max(totals or [0]) or 1
    plot_h = H - PAD_B - PAD_T
    pts = [(_x(i, n), PAD_T + plot_h * (1 - t / top)) for i, t in enumerate(totals)]
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Total test time per run">']
    for frac in (0, 0.5, 1):
        y = PAD_T + plot_h * (1 - frac)
        parts.append(f'<line class="grid" x1="{PAD_L}" x2="{W - 8}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{top * frac / 60:.1f}m</text>')
    if len(pts) > 1:
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        parts.append(f'<path d="{path}" fill="none" stroke="var(--series)" stroke-width="2"/>')
    for (x, y), run, t in zip(pts, runs, totals, strict=True):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--series)" stroke="var(--card)" '
                     f'stroke-width="2"><title>{escape(run["label"])}: {t / 60:.1f} min</title></circle>')
    parts += _run_labels(runs), "</svg>"
    return "".join(parts)


def _run_labels(runs: list[dict]) -> str:
    n = len(runs)
    if not n:
        return ""
    step = max(1, n // 8)
    shown = [i for i in range(n) if i % step == 0]
    if shown[-1] != n - 1:  # always label the latest run, dropping a neighbour that would overlap it
        shown[-1 if n - 1 - shown[-1] < step else len(shown):] = [n - 1]
    # the latest label is right-aligned so it is not cut off at the edge
    return "".join(f'<text x="{_x(i, n):.1f}" y="{H - 8}" text-anchor="middle">{escape(runs[i]["label"][:10])}</text>'
                   if i < n - 1 or n == 1 else
                   f'<text x="{W - 8}" y="{H - 8}" text-anchor="end">{escape(runs[i]["label"][:10])}</text>'
                   for i in shown)


def _table(rows: list[tuple[str, ...]], headers: tuple[str, ...], numeric: set[int]) -> str:
    if not rows:
        return '<p class="empty">None.</p>'
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f'<td class="n">{c}</td>' if i in numeric else f"<td>{c}</td>"
                                    for i, c in enumerate(row)) + "</tr>" for row in rows)
    return f'<div class="card"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render(runs: list[dict], quarantined: set[str], title: str = "QualityLens test trends",
           min_runs: int = history.DEFAULT_MIN_RUNS, threshold: float = history.DEFAULT_THRESHOLD) -> str:
    if not runs:
        body = '<p class="empty">No runs recorded yet. Record one with: qualitylens history add results/*.xml</p>'
        return _page(title, body)
    all_stats = history.stats(runs)
    latest = runs[-1]
    flaky = history.flaky_tests(runs, min_runs, threshold)
    failing = [s for s in all_stats.values() if history.classify(s, min_runs, threshold) == "failing"]
    slowest = sorted(all_stats.values(), key=lambda s: -s.mean_seconds)[:10]
    executed = sum(o in history.EXECUTED for o, _ in latest["results"].values())
    tiles = [(f"{history.pass_rate(latest):.1f}%", "as expected, latest run"), (str(executed), "tests executed"),
             (str(len(flaky)), "flaky tests"), (str(len(failing)), "failing now"), (str(len(runs)), "runs in history")]
    sections = [
        f'<p class="sub">{len(runs)} runs, {escape(runs[0].get("time", "")[:10])} to '
        f'{escape(latest.get("time", "")[:10])}. Latest: <code>{escape(latest["label"])}</code></p>',
        '<div class="tiles">' + "".join(f"<div class=tile><b>{v}</b><span>{k}</span></div>" for v, k in tiles)
        + "</div>",
        "<h2>Unexpected failures per run</h2>", f'<div class="card">{failure_bars(runs)}</div>',
        "<h2>Total test time per run</h2>", f'<div class="card">{duration_line(runs)}</div>',
        f"<h2>Flaky tests ({len(flaky)})</h2>",
        _table([(f"<code>{escape(s.test_id)}</code>", f"{s.flip_rate:.0%}", f"{s.failures}/{s.runs}",
                 f"<code>{s.timeline()}</code>", "yes" if s.test_id in quarantined else "<b>no</b>") for s in flaky],
               ("Test", "Flip rate", "Failures", "Timeline", "Quarantined"), {1, 2}),
        f"<h2>Failing in the latest run ({len(failing)})</h2>",
        _table([(f"<code>{escape(s.test_id)}</code>", f"{s.failures}/{s.runs}", f"<code>{s.timeline()}</code>")
                for s in failing], ("Test", "Failures", "Timeline"), {1}),
        "<h2>Slowest tests (mean)</h2>",
        _table([(f"<code>{escape(s.test_id)}</code>", f"{s.mean_seconds:.1f} s", f"{s.last_seconds:.1f} s")
                for s in slowest], ("Test", "Mean", "Latest"), {1, 2}),
        '<p class="sub" style="margin-top:24px">Timeline: ✓ passed, ✗ failed, ◌ known bug (strict xfail), '
        "· skipped; oldest on the left.</p>",
    ]
    return _page(title, "".join(sections))


def _page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)}</title>'
            f"<style>{CSS}</style></head><body><main><h1>{escape(title)}</h1>{body}</main></body></html>\n")
