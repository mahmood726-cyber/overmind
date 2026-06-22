"""Deterministic infra-invariant checker (audit P1-4).

A small, local-first, dependency-light guardrail that fails loudly on the exact
operational edge-conditions the 2026-06-20 infrastructure audit surfaced. It is
meant to run daily and (optionally) pre-push, the same way Sentinel + Overmind
encode past incidents as standing checks.

Each invariant is a pure function returning an ``InvariantResult`` so the suite
is fully testable without touching the real filesystem. The CLI
(``python -m overmind.infra_invariants``) runs every invariant against the live
machine and exits non-zero if any returns FAIL.

Design rules honoured here:
  - No hardcoded single-drive assumptions: roots are discovered from env / the
    user's home / candidate drives, and every check is **fail-soft** on a
    missing optional input (a missing .codex config is not a FAIL — an
    *enabled force-push* is).
  - Never print secret values: the key/OAuth checks read only expiry metadata
    and existence, never the secret material itself.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable


class Status(str, Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"  # optional input absent — neither pass nor fail


@dataclass(slots=True)
class InvariantResult:
    name: str
    status: Status
    detail: str
    evidence: list[str] = field(default_factory=list)


# ── helpers ─────────────────────────────────────────────────────────


def _candidate_homes() -> list[Path]:
    """Codex/agent home dirs to inspect, override via OVERMIND_AGENT_HOMES."""
    override = os.environ.get("OVERMIND_AGENT_HOMES")
    if override:
        return [Path(p) for p in override.split(os.pathsep) if p.strip()]
    home = Path.home()
    return [home / ".codex", home / ".codex-noreen"]


def _file_age_days(path: Path, *, now: float | None = None) -> float:
    now = now if now is not None else time.time()
    return (now - path.stat().st_mtime) / 86400.0


# ── invariant: force-push must be disabled ──────────────────────────

# Matches `git-always-force-push = true` (codex config.toml) tolerant of spacing
# and quoting. Only `true` is a violation; `false` is the desired state.
_FORCE_PUSH_TRUE = re.compile(
    r"^\s*git[-_]always[-_]force[-_]push\s*=\s*[\"']?true[\"']?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def check_force_push_disabled(homes: Iterable[Path] | None = None) -> InvariantResult:
    """FAIL if any agent config enables always-force-push.

    This is the catastrophic-class invariant from the audit (P0-1): a headless
    agent with force-push on could rewrite remote history. The desired state is
    the setting absent or explicitly ``false``.
    """
    homes = list(homes) if homes is not None else _candidate_homes()
    offenders: list[str] = []
    inspected = 0
    for home in homes:
        cfg = home / "config.toml"
        if not cfg.is_file():
            continue
        inspected += 1
        try:
            text = cfg.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _FORCE_PUSH_TRUE.finditer(text):
            lineno = text[: match.start()].count("\n") + 1
            offenders.append(f"{cfg}:{lineno} enables git-always-force-push")
    if offenders:
        return InvariantResult(
            "force_push_disabled", Status.FAIL,
            "force-push is ENABLED in an agent config — flip to false immediately",
            offenders,
        )
    if inspected == 0:
        return InvariantResult(
            "force_push_disabled", Status.SKIP,
            "no agent config.toml found to inspect",
        )
    return InvariantResult(
        "force_push_disabled", Status.OK,
        f"force-push disabled across {inspected} agent config(s)",
    )


# ── invariant: finding logs bounded + fresh ─────────────────────────


def check_log_health(
    repos: Iterable[Path] | None = None,
    *,
    max_bytes: int = 2 * 1024 * 1024,
    stale_days: float = 21.0,
    now: float | None = None,
) -> InvariantResult:
    """WARN on oversized or stale append-only finding logs.

    The audit found a 3.2 MB, 25-day-stale STUCK_FAILURES.md. Rotation (P1-5)
    fixes growth going forward; this check is the standing alarm.
    """
    repos = list(repos) if repos is not None else _default_repos()
    log_names = ("STUCK_FAILURES.md", "STUCK_FAILURES.jsonl",
                 "sentinel-findings.md", "sentinel-findings.jsonl")
    problems: list[str] = []
    inspected = 0
    for repo in repos:
        for name in log_names:
            p = repo / name
            if not p.is_file():
                continue
            inspected += 1
            try:
                size = p.stat().st_size
                age = _file_age_days(p, now=now)
            except OSError:
                continue
            if size > max_bytes:
                problems.append(f"{p} is {size // 1024} KiB (> {max_bytes // 1024} KiB cap)")
            if age > stale_days:
                problems.append(f"{p} last written {age:.0f}d ago (> {stale_days:.0f}d SLA)")
    if problems:
        return InvariantResult("log_health", Status.WARN,
                               "finding logs breach size/freshness SLA", problems)
    if inspected == 0:
        return InvariantResult("log_health", Status.SKIP, "no finding logs found")
    return InvariantResult("log_health", Status.OK,
                           f"{inspected} finding log(s) within size + freshness SLA")


# ── invariant: doc freshness SLA ────────────────────────────────────


def check_doc_freshness(
    doc_path: Path | None = None,
    *,
    stale_days: float = 14.0,
    now: float | None = None,
) -> InvariantResult:
    """WARN if LIVE_CONTEXT.md is older than its own freshness SLA."""
    if doc_path is None:
        doc_path = Path.home() / ".claude" / "LIVE_CONTEXT.md"
    if not doc_path.is_file():
        return InvariantResult("doc_freshness", Status.SKIP,
                               f"{doc_path} not present")
    age = _file_age_days(doc_path, now=now)
    if age > stale_days:
        return InvariantResult("doc_freshness", Status.WARN,
                               f"{doc_path.name} is {age:.0f}d old (> {stale_days:.0f}d SLA)",
                               [str(doc_path)])
    return InvariantResult("doc_freshness", Status.OK,
                           f"{doc_path.name} fresh ({age:.0f}d old)")


# ── invariant: no expired agent OAuth token ─────────────────────────


def check_oauth_freshness(
    homes: Iterable[Path] | None = None,
    *,
    warn_within_days: float = 3.0,
    now: float | None = None,
) -> InvariantResult:
    """WARN/FAIL on expired or near-expiry Codex OAuth tokens.

    Reads only the ``expires``/``expires_at`` metadata from ``auth.json`` — the
    token material itself is never read or printed. The audit found the mahmood
    seat's refresh token already revoked while docs claimed a future expiry, so
    this turns the round-robin's availability into a checked invariant.
    """
    homes = list(homes) if homes is not None else _candidate_homes()
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc) if now is not None else datetime.now(timezone.utc)
    expired: list[str] = []
    soon: list[str] = []
    inspected = 0
    for home in homes:
        auth = home / "auth.json"
        if not auth.is_file():
            continue
        inspected += 1
        try:
            data = json.loads(auth.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        exp = _extract_expiry(data)
        if exp is None:
            continue
        days_left = (exp - now_dt).total_seconds() / 86400.0
        label = f"{home.name} token"
        if days_left < 0:
            expired.append(f"{label} expired {abs(days_left):.0f}d ago")
        elif days_left < warn_within_days:
            soon.append(f"{label} expires in {days_left:.1f}d")
    if expired:
        return InvariantResult("oauth_freshness", Status.FAIL,
                               "an agent OAuth token is expired", expired + soon)
    if soon:
        return InvariantResult("oauth_freshness", Status.WARN,
                               "an agent OAuth token expires soon", soon)
    if inspected == 0:
        return InvariantResult("oauth_freshness", Status.SKIP,
                               "no agent auth.json found")
    return InvariantResult("oauth_freshness", Status.OK,
                           f"{inspected} agent token(s) valid")


def _extract_expiry(data: dict) -> datetime | None:
    """Best-effort pull of an expiry timestamp from a Codex auth.json blob."""
    candidates = [data]
    if isinstance(data.get("tokens"), dict):
        candidates.append(data["tokens"])
    for blob in candidates:
        for key in ("expires_at", "expires", "expiry", "expiration"):
            val = blob.get(key)
            if val is None:
                continue
            try:
                if isinstance(val, (int, float)):
                    # epoch seconds (or ms if absurdly large)
                    secs = val / 1000.0 if val > 1e12 else float(val)
                    return datetime.fromtimestamp(secs, tz=timezone.utc)
                if isinstance(val, str):
                    s = val.strip().replace("Z", "+00:00")
                    dt = datetime.fromisoformat(s)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (ValueError, OverflowError, OSError):
                continue
    return None


# ── invariant: judge engine config is recognised ────────────────────


def check_judge_engine_config(env: dict | None = None) -> InvariantResult:
    """FAIL if OVERMIND_JUDGE_ENGINE is set to an unknown backend.

    A typo silently falling back is fine for availability but bad for intent;
    this catches a misconfigured engine before a nightly run quietly uses the
    wrong (or no) judge.
    """
    env = env if env is not None else os.environ
    raw = env.get("OVERMIND_JUDGE_ENGINE")
    if not raw:
        return InvariantResult("judge_engine_config", Status.OK,
                               "OVERMIND_JUDGE_ENGINE unset - using default")
    # Imported lazily so the checker has no hard dependency on the judge module.
    try:
        from overmind.verification.judge_factory import KNOWN_ENGINES
    except Exception:  # noqa: BLE001
        return InvariantResult("judge_engine_config", Status.SKIP,
                               "judge_factory not importable")
    tokens = [t.strip().lower() for t in re.split(r"[,;]", raw) if t.strip()]
    unknown = [t for t in tokens if t not in KNOWN_ENGINES]
    if unknown:
        return InvariantResult("judge_engine_config", Status.FAIL,
                               f"unknown judge engine(s): {', '.join(unknown)}",
                               [f"known: {', '.join(sorted(KNOWN_ENGINES))}"])
    return InvariantResult("judge_engine_config", Status.OK,
                           f"judge engine(s) recognised: {', '.join(tokens)}")


# ── registry + runner ───────────────────────────────────────────────


def _default_repos() -> list[Path]:
    override = os.environ.get("OVERMIND_INFRA_REPOS")
    if override:
        return [Path(p) for p in override.split(os.pathsep) if p.strip()]
    repos: list[Path] = []
    for drive in ("F:", "C:"):
        for name in ("Sentinel", "overmind"):
            p = Path(f"{drive}\\{name}") if os.name == "nt" else Path(drive) / name
            if p.is_dir():
                repos.append(p)
    return repos


INVARIANTS: tuple[Callable[[], InvariantResult], ...] = (
    check_force_push_disabled,
    check_log_health,
    check_doc_freshness,
    check_oauth_freshness,
    check_judge_engine_config,
)


def run_all() -> list[InvariantResult]:
    return [fn() for fn in INVARIANTS]


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="overmind.infra_invariants",
        description="Deterministic infra-invariant checker (audit P1-4).",
    )
    parser.add_argument("--json", action="store_true", help="emit results as JSON")
    parser.add_argument(
        "--strict", action="store_true",
        help="treat WARN as failure (exit non-zero on WARN too)",
    )
    args = parser.parse_args(argv)

    results = run_all()
    if args.json:
        print(json.dumps([
            {"name": r.name, "status": r.status.value, "detail": r.detail, "evidence": r.evidence}
            for r in results
        ], indent=2))
    else:
        for r in results:
            print(f"[{r.status.value:4}] {r.name}: {r.detail}")
            for ev in r.evidence:
                print(f"         - {ev}")

    bad = {Status.FAIL}
    if args.strict:
        bad = {Status.FAIL, Status.WARN}
    return 1 if any(r.status in bad for r in results) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
