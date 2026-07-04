"""Cross-vendor check-before-ship stage (T11 / T-CV / WORLD_CLASS_SPEC D1).

This is the *first-class* form of the triple-vendor witness we proved end-to-end
(Claude maker → Codex/agy checker). It runs an **independent, different-family**
bug-hunt / review pass over an artifact and records that a cross-vendor check was
present — the T-CV gate: "a different-vendor check ran before ship."

Two properties make it a differentiator rather than just another judge:
  1. **Decorrelation is enforced** — the checker's model family must differ from
     the writer's (Anthropic / OpenAI / Google), reusing ``judge_factory``'s
     family map. A same-family "check" is flagged non-decorrelated and does not
     count as an independent cross-vendor witness.
  2. **Advisory-first** — findings land as WARN-level advisories, never
     ship-blocking on the first cycle (research doc §2 T11). A false positive can
     never block a push. Promotion of a *finding class* to blocking is a later,
     measured step.

Gated behind ``OVERMIND_CROSS_VENDOR_CHECK`` (default 'off'; 'shadow' to run it
as an advisory producer). Backends are injectable so the whole stage is unit-
testable without spawning a CLI or burning quota. When no different-family
backend is live, the stage emits an explicit ``AUTH_DEGRADED`` reason rather than
silently "passing" an empty review.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from overmind.review.finding import ReviewFinding, parse_review_output
from overmind.verification.judge_backends import JUDGE_ERROR, AgyBackend, CodexBackend
from overmind.verification.judge_factory import family_for_engine

logger = logging.getLogger(__name__)

# Default checker preference order (different-family bug-hunters). Codex is our
# strongest bug-finder (research doc §2 T11); agy is the Google-family backstop.
DEFAULT_CHECKER_ENGINES: tuple[str, ...] = ("codex", "codex-noreen", "agy")

# Reasoning effort for the real bug-hunt pass (vs 'low' for a smoke probe).
BUGHUNT_EFFORT = "xhigh"


def check_mode() -> str:
    """'off' (default) | 'shadow' (run as advisory producer)."""
    raw = os.environ.get("OVERMIND_CROSS_VENDOR_CHECK", "off").strip().lower()
    if raw in {"shadow", "on", "1", "true", "yes"}:
        return "shadow"
    return "off"


# The RapidMeta P0-denominator-logic canary: an arithmetically-impossible 2x2 cell
# (events > N). A real bug-finder MUST flag this; a "found-nothing pass" on it is a
# canary FAILURE (research doc §1.4 / §3 benchmark). Concrete, non-fabricated —
# CAPLACIZUMAB_TTP cE=524 > cN=39.
CANARY_ARTIFACT = (
    "2x2 contingency table for CAPLACIZUMAB_TTP:\n"
    "  control arm: events cE=524, N cN=39\n"
    "  treatment arm: events tE=12, N tN=41\n"
    "Computed risk ratio from these cells."
)


@dataclass(slots=True)
class SeatProbe:
    """Result of a low-effort auth/liveness smoke probe of one Codex seat."""

    seat: str
    alive: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"seat": self.seat, "alive": self.alive, "detail": self.detail}


def smoke_probe_codex_seats(
    seats: tuple[str, ...] | list[str] = ("mahmood", "noreen"),
    *,
    backends: dict[str, object] | None = None,
    probe_prompt: str = "Reply with the single word READY.",
) -> list[SeatProbe]:
    """Low-effort liveness/auth probe of both Codex seats (T5 attestation smoke).

    Runs the cheap ``effort='low'`` probe so a real bug-hunt (xhigh) is only spent
    once seats are known live. A seat that is unavailable (no codex CLI / no
    CODEX_HOME) or returns a ``JUDGE_ERROR:`` (e.g. 401) is reported ``alive=False``
    — loud, not silently degraded. Backends are injectable for tests.
    """
    results: list[SeatProbe] = []
    for seat in seats:
        backend = (backends or {}).get(seat)
        if backend is None:
            backend = CodexBackend(seat=seat, effort="low")
        available = getattr(backend, "available", None)
        if callable(available) and not available():
            results.append(SeatProbe(seat, False, "unavailable (no codex CLI / CODEX_HOME)"))
            continue
        resp = backend.query(probe_prompt)
        if isinstance(resp, str) and resp.startswith(JUDGE_ERROR):
            results.append(SeatProbe(seat, False, resp[:120]))
        else:
            results.append(SeatProbe(seat, True, "ok"))
    return results


def is_found_nothing_pass(result: "CrossVendorCheckResult") -> bool:
    """True when a check on a KNOWN-buggy artifact came back PASS with no findings.

    On the canary this is a FAILURE signal — a bug-hunt that finds nothing on a
    planted defect has no signal (LFD found-nothing-pass fence)."""
    return bool(result.present and result.verdict == "PASS" and not result.findings)


def _build_backend(engine: str, effort: str | None):
    """Construct a checker backend for an engine name (bug-hunt tuned)."""
    name = engine.strip().lower()
    if name == "codex":
        return CodexBackend(seat="mahmood", effort=effort)
    if name == "codex-noreen":
        return CodexBackend(seat="noreen", effort=effort)
    if name == "agy":
        return AgyBackend()
    raise ValueError(f"unknown cross-vendor checker engine: {engine}")


@dataclass(slots=True)
class CrossVendorCheckResult:
    """Outcome of a cross-vendor check. Advisory — never a ship gate on cycle 1."""

    present: bool                       # T-CV gate: did a cross-vendor check run?
    decorrelated: bool                  # checker family != writer family
    writer_family: str
    checker_engine: str | None = None
    checker_family: str | None = None
    findings: list[ReviewFinding] = field(default_factory=list)
    verdict: str = "CONCERNS"           # advisory verdict (PASS/CONCERNS/BLOCK)
    reason: str = ""                    # why absent / degraded, when present=False
    raw_output: str = ""

    def to_dict(self) -> dict:
        return {
            "cross_vendor_check_present": self.present,
            "decorrelated": self.decorrelated,
            "writer_family": self.writer_family,
            "checker_engine": self.checker_engine,
            "checker_family": self.checker_family,
            "verdict": self.verdict,
            "num_findings": len(self.findings),
            "reason": self.reason,
        }


class CrossVendorChecker:
    """Runs a different-family bug-hunt over an artifact and records presence.

    ``backends`` is an optional injected mapping ``engine -> backend`` (each with
    ``.query(prompt)`` and optionally ``.available()``) so tests never spawn a
    CLI. When absent, real backends are constructed lazily per engine.
    """

    def __init__(
        self,
        checker_engines: tuple[str, ...] | list[str] = DEFAULT_CHECKER_ENGINES,
        *,
        effort: str | None = BUGHUNT_EFFORT,
        backends: dict[str, object] | None = None,
    ) -> None:
        self.checker_engines = tuple(checker_engines)
        self.effort = effort
        self._injected = backends

    def _backend_for(self, engine: str):
        if self._injected is not None and engine in self._injected:
            return self._injected[engine]
        return _build_backend(engine, self.effort)

    @staticmethod
    def _is_available(backend) -> bool:
        available = getattr(backend, "available", None)
        return available() if callable(available) else True

    def select_checker(self, writer_engine: str) -> tuple[str, object] | None:
        """Pick the first *live, different-family* checker for a writer engine.
        Returns (engine, backend) or None if none is available/decorrelated."""
        writer_family = family_for_engine(writer_engine)
        for engine in self.checker_engines:
            if family_for_engine(engine) == writer_family:
                continue  # same family — not a decorrelated cross-vendor check
            backend = self._backend_for(engine)
            if self._is_available(backend):
                return engine, backend
        return None

    def check(
        self,
        artifact: str,
        *,
        writer_engine: str = "claude",
        prompt_prefix: str | None = None,
    ) -> CrossVendorCheckResult:
        """Run the cross-vendor bug-hunt over ``artifact`` (code / diff / summary).

        Respects ``OVERMIND_CROSS_VENDOR_CHECK``: when 'off', returns a
        present=False result with reason='disabled' (no call made). Always
        advisory — the returned verdict never blocks a ship on its own.
        """
        writer_family = family_for_engine(writer_engine)
        if check_mode() == "off":
            return CrossVendorCheckResult(
                present=False, decorrelated=False, writer_family=writer_family,
                reason="disabled",
            )

        selected = self.select_checker(writer_engine)
        if selected is None:
            # No live different-family backend — be loud, don't fake a pass.
            logger.warning(
                "cross-vendor check AUTH_DEGRADED: no live different-family "
                "checker for writer=%s (family=%s); tried %s",
                writer_engine, writer_family, list(self.checker_engines),
            )
            return CrossVendorCheckResult(
                present=False, decorrelated=False, writer_family=writer_family,
                reason="AUTH_DEGRADED: no live different-family checker",
            )

        engine, backend = selected
        checker_family = family_for_engine(engine)
        prompt = self._build_prompt(artifact, prompt_prefix)
        raw = backend.query(prompt)

        if isinstance(raw, str) and raw.startswith(JUDGE_ERROR):
            logger.warning("cross-vendor checker %s failed: %s", engine, raw[:160])
            return CrossVendorCheckResult(
                present=False, decorrelated=True, writer_family=writer_family,
                checker_engine=engine, checker_family=checker_family,
                reason=f"checker_error: {raw[:160]}", raw_output=raw,
            )

        parsed = parse_review_output(f"codex-checker:{engine}", raw or "")
        result = CrossVendorCheckResult(
            present=True,
            decorrelated=(checker_family != writer_family),
            writer_family=writer_family,
            checker_engine=engine,
            checker_family=checker_family,
            findings=parsed.findings,
            verdict=parsed.verdict,
            raw_output=raw or "",
        )
        # Advisory WARN when the different-vendor checker raised concerns — never
        # ship-blocking on cycle 1.
        if result.findings:
            logger.warning(
                "cross-vendor check (%s, family=%s) raised %d advisory finding(s) "
                "on writer=%s artifact — ADVISORY ONLY, not ship-blocking",
                engine, checker_family, len(result.findings), writer_engine,
            )
        return result

    @staticmethod
    def _build_prompt(artifact: str, prompt_prefix: str | None) -> str:
        header = prompt_prefix or (
            "You are an independent, adversarial code reviewer from a DIFFERENT "
            "vendor than the author. Hunt for real correctness bugs: off-by-one, "
            "impossible arithmetic (e.g. events > N in a 2x2 table), silent "
            "wrong-number defects, unhandled edge cases. Trust tests/diffs over "
            "the author's narrative. Report each finding on its own line as "
            "'- [P0|P1|P2] <description> (<file:line>)' and end with "
            "'VERDICT: PASS|CONCERNS|BLOCK'. If you find nothing, say so "
            "explicitly and VERDICT: PASS."
        )
        return f"{header}\n\n--- ARTIFACT UNDER REVIEW ---\n{artifact}\n--- END ---\n"
