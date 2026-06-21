"""Config/env-driven judge construction (audit P2-12 / design point 1).

Selects the judge backend among the supported engines, with a sane default and
graceful fallback, removing the single-GEMINI_API_KEY dependency.

Engine names (``OVERMIND_JUDGE_ENGINE``):
    claude         Claude Code CLI            (default; correctness-critical)
    codex          Codex `codex exec`, mahmood seat
    codex-noreen   Codex `codex exec`, noreen seat
    agy            agy-driver (Antigravity/Gemini over OAuth)
    gemini         direct Gemini API
    local          local runtime (Gemma/Qwen) — OFF unless OVERMIND_LOCAL_MODEL=1
    stub           deterministic stub (tests)

Config contract:
    OVERMIND_JUDGE_ENGINE  comma-separated, ordered.
        - one value  -> that engine, wrapped so it still degrades cleanly
        - many values + OVERMIND_JUDGE_MODE=fallback (default) -> try in order
        - many values + OVERMIND_JUDGE_MODE=quorum -> QuorumJudge over all
    Default when unset: "claude,gemini" fallback chain (strong primary, API
    secondary), matching the model-selection policy: Opus-class reasoning for
    the judge, with a non-Claude backstop so a Claude outage still produces a
    verdict.

Everything is fail-soft: an unknown engine name is dropped with a logged
warning rather than crashing the orchestrator, and an empty resulting chain
falls back to the default.
"""
from __future__ import annotations

import logging
import os
from typing import Callable

from overmind.verification.llm_judge import (
    GeminiBackend,
    LLMJudge,
    QuorumJudge,
    StubBackend,
)
from overmind.verification.judge_backends import (
    AgyBackend,
    ClaudeCodeBackend,
    CodexBackend,
    FallbackBackend,
    LocalModelBackend,
)

logger = logging.getLogger(__name__)

# name -> zero-arg builder returning a backend with a .query(prompt) method.
ENGINE_BUILDERS: dict[str, Callable[[], object]] = {
    "claude": lambda: ClaudeCodeBackend(),
    "codex": lambda: CodexBackend(seat="mahmood"),
    "codex-noreen": lambda: CodexBackend(seat="noreen"),
    "agy": lambda: AgyBackend(),
    "gemini": lambda: GeminiBackend(),
    "local": lambda: LocalModelBackend(),
    "stub": lambda: StubBackend(),
}

KNOWN_ENGINES = frozenset(ENGINE_BUILDERS)

DEFAULT_ENGINE_CHAIN = ("claude", "gemini")


def build_backend(engine: str) -> object:
    """Build a single backend by engine name (raises KeyError if unknown)."""
    return ENGINE_BUILDERS[engine.strip().lower()]()


def _parse_engine_spec(spec: str | None) -> list[str]:
    """Parse a comma/semicolon-separated engine spec into known engine names."""
    if not spec:
        return list(DEFAULT_ENGINE_CHAIN)
    raw = [t.strip().lower() for t in spec.replace(";", ",").split(",")]
    chosen = [t for t in raw if t]
    unknown = [t for t in chosen if t not in KNOWN_ENGINES]
    for u in unknown:
        logger.warning("Unknown judge engine %r ignored (known: %s)", u, ", ".join(sorted(KNOWN_ENGINES)))
    valid = [t for t in chosen if t in KNOWN_ENGINES]
    if not valid:
        logger.warning("No valid judge engines in %r; using default chain %s", spec, DEFAULT_ENGINE_CHAIN)
        return list(DEFAULT_ENGINE_CHAIN)
    return valid


def build_judge(
    spec: str | None = None,
    mode: str | None = None,
    transcript_window: int = 80,
) -> LLMJudge | QuorumJudge:
    """Construct the judge from an engine spec + mode.

    spec  : engine names (defaults to env OVERMIND_JUDGE_ENGINE, then the
            default chain). mode: "fallback" (default) or "quorum"
            (defaults to env OVERMIND_JUDGE_MODE).
    """
    if spec is None:
        spec = os.environ.get("OVERMIND_JUDGE_ENGINE")
    if mode is None:
        mode = os.environ.get("OVERMIND_JUDGE_MODE", "fallback")
    mode = (mode or "fallback").strip().lower()

    engines = _parse_engine_spec(spec)

    if mode == "quorum" and len(engines) > 1:
        judges = [LLMJudge(backend=build_backend(e), transcript_window=transcript_window) for e in engines]
        logger.info("LLM judge: quorum over %s", engines)
        return QuorumJudge(judges=judges)

    # Fallback chain (also the single-engine path: a 1-element chain still gets
    # the FallbackBackend wrapper so availability gating + clean degradation
    # apply uniformly).
    backends = [build_backend(e) for e in engines]
    logger.info("LLM judge: fallback chain %s", engines)
    return LLMJudge(backend=FallbackBackend(backends=backends), transcript_window=transcript_window)
