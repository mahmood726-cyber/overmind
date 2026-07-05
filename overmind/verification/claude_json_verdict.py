"""Typed Claude-lane verdicts via `claude -p --json-schema` (cc-adopt-4 win A3).

The Claude judge seat historically emitted a free-text ``VERDICT: PASS`` block
that ``LLMJudge._parse_verdict`` scraped with regex. Claude Code's
``--json-schema`` flag (stabilised ~v2.1.187) lets ``claude -p`` return a
schema-validated JSON object on stdout instead. This module provides:

  * ``CLAUDE_VERDICT_SCHEMA`` — the typed contract (adds ``objective_witness``,
    ``cross_vendor_check_present``, ``decorrelated`` as first-class fields, so the
    Stage-4 objective-gate floor is a typed field rather than a scraped line).
  * ``schema_cli_arg()`` — the compact JSON string for ``--json-schema``.
  * ``parse_typed_verdict()`` — JSON -> ``JudgeVerdict``, a drop-in replacement
    for the regex scraper that PRESERVES every truth-first failure semantic
    (JUDGE_ERROR passthrough, degenerate/empty -> abstain, unparseable ->
    ``judge_error``+``judge_parse_error`` so nothing silently auto-approves,
    injection/tamper -> refuse a coerced PASS) AND adds the objective-witness
    floor (a PASS with no passing objective witness is downgraded to abstain).

Flag-gated: the live judge flow is unchanged unless a caller opts in via
``ClaudeCodeBackend(json_schema=True)`` + ``LLMJudge(verdict_parser=...)`` or the
``build_claude_typed_judge`` helper. ``claude_json_schema_enabled()`` reads
``OVERMIND_CLAUDE_JSON_SCHEMA`` (default OFF) for callers that want an env switch.
"""
from __future__ import annotations

import json
import os
from typing import Any

from overmind.verification.llm_judge import (
    JudgeVerdict,
    LLMJudge,
    degenerate_response_reason,
    injection_tamper_reason,
)

JUDGE_ERROR = "JUDGE_ERROR:"

# The typed verdict contract handed to `claude -p --json-schema <this>`.
CLAUDE_VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string"},
        "concerns": {"type": "array", "items": {"type": "string"}},
        "requirements_met": {"type": "array", "items": {"type": "string"}},
        "requirements_missed": {"type": "array", "items": {"type": "string"}},
        # The D2 objective-gate floor, now a typed field instead of a scraped line.
        "objective_witness": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "present": {"type": "boolean"},
                "kind": {"type": "string"},
                "passed": {"type": "boolean"},
            },
            "required": ["present", "passed"],
        },
        "cross_vendor_check_present": {"type": "boolean"},
        "decorrelated": {"type": "boolean"},
    },
    "required": ["verdict", "confidence", "reasoning", "objective_witness"],
}


def schema_cli_arg() -> str:
    """Compact JSON for the ``--json-schema`` CLI argument (single line)."""
    return json.dumps(CLAUDE_VERDICT_SCHEMA, separators=(",", ":"))


def claude_json_schema_enabled() -> bool:
    """Env switch ``OVERMIND_CLAUDE_JSON_SCHEMA`` (default OFF). Off => the live
    Claude seat keeps the regex scraper byte-for-byte."""
    return os.environ.get("OVERMIND_CLAUDE_JSON_SCHEMA", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _judge_error(reason: str, raw: str, extra_concerns: list[str]) -> JudgeVerdict:
    # Mirror _parse_verdict's unparseable path: passed=True is inert because the
    # orchestrator gates on the judge_error concern (falls back to tests-only /
    # escalate) — never a silent approval.
    return JudgeVerdict(
        passed=True,
        confidence=0.0,
        reasoning=f"{reason}: {raw[:200]}",
        concerns=["judge_error", *extra_concerns],
    )


def parse_typed_verdict(raw: str) -> JudgeVerdict:
    """Parse a ``claude -p --json-schema`` JSON verdict into a ``JudgeVerdict``.

    Drop-in for ``LLMJudge._parse_verdict`` on the Claude seat. Same failure
    semantics, plus the objective-witness floor. Retires regex scraping without
    capability loss.
    """
    if raw.startswith(JUDGE_ERROR):
        # Backend-level failure (timeout, CLI error) — fall back to tests-only.
        return JudgeVerdict(
            passed=True,
            confidence=0.0,
            reasoning=f"Judge unavailable: {raw}",
            concerns=["judge_error"],
        )

    # Empty / filler / punctuation-only payloads must abstain, never pass.
    degenerate = degenerate_response_reason(raw)
    if degenerate is not None:
        return JudgeVerdict(
            passed=False,
            confidence=0.0,
            reasoning=f"Judge response degenerate ({degenerate}): {raw[:200]!r}",
            concerns=["judge_error", "judge_degenerate"],
        )

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return _judge_error("Judge JSON unparseable", raw, ["judge_parse_error"])
    if not isinstance(data, dict):
        return _judge_error("Judge JSON not an object", raw, ["judge_parse_error"])

    verdict = str(data.get("verdict", "")).upper()
    if verdict not in {"PASS", "FAIL", "UNKNOWN"}:
        return _judge_error("Judge JSON missing/invalid verdict", raw, ["judge_parse_error"])

    passed = verdict == "PASS"

    # Injection / planted-verdict guard on the free-text reasoning: a coerced PASS
    # is the dangerous direction — refuse it, abstain. (Schema constrains shape,
    # not that the model wasn't manipulated by injected witness/transcript text.)
    reasoning = str(data.get("reasoning", "No reasoning provided."))
    tamper = injection_tamper_reason(reasoning, verdict_passed=passed)
    if tamper is not None:
        return JudgeVerdict(
            passed=False,
            confidence=0.0,
            reasoning=f"Judge reply rejected — injection/tamper signature ({tamper}): {reasoning[:200]!r}",
            concerns=["judge_error", "judge_injection_suspected", tamper],
        )

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    concerns = [str(c) for c in (data.get("concerns") or []) if str(c).strip()]
    met = [str(x) for x in (data.get("requirements_met") or []) if str(x).strip()]
    missed = [str(x) for x in (data.get("requirements_missed") or []) if str(x).strip()]

    # Objective-gate floor (D2): a PASS is only honored if an objective witness is
    # present AND passed. A confident PASS with no passing witness is exactly the
    # "SKIP-as-pass / unverified release" failure mode — downgrade to abstain.
    witness = data.get("objective_witness") or {}
    witness_present = bool(witness.get("present", False))
    witness_passed = bool(witness.get("passed", False))
    if passed and not (witness_present and witness_passed):
        return JudgeVerdict(
            passed=False,
            confidence=0.0,
            reasoning=(
                "PASS refused — no passing objective witness "
                f"(present={witness_present}, passed={witness_passed}). {reasoning[:160]}"
            ),
            concerns=["judge_error", "objective_witness_missing", *concerns],
            requirements_met=met,
            requirements_missed=missed,
        )

    return JudgeVerdict(
        passed=passed,
        confidence=confidence,
        reasoning=reasoning,
        concerns=concerns,
        requirements_met=met,
        requirements_missed=missed,
    )


def build_claude_typed_judge(transcript_window: int = 80, use_cot: bool | None = None) -> LLMJudge:
    """Construct an ``LLMJudge`` whose Claude seat uses the typed ``--json-schema``
    path (structured emit + ``parse_typed_verdict``) instead of regex scraping.

    Imported lazily to avoid a circular import at module load.
    """
    from overmind.verification.judge_backends import ClaudeCodeBackend

    return LLMJudge(
        backend=ClaudeCodeBackend(json_schema=True),
        transcript_window=transcript_window,
        use_cot=use_cot,
        verdict_parser=parse_typed_verdict,
    )
