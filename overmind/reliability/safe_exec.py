"""Anti-wedge subprocess launch + ReDoS screen (reliability — item 4).

Today a runaway node/lint process (and a catastrophic-backtrack regex) wedged a
session. This module is the hardened launch path so that can't happen:

  * ``run_guarded`` — bounded wall-clock timeout, **process-tree kill** on expiry
    (reuses ``subprocess_utils.kill_process_tree`` — reaches grandchildren on
    Windows), **stdin from NUL/DEVNULL** so a process that blocks reading stdin
    can never hang the launcher, and a scrubbed env. Never uses ``shell=True``.
  * ``looks_catastrophic`` / ``compile_guarded`` — a heuristic ReDoS screen so a
    rule-authored pattern with nested unbounded quantifiers (``(a+)+``) is caught
    before it runs, rather than hanging the scan.

Both are opt-in helpers; importing this module changes nothing on its own.
"""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from overmind.subprocess_utils import kill_process_tree, safe_subprocess_env, split_command

DEFAULT_TIMEOUT_SECONDS = 120.0


@dataclass(slots=True)
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def run_guarded(
    command: str | list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    stdin_text: str | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> ExecResult:
    """Run a subprocess with a hard timeout, process-tree kill, and a stdin that
    can never wedge the launcher.

    ``command`` may be a pre-split argv list or a string (split via
    ``split_command``). On timeout the whole process tree is killed and
    ``timed_out=True`` / ``returncode=-1`` is returned — the caller never wedges.

    ``stdin_text``:
      * ``None`` (default) — stdin is ``DEVNULL`` (NUL on Windows): a process that
        blocks reading stdin gets EOF immediately and cannot hang the launcher.
      * a string — the text is written to the child's stdin and stdin is then
        **closed** (EOF sent). This is the anti-wedge-safe way to deliver a prompt
        on stdin (e.g. ``claude -p`` / ``codex exec -``): the child receives its
        input and an EOF, so it can never block waiting for *more* stdin — the D3
        ``codex exec`` "reading additional input from stdin…" hang. Delivering a
        prompt this way still gets the full tree-kill + hard-timeout guard, unlike
        a bare ``subprocess.run`` which kills only the direct child.
    """
    argv = command if isinstance(command, list) else split_command(command)
    run_env = safe_subprocess_env()
    if env:
        run_env.update(env)
    start = clock()
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            shell=False,
            # PIPE when we have a prompt to deliver (written+closed below), else
            # DEVNULL. Either way the child gets an EOF and never blocks on stdin.
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
        )
    except (OSError, ValueError) as exc:
        return ExecResult(-1, "", f"failed to start: {exc}", False, clock() - start)

    try:
        stdout, stderr = proc.communicate(input=stdin_text, timeout=timeout)
        return ExecResult(proc.returncode, stdout or "", stderr or "", False, clock() - start)
    except subprocess.TimeoutExpired:
        kill_process_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            # Tree-kill did not reap it within 5s. Force-kill the direct child and
            # release the pipe FDs so no reader thread / file handle leaks and no
            # possibly-live process is left dangling (P1-8, cross-vendor 2026-07-11).
            try:
                proc.kill()
            except OSError:
                pass
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except OSError:
                    pass
            stdout, stderr = "", ""
        return ExecResult(
            -1, stdout or "", (stderr or "") + f"\n[timed out after {timeout}s; process tree killed]",
            True, clock() - start,
        )


# --- ReDoS screen ---------------------------------------------------------------

# An unbounded quantifier: +, *, or {n,} (comma with no upper bound). {1,80} is
# bounded and does NOT match.
_UNBOUNDED = re.compile(r"[+*]|\{\d+,\}")
# A group ( ... ) immediately followed by an unbounded quantifier.
_GROUP_THEN_UNBOUNDED = re.compile(r"\(([^()]*)\)\s*(?:[+*]|\{\d+,\})")


def looks_catastrophic(pattern: str) -> bool:
    """Heuristic: True if ``pattern`` has a group with an inner unbounded
    quantifier that is itself unbounded-quantified — the classic
    catastrophic-backtracking shape ``(a+)+`` / ``(.*)*`` / ``([a-z]+){2,}``.

    Conservative (few false positives): plain ``a+``, ``[abc]+``, ``(abc)+`` and
    bounded ``\\d{1,80}`` are NOT flagged. Does not descend nested groups — a
    heuristic pre-screen, not a proof.
    """
    for m in _GROUP_THEN_UNBOUNDED.finditer(pattern):
        if _UNBOUNDED.search(m.group(1)):
            return True
    return False


def compile_guarded(pattern: str, flags: int = 0) -> re.Pattern:
    """Compile a regex, refusing patterns that look catastrophic.

    Raises ``ValueError`` on a catastrophic shape so a rule loader fails closed
    (log + skip the rule) instead of letting the pattern wedge a scan.
    """
    if looks_catastrophic(pattern):
        raise ValueError(f"refusing likely-catastrophic regex (ReDoS): {pattern[:120]!r}")
    return re.compile(pattern, flags)
