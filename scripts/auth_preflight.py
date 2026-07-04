"""Run a truthful vendor auth preflight (reliability item 3).

Runs a REAL `codex exec` / `agy --print` smoke of every non-Claude seat — not the
lying `login status` — and reports each seat live / degraded. Exit 0 if at least
one non-Claude vendor is live; exit 1 if all are degraded (so a CI/dispatch step
can gate on it). See harness/AUTH_PREFLIGHT_RUNBOOK.md for the recovery recipe.

Usage:
    python scripts/auth_preflight.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from the repo root without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overmind.reliability.auth_preflight import (  # noqa: E402
    degraded_seats,
    live_vendors,
    preflight_all,
    summarize,
)


def main() -> int:
    probes = preflight_all()
    for p in probes:
        mark = "LIVE " if p.alive else "DEGRADED"
        print(f"  [{mark}] {p.vendor}:{p.seat} - {p.detail}")
    print(summarize(probes))
    live = live_vendors(probes)
    if not live:
        print(
            "\nAll non-Claude vendors DEGRADED. Re-auth per harness/AUTH_PREFLIGHT_RUNBOOK.md "
            "(interactive `codex login` on pc1; agy driver check).",
            file=sys.stderr,
        )
        return 1
    if degraded_seats(probes):
        print(f"\nSome seats degraded; live vendors: {live}. Dispatch only to live seats.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
