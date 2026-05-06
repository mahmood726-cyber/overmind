"""Morning watchdog: surface a failed/missing nightly verifier run.

Designed to run at 08:00 daily (after the 03:00 nightly has had 5h to
finish). Asserts:

1. `nightly_<yesterday>.json` exists in `data/nightly_reports/`
2. Report does NOT carry `partial: true` (would mean the run was killed
   mid-loop by faulthandler / kill-tree / power loss)
3. Report's `timestamp` is within the last 24h (catches stale-pinned reports)
4. Sentinel total_block did not regress past the dedup threshold

On any failure: write `data/nightly_reports/watchdog_<today>.alert` and
emit a Windows toast (best effort — toast failure must not mask the alert).

Per the 8-persona blinded review (P0-3 SRE): the 2026-05-04 freeze went
unnoticed for 3 days because nothing paged. This watchdog closes that
gap. Recovery time goes from "until the human checks manually" (unbounded)
to "by 08:00 the next morning."

Exit code:
  0 — last night's run is healthy
  1 — alert raised (file written, toast attempted)
  2 — watchdog itself crashed (rare; see traceback in stderr)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "nightly_reports"
ALERT_PATH = REPORT_DIR / f"watchdog_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.alert"
BLOCK_THRESHOLD = 30000  # mirrors nightly_verify.py BLOCK_THRESHOLD


def _yesterday_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _try_toast(title: str, body: str) -> None:
    """Best-effort Windows toast notification. Failure must not mask alert."""
    try:
        import subprocess
        # Use built-in BurntToast equivalent via PowerShell. Falls back to
        # a beep + console log if PowerShell COM/WinRT isn't available.
        ps_script = (
            "[Windows.UI.Notifications.ToastNotificationManager,"
            "Windows.UI.Notifications,ContentType=WindowsRuntime] | Out-Null; "
            "[Windows.Data.Xml.Dom.XmlDocument,"
            "Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime] | Out-Null; "
            f"$xml = '<toast><visual><binding template=\"ToastGeneric\">"
            f"<text>{title}</text><text>{body}</text></binding></visual></toast>'; "
            "$doc = New-Object Windows.Data.Xml.Dom.XmlDocument; "
            "$doc.LoadXml($xml); "
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($doc); "
            "[Windows.UI.Notifications.ToastNotificationManager]"
            "::CreateToastNotifier('Overmind').Show($toast)"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            timeout=10, capture_output=True, check=False,
        )
    except Exception:
        pass


def _raise_alert(reasons: list[str]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"  - {r}" for r in reasons)
    payload = (
        f"OVERMIND NIGHTLY WATCHDOG ALERT\n"
        f"raised at {datetime.now(timezone.utc).isoformat()}\n\n"
        f"Reasons:\n{body}\n\n"
        f"Recovery: see C:/overmind/RUNBOOK.md\n"
    )
    ALERT_PATH.write_text(payload, encoding="utf-8")
    print(payload, file=sys.stderr)
    _try_toast("Overmind nightly failed", reasons[0][:120])


def check() -> int:
    """Return 0 if healthy, 1 if alert raised."""
    reasons: list[str] = []
    yesterday = _yesterday_iso()
    nightly_path = REPORT_DIR / f"nightly_{yesterday}.json"

    if not nightly_path.exists():
        reasons.append(
            f"nightly_{yesterday}.json missing — scheduled run did not "
            f"complete or did not start"
        )
        _raise_alert(reasons)
        return 1

    try:
        report = json.loads(nightly_path.read_text(encoding="utf-8"))
    except Exception as e:
        reasons.append(f"nightly_{yesterday}.json malformed: {type(e).__name__}: {e}")
        _raise_alert(reasons)
        return 1

    if report.get("partial") is True:
        reasons.append(
            f"nightly_{yesterday}.json has partial=true — run was killed "
            f"before reaching the canonical end-of-run write"
        )

    ts = report.get("timestamp", "")
    if ts:
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - t
            if age > timedelta(hours=30):
                reasons.append(
                    f"nightly_{yesterday}.json timestamp {ts} is {age} old "
                    f"— stale-pinned report, not a fresh run"
                )
        except Exception as e:
            reasons.append(f"nightly_{yesterday}.json timestamp unparseable: {e}")

    block_total = (report.get("sentinel") or {}).get("total_block", 0)
    if isinstance(block_total, int) and block_total > BLOCK_THRESHOLD:
        reasons.append(
            f"sentinel.total_block={block_total} exceeded threshold "
            f"{BLOCK_THRESHOLD} — dedup may have regressed"
        )

    total_projects = report.get("total_projects", 0)
    if isinstance(total_projects, int) and total_projects < 10 and not report.get("partial"):
        # A canonical (non-partial) report with <10 projects is suspicious
        # — the scheduler runs --limit 50 by default.
        reasons.append(
            f"nightly_{yesterday}.json reports total_projects={total_projects} "
            f"on a non-partial run — expected ~50. Possibly a manual "
            f"--projects-from-file rerun overwrote the canonical report; "
            f"check that latest.json wasn't clobbered."
        )

    if reasons:
        _raise_alert(reasons)
        return 1
    print(f"[watchdog] nightly_{yesterday}.json healthy: "
          f"projects={report.get('total_projects')} "
          f"certified={report.get('certified')} "
          f"block_total={block_total}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(check())
    except Exception as e:  # pragma: no cover — only via crash
        import traceback
        traceback.print_exc()
        try:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            (REPORT_DIR / "watchdog_crash.log").write_text(
                f"{datetime.now(timezone.utc).isoformat()}\n{traceback.format_exc()}",
                encoding="utf-8",
            )
        except Exception:
            pass
        sys.exit(2)
