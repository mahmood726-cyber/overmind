"""Pluggable judge backends + fallback wiring (audit P2-12 / design point 1).

The LLM judge was hard-wired to Gemini (single GEMINI_API_KEY dependency). This
module adds the other engines the model-selection policy calls for and a
fallback wrapper so the judge keeps working when the primary engine is
unavailable or over quota:

  - ClaudeCodeBackend : `claude -p` — strong reasoning, correctness-critical judging
  - CodexBackend      : `codex exec` (both seats: .codex / .codex-noreen)
  - AgyBackend        : agy-driver (Antigravity/Gemini via OAuth, off the API key)
  - LocalModelBackend : local runtime (Gemma/Qwen) — OFF by default, for cheap
                        high-volume non-correctness-critical work
  - GeminiBackend     : direct Gemini API (lives in llm_judge.py)

Every backend exposes ``query(prompt) -> str`` (returning a ``JUDGE_ERROR:``
prefix on failure, matching the existing contract that the orchestrator gates
on) and ``available() -> bool`` so the fallback layer can skip a down engine
without burning a call. Subprocess backends accept an injectable ``runner`` so
the routing/fallback logic is fully unit-testable without spawning a CLI or
burning quota.

Security: subprocess backends run under a scrubbed env (safe_subprocess_env)
plus only the explicit overrides they need (e.g. CODEX_HOME); secret values are
never logged or echoed.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

from overmind.subprocess_utils import safe_subprocess_env, split_command

# A runner takes (argv, stdin_text, env_overrides, timeout) and returns stdout.
Runner = Callable[[list[str], str, dict[str, str], int], str]

JUDGE_ERROR = "JUDGE_ERROR:"


def _default_runner(
    argv: list[str], stdin_text: str, env_overrides: dict[str, str], timeout: int
) -> str:
    """Run a vendor CLI under a scrubbed env, delivering the prompt on stdin.

    Routes through the anti-wedge chokepoint ``reliability.safe_exec.run_guarded``
    (D1/D2/D3 hardening 2026-07-10) so every vendor exec — ``claude -p``,
    ``ssh … claude -p``, ``codex exec -``, agy — inherits a **process-tree kill on
    timeout** (a bare ``subprocess.run`` kills only the direct child, leaking the
    ssh/codex grandchildren that wedged nightly workers) and a stdin that is
    written-then-closed (EOF), so a CLI that keeps reading stdin cannot hang the
    launcher. Behaviour on the happy path and on a non-zero exit is unchanged; only
    a timeout now tears down the whole tree instead of leaking it.

    The ``JUDGE_ERROR:`` string contract the orchestrator/fallback gate on is
    preserved: a timeout / spawn failure / non-zero exit all return a
    ``JUDGE_ERROR:``-prefixed string; success returns the stripped stdout.
    """
    from overmind.reliability.safe_exec import run_guarded

    env = safe_subprocess_env()
    env.update(env_overrides)
    res = run_guarded(argv, timeout=float(timeout), env=env, stdin_text=stdin_text)
    if res.timed_out:
        return f"{JUDGE_ERROR} TimeoutExpired: timed out after {timeout}s; process tree killed"
    if res.returncode == -1 and "failed to start" in res.stderr:
        # spawn failure (OSError/ValueError) — matches the prior OSError path
        return f"{JUDGE_ERROR} OSError: {res.stderr.strip()[:200]}"
    if res.returncode != 0:
        return f"{JUDGE_ERROR} exit {res.returncode}: {(res.stderr or '').strip()[:200]}"
    return res.stdout.strip()


@dataclass(slots=True)
class ClaudeCodeBackend:
    """Judge via the Claude Code CLI (`claude -p`). Prompt on stdin.

    Model-selection: this is the default for correctness-critical judging —
    Opus-class reasoning. **Auth is the subscription OAuth token, NOT an API key:**
    it resolves ``CLAUDE_CODE_OAUTH_TOKEN`` and passes it to the subprocess as a
    bearer credential (subscription billing preserved). ``ANTHROPIC_API_KEY`` is
    only a fallback when no OAuth token is present. Without a token the CLI reports
    "Not logged in" (a headless subprocess does not inherit the interactive
    session's keychain creds), so the token is the supported headless path.
    """

    command: str = "claude -p"
    timeout: int = 180
    runner: Runner = _default_runner
    oauth_token: str | None = None       # explicit override; else CLAUDE_CODE_OAUTH_TOKEN
    # A3 (cc-adopt-4): when True, request a schema-validated JSON verdict via
    # `--json-schema` instead of a free-text VERDICT block. Default False keeps
    # the argv (and the live verdict flow) byte-for-byte unchanged; the typed
    # output is parsed by claude_json_verdict.parse_typed_verdict, not the regex
    # scraper. Kept as a flag so this only touches the verdict flow when opted in.
    json_schema: bool = False

    def _oauth_token(self) -> str | None:
        return self.oauth_token or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or None

    def _auth_env(self) -> dict[str, str]:
        token = self._oauth_token()
        return {"CLAUDE_CODE_OAUTH_TOKEN": token} if token else {}

    def available(self) -> bool:
        # CLI present AND some auth path resolvable (OAuth token or API key).
        if shutil.which(self.command.split()[0]) is None:
            return False
        return bool(self._oauth_token()) or bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _argv(self) -> list[str]:
        argv = split_command(self.command)
        if self.json_schema:
            # Local import: judge_backends must not import claude_json_verdict at
            # module load (that module imports from llm_judge).
            from overmind.verification.claude_json_verdict import schema_cli_arg
            argv += ["--json-schema", schema_cli_arg()]
        return argv

    def query(self, prompt: str) -> str:
        return self.runner(self._argv(), prompt, self._auth_env(), self.timeout)


@dataclass(slots=True)
class SshClaudeBackend:
    """Judge via `claude -p` on a REMOTE node over SSH (additive; flag-gated).

    Motivation: headless `claude -p` on the local node can be unauthed (stale
    OAuth token / empty credentials / the desktop-host OAuth-refresh IPC is not
    reachable from a bare subprocess), while ANOTHER node holds a valid Claude
    Code SUBSCRIPTION login. This backend runs the worker there:
    ``ssh <host> claude -p`` with the prompt piped on stdin, returning the
    subscription completion. No API key, no metered path — the subscription
    bearer lives only on the remote node.

    Enabled only when a host is configured (``host`` arg or
    OVERMIND_CLAUDE_SSH_HOST); otherwise ``available()`` is False and the harness
    keeps using the local token path — this class never displaces it. The runner
    is injectable so routing/parse logic is unit-testable without a real SSH hop.
    """

    host: str | None = None                # e.g. mahmo@100.80.183.43
    key: str | None = None                 # ssh identity file (-i)
    # Portable default: a bare `claude -p` the REMOTE node's PATH resolves (matches
    # ClaudeCodeBackend.command and the `ssh <host> claude -p` worker documented in
    # scripts/run_benchmark.py). This runs on ANY node (laptop/pc2/…), not just a
    # machine where claude sits at a specific absolute path. `shutil.which` can't be
    # used here — it resolves on the LOCAL node, but this command runs remotely — so
    # a node whose non-interactive SSH PATH lacks claude sets an absolute path via
    # OVERMIND_CLAUDE_SSH_REMOTE_CMD (see _remote()) instead of hardcoding one here.
    remote_cmd: str = "claude -p"
    ssh_command: str = "ssh"
    timeout: int = 180
    runner: Runner = _default_runner

    # Benign SSH advisory lines that may precede the real completion on stdout on
    # some configs (the post-quantum KX warning normally goes to stderr, but strip
    # defensively so they never corrupt the parsed verdict).
    _SSH_NOISE = ("post-quantum", "store now, decrypt", "openssh.com",
                  "may need to be upgraded", "This session may be vulnerable")

    def _host(self) -> str | None:
        return self.host or os.environ.get("OVERMIND_CLAUDE_SSH_HOST") or None

    def _key(self) -> str | None:
        return self.key or os.environ.get("OVERMIND_CLAUDE_SSH_KEY") or None

    def _remote(self) -> str:
        return os.environ.get("OVERMIND_CLAUDE_SSH_REMOTE_CMD") or self.remote_cmd

    def available(self) -> bool:
        if shutil.which(self.ssh_command) is None:
            return False
        if not self._host():
            return False
        key = self._key()
        if key and not Path(key).is_file():
            return False
        return True

    def _argv(self) -> list[str]:
        argv = [self.ssh_command, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
        key = self._key()
        if key:
            argv += ["-i", key]
        argv += [self._host() or "", self._remote()]
        return argv

    def query(self, prompt: str) -> str:
        if not self._host():
            return f"{JUDGE_ERROR} no SSH host configured (OVERMIND_CLAUDE_SSH_HOST)"
        raw = self.runner(self._argv(), prompt, {}, self.timeout)
        if raw.startswith(JUDGE_ERROR):
            return raw
        lines = [ln for ln in raw.splitlines() if not any(m in ln for m in self._SSH_NOISE)]
        return "\n".join(lines).strip()


@dataclass(slots=True)
class CodexBackend:
    """Judge via `codex exec` for parallel verification bursts.

    Two seats share one round-robin: ``seat="mahmood"`` -> ~/.codex,
    ``seat="noreen"`` -> ~/.codex-noreen, selected by CODEX_HOME. Runs
    read-only (`--sandbox read-only`) and `--skip-git-repo-check` so the judge
    never mutates a repo.
    """

    seat: str = "mahmood"
    timeout: int = 180
    runner: Runner = _default_runner
    command: str = "codex"
    # Reasoning-effort knob (T11 / WORLD_CLASS_SPEC D1). None => current behavior
    # byte-for-byte (no config override appended). Use 'low' for the cheap
    # availability/smoke probe, 'xhigh' for the real bug-hunt pass.
    effort: str | None = None

    def _codex_home(self) -> Path:
        override = os.environ.get("OVERMIND_CODEX_HOME_" + self.seat.upper())
        if override:
            return Path(override)
        dirname = ".codex" if self.seat == "mahmood" else f".codex-{self.seat}"
        return Path.home() / dirname

    def available(self) -> bool:
        return shutil.which(self.command) is not None and self._codex_home().is_dir()

    def query(self, prompt: str) -> str:
        cmd = shutil.which(self.command) or self.command
        argv = [cmd, "exec", "--skip-git-repo-check", "--sandbox", "read-only"]
        if self.effort:
            # codex config override for reasoning effort; appended only when set
            # so the default (effort=None) argv is unchanged.
            argv += ["--config", f"model_reasoning_effort={self.effort}"]
        argv += ["-"]
        # On Windows, .CMD / .BAT files cannot be executed directly by subprocess
        # without shell=True.  Wrap with `cmd /c` so the runner stays shell=False.
        if sys.platform == "win32" and cmd.upper().endswith((".CMD", ".BAT")):
            argv = ["cmd", "/c"] + argv
        return self.runner(argv, prompt, {"CODEX_HOME": str(self._codex_home())}, self.timeout)


# --- agy async-envelope handling (gap-analysis close #1) ------------------------
# agy (Antigravity/Gemini) is an AGENTIC model: given a question it frequently runs
# a *tool* (execute a python snippet, list a directory) instead of answering, and
# the driver returns the tool-invocation ENVELOPE as the turn's "text" — a
# still-running handle ("Tool is running as a background task with task id …") or a
# bare "Created At: … / The command completed" wrapper with no answer body. That
# envelope has no FLAG/VERDICT line, so the reviewer parses it as unusable and agy's
# real judgment is lost. In the 2026-07-06 held-out run this was 9 of Arm C's 10
# missed defects — NOT a reasoning failure (agy hits ~98% when it actually answers),
# a plumbing bug. The fix: (a) prepend a directive that forbids tool use and demands
# a direct plain-text answer, and (b) if an envelope still comes back, POLL — re-ask
# (bounded) until a real answer is captured, then fail closed if it never is.
_AGY_DIRECT_ANSWER_PREFIX = (
    "IMPORTANT: You are a text-only reviewer. Do NOT run any tools, code, shell, or "
    "background commands, and do NOT inspect the filesystem. Reason only from the "
    "text in this message and reply in plain text with the answer directly.\n\n"
)
_AGY_RETRY_PREFIX = (
    "CRITICAL: Your previous reply launched a tool/background task instead of "
    "answering. Do NOT run any tool, command, or background task. Answer NOW, using "
    "ONLY your own reasoning over the text below, in plain text.\n\n"
)
# Markers of a driver tool-envelope rather than a model answer.
_AGY_ENVELOPE_MARKERS = (
    "is running as a background task",
    "The command completed",
    "The command failed with exit code",
    "Completed At:",
)
_AGY_ANSWER_RE = re.compile(r"\b(FLAG|VERDICT|ANSWER)\s*:", re.IGNORECASE)


def is_async_envelope(text: str) -> bool:
    """True when ``text`` is an agy tool-invocation envelope, not a model answer.

    An answer (a FLAG/VERDICT/ANSWER line) is never treated as an envelope even if a
    tool also ran. Otherwise a leading ``Created At:`` tool-step header, a
    still-running background-task handle, or a ``command completed`` wrapper marks an
    envelope. Empty text is NOT an envelope (a distinct failure handled by caller)."""
    t = (text or "").strip()
    if not t:
        return False
    if _AGY_ANSWER_RE.search(t):
        return False
    if t.startswith("Created At:"):
        return True
    return any(m in t for m in _AGY_ENVELOPE_MARKERS)


@dataclass(slots=True)
class AgyBackend:
    """Judge via the agy-driver (Antigravity/Gemini over OAuth).

    Uses the user's Gemini quota through the logged-in Antigravity session
    rather than the shared API key — diversifies the blast radius. The driver
    takes the prompt as a CLI arg and emits JSON with a ``text`` field.

    Because agy is agentic and tends to run tools rather than answer, ``query``
    prepends a no-tools directive and POLLS (bounded ``max_polls`` re-asks) past any
    async envelope until a real answer is captured — recovering agy's judgment
    instead of dropping an unusable wrapper. See ``is_async_envelope``.
    """

    model: str = "pro"
    timeout: int = 180
    runner: Runner = _default_runner
    driver_path: str | None = None
    max_polls: int = 3            # total attempts (1 initial + up to 2 re-polls) on an envelope

    def _driver(self) -> Path | None:
        override = self.driver_path or os.environ.get("AGY_DRIVER_PATH")
        if override:
            p = Path(override)
            return p if p.is_file() else None
        candidate = Path.home() / "agy-driver" / "agy_driver.py"
        return candidate if candidate.is_file() else None

    def available(self) -> bool:
        return self._driver() is not None

    def _argv(self, driver: Path, prompt: str) -> list[str]:
        # `--` before the prompt so a prompt that begins with `-`/`--` (e.g. a code
        # snippet, or the "--print-timeout 280s" fragility class) is bound as the
        # POSITIONAL prompt and never mis-parsed as a driver flag. Everything after
        # `--` is positional to argparse. (agy arg-parsing fragility, #5.)
        return ["python", str(driver), "--json", "--quiet-driver",
                "--model", self.model, "--", prompt]

    @staticmethod
    def _extract_answer(raw: str) -> str:
        """Pull the model answer out of the driver's --json payload. Prefers a
        FLAG/VERDICT-bearing chunk (recovering an answer emitted BEFORE a trailing
        tool step) over the terminal ``text`` field."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw  # non-JSON banner lines — fall back to raw text
        text = (data.get("text") or "").strip()
        if _AGY_ANSWER_RE.search(text):
            return text
        all_model = (data.get("all_model_text") or "").strip()
        if _AGY_ANSWER_RE.search(all_model):
            return all_model
        return text

    def query(self, prompt: str) -> str:
        driver = self._driver()
        if driver is None:
            return f"{JUDGE_ERROR} agy-driver not found"
        attempts = max(1, self.max_polls)
        last_text = ""
        for i in range(attempts):
            prefix = _AGY_DIRECT_ANSWER_PREFIX if i == 0 else _AGY_RETRY_PREFIX
            raw = self.runner(self._argv(driver, prefix + prompt), "", {}, self.timeout)
            if raw.startswith(JUDGE_ERROR):
                return raw
            text = self._extract_answer(raw)
            if text:
                last_text = text
            if text and not is_async_envelope(text):
                return text
            # envelope or empty -> poll again with a stronger no-tools directive
        if not last_text:
            return f"{JUDGE_ERROR} agy returned empty text"
        return f"{JUDGE_ERROR} agy returned only an async envelope after {attempts} polls"


@dataclass(slots=True)
class LocalModelBackend:
    """Judge via a local OpenAI/Ollama-compatible runtime (Gemma/Qwen).

    OFF by default (design point 2): only usable when OVERMIND_LOCAL_MODEL=1 (or
    ``enabled=True``). Intended for cheap, high-volume, NON-correctness-critical
    work — never the sole judge for a ship decision. Talks to an Ollama-style
    ``/api/generate`` endpoint with no third-party dependency.
    """

    model: str = "qwen2.5"
    endpoint: str = "http://localhost:11434/api/generate"
    timeout: int = 120
    enabled: bool | None = None
    _http: Callable[[str, bytes, int], str] | None = None

    def _is_enabled(self) -> bool:
        if self.enabled is not None:
            return self.enabled
        return os.environ.get("OVERMIND_LOCAL_MODEL", "").strip().lower() in {"1", "true", "yes", "on"}

    def available(self) -> bool:
        return self._is_enabled()

    def query(self, prompt: str) -> str:
        if not self._is_enabled():
            return f"{JUDGE_ERROR} local model lane disabled (set OVERMIND_LOCAL_MODEL=1)"
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode("utf-8")
        try:
            raw = (self._http or _default_http)(self.endpoint, payload, self.timeout)
        except Exception as exc:  # noqa: BLE001 — local runtime optional, isolate
            return f"{JUDGE_ERROR} local model unreachable: {type(exc).__name__}: {str(exc)[:160]}"
        try:
            return json.loads(raw).get("response", f"{JUDGE_ERROR} empty local response")
        except json.JSONDecodeError:
            return raw.strip() or f"{JUDGE_ERROR} empty local response"


def _default_http(url: str, payload: bytes, timeout: int) -> str:
    from urllib.request import Request, urlopen

    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — localhost only
        return resp.read().decode("utf-8")


@dataclass(slots=True)
class FallbackBackend:
    """Try an ordered list of backends; return the first usable verdict.

    Skips backends whose ``available()`` is False (no wasted call), and treats a
    ``JUDGE_ERROR:`` response as "try the next engine" — so an over-quota or
    down primary transparently falls through to the next. Returns a combined
    ``JUDGE_ERROR:`` only if every backend is unavailable/failed, which the
    orchestrator then handles by falling back to test-suite-only verification.
    """

    backends: list[object]

    def query(self, prompt: str) -> str:
        errors: list[str] = []
        for position, backend in enumerate(self.backends):
            name = type(backend).__name__
            available = getattr(backend, "available", None)
            if callable(available) and not available():
                errors.append(f"{name}: unavailable")
                continue
            response = backend.query(prompt)
            if not response.startswith(JUDGE_ERROR):
                # Observability (agy review point): make a silent downgrade to a
                # non-primary backend visible, so reduced advisory confidence is
                # never hidden. INFO when primary served; WARNING when a later
                # backend did because earlier ones were down/over-quota.
                if position == 0:
                    logger.info("judge served by primary backend %s", name)
                else:
                    logger.warning(
                        "judge fell back to backend %s (position %d); "
                        "earlier backends unavailable/failed: %s",
                        name, position, " | ".join(errors),
                    )
                return response
            errors.append(f"{name}: {response}")
        return f"{JUDGE_ERROR} all judge backends failed [{' | '.join(errors) or 'none configured'}]"
