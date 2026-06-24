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
from dataclasses import dataclass, field
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

# Map each engine to its underlying model family. Judges in the SAME family share
# correlated failure modes, so they do not count as independent votes (audit A2 /
# arXiv:2605.29800 "Nine Judges, Two Effective Votes"). agy and gemini are both
# Google/Gemini; codex (both seats) is OpenAI; claude is Anthropic.
ENGINE_FAMILY: dict[str, str] = {
    "claude": "anthropic",
    "codex": "openai",
    "codex-noreen": "openai",
    "agy": "google",
    "gemini": "google",
    "local": "local",
    "stub": "stub",
}

# Each extra judge beyond the first in a family adds only a small fraction of an
# independent vote (diminishing, correlated). Heuristic, not a calibrated number —
# it exists to make over-counted panels visible, not to be precise.
_REDUNDANT_VOTE_WEIGHT = 0.25


@dataclass(slots=True)
class EffectiveVotes:
    """Independence estimate for a quorum panel."""
    nominal: int                       # how many judges
    distinct_families: int             # how many independent model families
    families: dict[str, int] = field(default_factory=dict)  # family -> count
    effective_votes: float = 0.0       # decorrelated estimate
    warning: str | None = None         # set when the panel over-counts independence


def family_for_engine(engine: str) -> str:
    """Model family for an engine name (unknown engines map to their own name)."""
    return ENGINE_FAMILY.get(engine.strip().lower(), engine.strip().lower())


def estimate_effective_votes(engines: list[str]) -> EffectiveVotes:
    """Estimate how many *independent* votes a quorum of these engines really has.

    Same-family judges share correlated errors, so a 3-engine quorum that is all
    Claude is ~1 effective vote, not 3. Returns the nominal count, the distinct
    family count, the per-family breakdown, a (heuristic) effective-vote estimate,
    and a warning string when nominal overstates independence.
    """
    families: dict[str, int] = {}
    for e in engines:
        fam = family_for_engine(e)
        families[fam] = families.get(fam, 0) + 1
    nominal = len(engines)
    distinct = len(families)
    redundant = nominal - distinct
    effective = distinct + _REDUNDANT_VOTE_WEIGHT * redundant
    warning = None
    if nominal > 1 and distinct < nominal:
        warning = (
            f"quorum of {nominal} judges spans only {distinct} model "
            f"{'family' if distinct == 1 else 'families'} ({families}); "
            f"same-family judges share correlated failure modes, so this is "
            f"~{effective:.1f} effective independent votes — do not treat it as "
            f"{nominal} independent checks. Prefer different-family engines."
        )
    return EffectiveVotes(
        nominal=nominal,
        distinct_families=distinct,
        families=families,
        effective_votes=effective,
        warning=warning,
    )


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
    use_cot: bool | None = None,
) -> LLMJudge | QuorumJudge:
    """Construct the judge from an engine spec + mode.

    spec  : engine names (defaults to env OVERMIND_JUDGE_ENGINE, then the
            default chain). mode: "fallback" (default) or "quorum"
            (defaults to env OVERMIND_JUDGE_MODE). use_cot: enable the
            CoT + rubric prompt (defaults to env OVERMIND_JUDGE_COT; None lets
            each LLMJudge read the env itself).
    """
    if spec is None:
        spec = os.environ.get("OVERMIND_JUDGE_ENGINE")
    if mode is None:
        mode = os.environ.get("OVERMIND_JUDGE_MODE", "fallback")
    mode = (mode or "fallback").strip().lower()

    engines = _parse_engine_spec(spec)

    if mode == "quorum" and len(engines) > 1:
        judges = [
            LLMJudge(backend=build_backend(e), transcript_window=transcript_window, use_cot=use_cot)
            for e in engines
        ]
        effective = estimate_effective_votes(engines)
        if effective.warning:
            logger.warning("LLM judge quorum: %s", effective.warning)
        logger.info(
            "LLM judge: quorum over %s (%d engines, ~%.1f effective independent votes across %d families)",
            engines, len(engines), effective.effective_votes, effective.distinct_families,
        )
        return QuorumJudge(
            judges=judges,
            nominal_votes=effective.nominal,
            effective_votes=effective.effective_votes,
            distinct_families=effective.distinct_families,
            panel_warning=effective.warning,
        )

    # Fallback chain (also the single-engine path: a 1-element chain still gets
    # the FallbackBackend wrapper so availability gating + clean degradation
    # apply uniformly).
    backends = [build_backend(e) for e in engines]
    logger.info("LLM judge: fallback chain %s", engines)
    return LLMJudge(
        backend=FallbackBackend(backends=backends),
        transcript_window=transcript_window,
        use_cot=use_cot,
    )
