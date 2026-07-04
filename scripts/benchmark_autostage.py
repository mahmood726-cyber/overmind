"""Auto-stage the model arms (A/B/C) when vendor capacity returns.

Designed to be invoked by the supervised drain daemon (which auto-resumes ~5h
after an out-of-credits cap) or a scheduler. It:
  1. reads the reliability cap-log — if seats are still capped, prints the
     expected reset time and exits 0 (nothing to do yet);
  2. otherwise runs `scripts/run_benchmark.py`, which preflights vendors and runs
     whatever is live (resuming completed tasks via checkpoint).

Idempotent + resumable: safe to call repeatedly. No vendor work is dispatched to a
degraded seat (run_benchmark preflights first).

Wire-up (documented, not auto-installed):
    # in the drain loop's post-recovery hook, or a schedule near the ~5h refill:
    python scripts/benchmark_autostage.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overmind.reliability.cap_log import CapLog, default_cap_log_path  # noqa: E402


def main() -> int:
    cap_path = default_cap_log_path(ROOT / "data")
    caps = CapLog(cap_path).active_caps()
    vendor_caps = {s: e for s, e in caps.items() if any(v in s.lower() for v in ("codex", "agy", "gemini"))}
    if vendor_caps:
        for seat, ev in vendor_caps.items():
            reset = f"{ev.reset_at:.0f}" if ev.reset_at else "unknown"
            print(f"  [staged] {seat} still capped (reset_at epoch={reset}): {ev.cap_message[:80]}")
        print("Vendor capacity not back yet — benchmark A/B/C remain STAGED. Re-invoke after reset.")
        return 0
    print("No active vendor caps — running the benchmark (preflight will gate per-vendor).")
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "run_benchmark.py")])


if __name__ == "__main__":
    raise SystemExit(main())
