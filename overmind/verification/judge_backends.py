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
import shutil
import subprocess
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
    """Run a CLI under a scrubbed env, piping the prompt on stdin."""
    env = safe_subprocess_env()
    env.update(env_overrides)
    try:
        result = subprocess.run(
            argv,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        return f"{JUDGE_ERROR} {type(exc).__name__}: {str(exc)[:200]}"
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:200]
        return f"{JUDGE_ERROR} exit {result.returncode}: {stderr}"
    return result.stdout.strip()


@dataclass(slots=True)
class ClaudeCodeBackend:
    """Judge via the Claude Code CLI (`claude -p`). Prompt on stdin.

    Model-selection: this is the default for correctness-critical judging —
    Opus-class reasoning. No API key needed (uses the logged-in CLI session).
    """

    command: str = "claude -p"
    timeout: int = 180
    runner: Runner = _default_runner

    def available(self) -> bool:
        return shutil.which(self.command.split()[0]) is not None

    def query(self, prompt: str) -> str:
        return self.runner(split_command(self.command), prompt, {}, self.timeout)


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

    def _codex_home(self) -> Path:
        override = os.environ.get("OVERMIND_CODEX_HOME_" + self.seat.upper())
        if override:
            return Path(override)
        dirname = ".codex" if self.seat == "mahmood" else f".codex-{self.seat}"
        return Path.home() / dirname

    def available(self) -> bool:
        return shutil.which(self.command) is not None and self._codex_home().is_dir()

    def query(self, prompt: str) -> str:
        argv = [self.command, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-"]
        return self.runner(argv, prompt, {"CODEX_HOME": str(self._codex_home())}, self.timeout)


@dataclass(slots=True)
class AgyBackend:
    """Judge via the agy-driver (Antigravity/Gemini over OAuth).

    Uses the user's Gemini quota through the logged-in Antigravity session
    rather than the shared API key — diversifies the blast radius. The driver
    takes the prompt as a CLI arg and emits JSON with a ``text`` field.
    """

    model: str = "pro"
    timeout: int = 180
    runner: Runner = _default_runner
    driver_path: str | None = None

    def _driver(self) -> Path | None:
        override = self.driver_path or os.environ.get("AGY_DRIVER_PATH")
        if override:
            p = Path(override)
            return p if p.is_file() else None
        candidate = Path.home() / "agy-driver" / "agy_driver.py"
        return candidate if candidate.is_file() else None

    def available(self) -> bool:
        return self._driver() is not None

    def query(self, prompt: str) -> str:
        driver = self._driver()
        if driver is None:
            return f"{JUDGE_ERROR} agy-driver not found"
        argv = ["python", str(driver), "--json", "--model", self.model, prompt]
        raw = self.runner(argv, "", {}, self.timeout)
        if raw.startswith(JUDGE_ERROR):
            return raw
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Driver may print non-JSON banner lines; fall back to raw text.
            return raw
        text = data.get("text", "")
        return text if text else f"{JUDGE_ERROR} agy returned empty text"


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
