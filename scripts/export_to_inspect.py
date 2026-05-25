"""Phase-3 N: Export Overmind nightly bundles to inspect_ai EvalLog JSON.

Walks data/nightly_reports/bundles/<latest-date>/ (or a specified --date),
converts every bundle into inspect_ai-compatible JSON, and writes to
data/nightly_reports/inspect_format/<date>/.

Strictly additive — original bundles unchanged. Run after a nightly to
make the verdicts viewable in `inspect view`.

Usage:
    python scripts/export_to_inspect.py                   # latest date
    python scripts/export_to_inspect.py --date 2026-05-17 # specific date
    python scripts/export_to_inspect.py --project Finrenone --date 2026-05-17
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Local import — works whether running from project root or scripts/
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from overmind.integrations.inspect_ai_adapter import bundle_file_to_inspect


BUNDLES_ROOT = SCRIPT_DIR.parent / "data" / "nightly_reports" / "bundles"
INSPECT_ROOT = SCRIPT_DIR.parent / "data" / "nightly_reports" / "inspect_format"


def latest_date() -> str | None:
    if not BUNDLES_ROOT.is_dir():
        return None
    dates = sorted(d.name for d in BUNDLES_ROOT.iterdir() if d.is_dir())
    return dates[-1] if dates else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="bundle date directory (default: latest)")
    ap.add_argument("--project", help="only export this project (substring match)")
    args = ap.parse_args(argv)

    date = args.date or latest_date()
    if not date:
        sys.stderr.write(f"No bundle dates found under {BUNDLES_ROOT}\n")
        return 1

    src = BUNDLES_ROOT / date
    if not src.is_dir():
        sys.stderr.write(f"Date dir does not exist: {src}\n")
        return 1
    dst = INSPECT_ROOT / date
    dst.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped = 0
    for bundle_path in sorted(src.glob("*.json")):
        if args.project and args.project.lower() not in bundle_path.stem.lower():
            continue
        try:
            eval_log = bundle_file_to_inspect(bundle_path)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"  [SKIP] {bundle_path.name}: {e!r}\n")
            skipped += 1
            continue
        out_path = dst / bundle_path.name
        out_path.write_text(json.dumps(eval_log, indent=2), encoding="utf-8")
        written += 1

    print(f"Wrote {written} inspect-format files to {dst}")
    if skipped:
        print(f"Skipped {skipped} bundles (see stderr)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
