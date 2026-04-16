"""Generate an HTML morning insights dashboard from the latest nightly report.

Called at the end of each nightly run. Writes to C:/overmind/dashboard/index.html
and optionally opens it in the default browser.

Usage:
    python scripts/generate_dashboard.py              # Generate from latest report
    python scripts/generate_dashboard.py --open       # Generate and open in browser
"""
from __future__ import annotations

import json
import os
import sys
import webbrowser
from datetime import datetime, UTC
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REPORT_DIR = DATA_DIR / "nightly_reports"
DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard"


def load_latest_report() -> dict | None:
    path = REPORT_DIR / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_report_history(days: int = 7) -> list[dict]:
    reports = []
    for f in sorted(REPORT_DIR.glob("nightly_*.json"), reverse=True)[:days]:
        if f.name == "latest.json":
            continue
        try:
            reports.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return reports


def load_cusum_warnings() -> list[str]:
    warnings = []
    cusum_dir = DATA_DIR / "cusum_state"
    if not cusum_dir.exists():
        return warnings
    for f in cusum_dir.glob("*_cusum.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for key, state in data.items():
                if state.get("warning"):
                    warnings.append(f"{f.stem.replace('_cusum', '')}: {key} (CUSUM={state['cusum_pos']:.1f})")
        except (json.JSONDecodeError, OSError):
            pass
    return warnings


def load_stability_alerts() -> list[dict]:
    path = DATA_DIR / "stability_state.json"
    if not path.exists():
        return []
    try:
        states = json.loads(path.read_text(encoding="utf-8"))
        alerts = []
        for pid, state in states.items():
            if state.get("streak", 0) == 0 and state.get("max_streak", 0) >= 5:
                recent = state.get("history", [])[-1:]
                if recent and recent[0] not in ("CERTIFIED", "PASS"):
                    alerts.append({
                        "project": pid[:25],
                        "max_streak": state["max_streak"],
                        "last_verdict": state["last_verdict"],
                    })
        return alerts
    except (json.JSONDecodeError, OSError):
        return []


def load_skills() -> list[dict]:
    path = Path("C:/overmind/wiki/SKILLS.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("skills", [])
    except (json.JSONDecodeError, OSError):
        return []


def generate_html(report: dict, history: list[dict], cusum_warnings: list[str], skills: list[dict], stability_alerts: list[dict] | None = None) -> str:
    timestamp = report.get("timestamp", "unknown")
    total = report.get("total_projects", 0)
    certified = report.get("certified", 0)
    rejected = report.get("rejected", 0)
    failed = report.get("failed", 0)
    single_pass = report.get("single_pass", 0)
    unverified = report.get("unverified", 0)
    total_time = report.get("total_time_seconds", 0)

    projects = report.get("projects", [])
    certified_projects = [p for p in projects if p["verdict"] == "CERTIFIED"]
    reject_projects = [p for p in projects if p["verdict"] == "REJECT"]
    fail_projects = [p for p in projects if p["verdict"] == "FAIL"]
    pass_projects = [p for p in projects if p["verdict"] == "PASS"]
    unverified_projects = [p for p in projects if p["verdict"] == "UNVERIFIED"]

    # Trend data
    trend_dates = []
    trend_certified = []
    trend_pass = []
    trend_reject = []
    trend_fail = []
    trend_unverified = []
    for h in reversed(history[:7]):
        ts = h.get("timestamp", "")[:10]
        trend_dates.append(f'"{ts}"')
        trend_certified.append(str(h.get("certified", 0)))
        trend_pass.append(str(h.get("single_pass", 0)))
        trend_reject.append(str(h.get("rejected", 0)))
        trend_fail.append(str(h.get("failed", 0)))
        trend_unverified.append(str(h.get("unverified", 0)))

    # Dream stats
    dream = report.get("dream", {})

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Overmind Morning Insights</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0e17; color: #e0e6ed; padding: 24px; }}
.header {{ text-align: center; margin-bottom: 32px; }}
.header h1 {{ font-size: 28px; color: #fff; letter-spacing: 2px; }}
.header .date {{ color: #8892a4; font-size: 14px; margin-top: 4px; }}
.header .runtime {{ color: #5a6577; font-size: 12px; }}
.grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 32px; }}
@media (max-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
.card {{ background: #131926; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #1e2a3a; }}
.card .number {{ font-size: 42px; font-weight: 700; line-height: 1; }}
.card .label {{ font-size: 12px; color: #8892a4; text-transform: uppercase; letter-spacing: 1px; margin-top: 6px; }}
.certified .number {{ color: #00e676; }}
.pass .number {{ color: #448aff; }}
.unverified .number {{ color: #b388ff; }}
.reject .number {{ color: #ff9100; }}
.fail .number {{ color: #ff5252; }}
.section {{ background: #131926; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #1e2a3a; }}
.section h2 {{ font-size: 16px; color: #fff; margin-bottom: 16px; border-bottom: 1px solid #1e2a3a; padding-bottom: 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; color: #8892a4; font-weight: 500; padding: 8px; border-bottom: 1px solid #1e2a3a; }}
td {{ padding: 8px; border-bottom: 1px solid #0d1117; }}
.verdict-certified {{ color: #00e676; font-weight: 600; }}
.verdict-pass {{ color: #448aff; }}
.verdict-unverified {{ color: #b388ff; }}
.verdict-reject {{ color: #ff9100; }}
.verdict-fail {{ color: #ff5252; }}
.warn {{ background: #2a1800; border: 1px solid #ff9100; border-radius: 8px; padding: 12px; margin-bottom: 8px; font-size: 13px; }}
.insight {{ background: #0d1a0d; border: 1px solid #00e676; border-radius: 8px; padding: 12px; margin-bottom: 8px; font-size: 13px; }}
.trend {{ display: flex; gap: 4px; align-items: flex-end; height: 60px; }}
.trend-bar {{ flex: 1; border-radius: 3px 3px 0 0; min-width: 8px; }}
.footer {{ text-align: center; color: #5a6577; font-size: 11px; margin-top: 32px; }}
</style>
</head>
<body>
<div class="header">
    <h1>OVERMIND</h1>
    <div class="date">Morning Insights — {timestamp[:10]}</div>
    <div class="runtime">{total} projects verified in {total_time:.0f}s</div>
</div>

<div class="grid">
    <div class="card certified"><div class="number">{certified}</div><div class="label">Certified</div></div>
    <div class="card pass"><div class="number">{single_pass}</div><div class="label">Pass</div></div>
    <div class="card unverified" title="Tier-3 projects with missing numerical baseline — NOT a release pass"><div class="number">{unverified}</div><div class="label">Unverified</div></div>
    <div class="card reject"><div class="number">{rejected}</div><div class="label">Reject</div></div>
    <div class="card fail"><div class="number">{failed}</div><div class="label">Fail</div></div>
</div>

{"".join(f'<div class="warn">CUSUM drift warning: {w}</div>' for w in cusum_warnings)}
{"".join(f\'<div class="warn">STABILITY BREAK: {a["project"]} was stable for {a["max_streak"]} runs, now {a["last_verdict"]}</div>\' for a in (stability_alerts or []))}


{f'<div class="section"><h2>Certified ({len(certified_projects)})</h2><table><tr><th>Project</th><th>Risk</th><th>Math</th><th>Witnesses</th><th>Time</th></tr>' + "".join(f'<tr><td>{p["name"]}</td><td>{p["risk"]}</td><td>{p["math_score"]}</td><td>{p["witness_count"]}</td><td>{p["elapsed"]:.1f}s</td></tr>' for p in certified_projects) + '</table></div>' if certified_projects else ''}

{f'<div class="section"><h2>Needs Investigation ({len(reject_projects)})</h2><table><tr><th>Project</th><th>Risk</th><th>Reason</th><th>Time</th></tr>' + "".join(f'<tr><td>{p["name"]}</td><td>{p["risk"]}</td><td style="font-size:11px">{p["arbitration_reason"][:80]}</td><td>{p["elapsed"]:.1f}s</td></tr>' for p in reject_projects) + '</table></div>' if reject_projects else ''}

{f'<div class="section"><h2>Failed ({len(fail_projects)})</h2><table><tr><th>Project</th><th>Risk</th><th>Reason</th><th>Time</th></tr>' + "".join(f'<tr><td>{p["name"]}</td><td>{p["risk"]}</td><td style="font-size:11px">{p["arbitration_reason"][:80]}</td><td>{p["elapsed"]:.1f}s</td></tr>' for p in fail_projects) + '</table></div>' if fail_projects else ''}

{f'<div class="section"><h2>Unverified — Missing Numerical Baseline ({len(unverified_projects)})</h2><p style="font-size:12px;color:#8892a4;margin-bottom:12px">Tier-3 projects where test + smoke PASSED but the numerical witness SKIPPED because the baseline file is missing. <strong>NOT a release pass</strong> — restore the baseline before promoting.</p><table><tr><th>Project</th><th>Risk</th><th>Math</th><th>Reason</th><th>Time</th></tr>' + "".join(f'<tr><td>{p["name"]}</td><td>{p["risk"]}</td><td>{p["math_score"]}</td><td style="font-size:11px">{p["arbitration_reason"][:80]}</td><td>{p["elapsed"]:.1f}s</td></tr>' for p in unverified_projects) + '</table></div>' if unverified_projects else ''}

{f'<div class="section"><h2>Passing ({len(pass_projects)})</h2><table><tr><th>Project</th><th>Risk</th><th>Math</th><th>Time</th></tr>' + "".join(f'<tr><td>{p["name"]}</td><td>{p["risk"]}</td><td>{p["math_score"]}</td><td>{p["elapsed"]:.1f}s</td></tr>' for p in pass_projects) + '</table></div>' if pass_projects else ''}

<div class="section">
    <h2>System Health</h2>
    <table>
        <tr><td>Dream cycle</td><td>{dream.get("merges", 0)} merges, {dream.get("archives", 0)} archives, {dream.get("memories_before", "?")}&rarr;{dream.get("memories_after", "?")} memories</td></tr>
        <tr><td>Skills library</td><td>{len(skills)} skills</td></tr>
        <tr><td>CUSUM warnings</td><td>{len(cusum_warnings)} projects drifting</td></tr>
    </table>
</div>

<div class="footer">
    Generated by Overmind v3.2 &middot; {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}
</div>
</body>
</html>"""


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="Open in browser after generating")
    args = parser.parse_args()

    report = load_latest_report()
    if not report:
        print("No latest.json found")
        return

    history = load_report_history(7)
    cusum_warnings = load_cusum_warnings()
    skills = load_skills()
    stability_alerts = load_stability_alerts()

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    html = generate_html(report, history, cusum_warnings, skills, stability_alerts)
    out_path = DASHBOARD_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard written to {out_path}")

    if args.open:
        webbrowser.open(str(out_path))
        print("Opened in browser")


if __name__ == "__main__":
    main()
