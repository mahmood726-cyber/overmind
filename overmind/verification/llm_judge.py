"""Agent-as-a-Judge: LLM-based verification of agent task completion.

Inspired by metauto-ai/agent-as-a-judge: after test commands pass, an LLM
reads the transcript + task requirements + verification results and gives a
structured verdict on whether the agent actually met the requirements.

Backends:
  - StubBackend:       deterministic, for tests
  - SubprocessBackend: calls `claude -p` or any CLI
  - GeminiBackend:     calls Google Gemini API (reads GEMINI_API_KEY from env/.env)
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.request import Request, urlopen
from urllib.error import URLError

from overmind.subprocess_utils import split_command
from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult, utc_now

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────


@dataclass(slots=True)
class JudgeVerdict:
    passed: bool
    confidence: float  # 0.0–1.0
    reasoning: str
    concerns: list[str] = field(default_factory=list)
    requirements_met: list[str] = field(default_factory=list)
    requirements_missed: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)


# ── Backend protocol ────────────────────────────────────────────────


class JudgeBackend(Protocol):
    def query(self, prompt: str) -> str: ...


class SubprocessBackend:
    """Call an LLM CLI tool (e.g., `claude -p`) via subprocess."""

    def __init__(self, command: str = "claude -p", timeout: int = 120) -> None:
        self.command = command
        self.timeout = timeout

    def query(self, prompt: str) -> str:
        try:
            result = subprocess.run(
                split_command(self.command),
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            return f"JUDGE_ERROR: {exc}"


class StubBackend:
    """Deterministic backend for testing."""

    def __init__(self, response: str = "VERDICT: PASS\nCONFIDENCE: 0.9\nREASONING: All requirements met.") -> None:
        self.response = response
        self.last_prompt: str | None = None

    def query(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


class GeminiBackend:
    """Call Google Gemini API via REST (no SDK dependency).

    Reads GEMINI_API_KEY from:
      1. Environment variable
      2. .env file in project root (parent of overmind/ package)
    """

    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        timeout: int = 120,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        if self._api_key:
            return self._api_key
        key = os.environ.get("GEMINI_API_KEY", "")
        if key:
            return key
        # Try .env file
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
        return ""

    def available(self) -> bool:
        """True if an API key is resolvable — lets the fallback layer skip a
        keyless Gemini backend without making a doomed call."""
        return bool(self.api_key)

    # Retry transient network failures with bounded exponential backoff.
    _RETRY_ATTEMPTS = 3
    _RETRY_BACKOFF_SECONDS = (1.0, 2.0)

    def query(self, prompt: str) -> str:
        key = self.api_key
        if not key:
            return "JUDGE_ERROR: GEMINI_API_KEY not found in environment or .env file"
        url = self.ENDPOINT.format(model=self.model)
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
        })
        last_error: str = "JUDGE_ERROR: no attempt succeeded"
        for attempt in range(self._RETRY_ATTEMPTS):
            req = Request(url, data=payload.encode("utf-8"), method="POST")
            req.add_header("Content-Type", "application/json")
            # API key in header (not URL query) so it is not leaked via proxy logs,
            # error messages, or persisted verdict.reasoning fields.
            req.add_header("x-goog-api-key", key)
            try:
                with urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "JUDGE_ERROR: empty response")
                return "JUDGE_ERROR: no candidates in response"
            except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
                # Redact the URL in case an exception stringifies the request target —
                # the URL no longer carries the key but rate-limit / 5xx payloads can
                # still echo request metadata back.
                last_error = f"JUDGE_ERROR: {type(exc).__name__}: {str(exc)[:200]}"
                if attempt + 1 < self._RETRY_ATTEMPTS:
                    time.sleep(self._RETRY_BACKOFF_SECONDS[min(attempt, len(self._RETRY_BACKOFF_SECONDS) - 1)])
        return last_error


# ── Judge prompt ────────────────────────────────────────────────────

JUDGE_PROMPT_TEMPLATE = """\
You are an independent verification judge.  Your task is to determine whether
an AI coding agent successfully completed the assigned task.

TASK:
{task_title}

REQUIRED VERIFICATION:
{required_verification}

PROJECT:
{project_name} ({project_path})

VERIFICATION RESULT:
Tests passed: {tests_passed}
Checks completed: {completed_checks}
Checks skipped: {skipped_checks}
Details: {details}

AGENT SESSION TRANSCRIPT (last {transcript_window} lines):
{transcript}

INSTRUCTIONS:
1. Assess whether the task requirements were actually met (not just "tests pass").
2. Look for signs of incomplete work, hacks, or workarounds.
3. Check if the verification evidence actually proves the task was done.

Respond in EXACTLY this format:
VERDICT: PASS or FAIL
CONFIDENCE: 0.0 to 1.0
REASONING: one paragraph explaining your assessment
CONCERNS: comma-separated list (or "none")
MET: comma-separated list of requirements met (or "none")
MISSED: comma-separated list of requirements missed (or "none")
"""


# Chain-of-thought + explicit rubric variant (audit A3 / arXiv:2604.23178:
# CoT is universally helpful; style bias dominates, position bias is negligible,
# so we add reasoning + a fixed rubric but deliberately do NOT do answer/position
# swapping). Opt-in via OVERMIND_JUDGE_COT=1 (or build_judge(use_cot=True)). The
# trailing output block is byte-identical in shape to the default template, so
# the same _parse_verdict logic and the degenerate guard apply unchanged.
JUDGE_PROMPT_TEMPLATE_COT = """\
You are an independent verification judge.  Your task is to determine whether
an AI coding agent successfully completed the assigned task.

TASK:
{task_title}

REQUIRED VERIFICATION:
{required_verification}

PROJECT:
{project_name} ({project_path})

VERIFICATION RESULT:
Tests passed: {tests_passed}
Checks completed: {completed_checks}
Checks skipped: {skipped_checks}
Details: {details}

AGENT SESSION TRANSCRIPT (last {transcript_window} lines):
{transcript}

Think step by step BEFORE deciding. Reason explicitly through this rubric, one
short line per dimension, judging substance only — ignore tone, verbosity, and
formatting (style is not evidence of correctness):
  - RELEVANCE: does the work address the actual task requirements?
  - ACCURACY:  is the implementation correct (no wrong logic, sign/constant/edge errors)?
  - EVIDENCE:  do the verification results genuinely prove the task was done
               (tests passing ≠ task solved; a SKIPPED check is NOT evidence)?
  - LOGIC:     any incomplete work, hacks, workarounds, or fabricated artifacts?

Truth-first rules: if the evidence is missing, skipped, or only partial, you must
NOT return PASS — prefer FAIL or a low confidence. Never reward a confident tone.

After the rubric reasoning, respond with the verdict in EXACTLY this format
(these six lines must appear, each starting at the beginning of its own line):
VERDICT: PASS or FAIL
CONFIDENCE: 0.0 to 1.0
REASONING: one paragraph explaining your assessment
CONCERNS: comma-separated list (or "none")
MET: comma-separated list of requirements met (or "none")
MISSED: comma-separated list of requirements missed (or "none")
"""


def _cot_enabled() -> bool:
    """Whether the CoT + rubric judge prompt is enabled (env OVERMIND_JUDGE_COT)."""
    return os.environ.get("OVERMIND_JUDGE_COT", "").strip().lower() in {"1", "true", "yes", "on"}


# ── LLM Judge ───────────────────────────────────────────────────────


class LLMJudge:
    """LLM-based judge that evaluates whether an agent completed its task."""

    def __init__(
        self,
        backend: JudgeBackend | None = None,
        transcript_window: int = 80,
        use_cot: bool | None = None,
    ) -> None:
        self.backend = backend or StubBackend()
        self.transcript_window = transcript_window
        # CoT + rubric prompt: explicit flag wins; otherwise read env. Off by
        # default so existing judge behavior is unchanged unless opted in.
        self.use_cot = _cot_enabled() if use_cot is None else use_cot

    def judge(
        self,
        task: TaskRecord,
        project: ProjectRecord,
        verification_result: VerificationResult,
        transcript_lines: list[str] | None = None,
    ) -> JudgeVerdict:
        """Submit task context to LLM and parse structured verdict."""
        prompt = self._build_prompt(task, project, verification_result, transcript_lines)
        response = self.backend.query(prompt)
        return self._parse_verdict(response)

    def _build_prompt(
        self,
        task: TaskRecord,
        project: ProjectRecord,
        result: VerificationResult,
        transcript_lines: list[str] | None,
    ) -> str:
        transcript = "\n".join(
            (transcript_lines or ["(no transcript available)"])[-self.transcript_window :]
        )
        template = JUDGE_PROMPT_TEMPLATE_COT if self.use_cot else JUDGE_PROMPT_TEMPLATE
        return template.format(
            task_title=task.title,
            required_verification=", ".join(task.required_verification),
            project_name=project.name,
            project_path=project.root_path,
            tests_passed="yes" if result.success else "no",
            completed_checks=", ".join(result.completed_checks) or "none",
            skipped_checks=", ".join(result.skipped_checks) or "none",
            details="; ".join(result.details[:5]) or "none",
            transcript_window=self.transcript_window,
            transcript=transcript,
        )

    def _parse_verdict(self, response: str) -> JudgeVerdict:
        """Parse structured LLM response into JudgeVerdict.

        Failure semantics (orchestrator.py:718 gates on "judge_error" concern):
        - JUDGE_ERROR response: tag judge_error so the orchestrator falls back
          to test-suite-only verification (documented fail-open-to-tests path).
        - Missing VERDICT field (unparseable response): tag judge_error AND
          judge_parse_error so the orchestrator does not silently auto-approve
          on a garbled LLM response.
        """
        if response.startswith("JUDGE_ERROR:"):
            return JudgeVerdict(
                passed=True,  # orchestrator ignores verdict when judge_error tagged
                confidence=0.0,
                reasoning=f"Judge unavailable: {response}",
                concerns=["judge_error"],
            )

        # Degenerate / master-key guard (arXiv:2507.08794): empty, punctuation-
        # only, or generic-filler replies must abstain, never pass. passed=False
        # is the truth-first stance (defensive even though the orchestrator gates
        # on judge_error); judge_error makes it fall back to tests-only / escalate.
        degenerate = degenerate_response_reason(response)
        if degenerate is not None:
            logger.warning("judge returned degenerate response (%s); abstaining", degenerate)
            return JudgeVerdict(
                passed=False,
                confidence=0.0,
                reasoning=f"Judge response degenerate ({degenerate}): {response[:200]!r}",
                concerns=["judge_error", "judge_degenerate"],
            )

        lines = response.strip().splitlines()
        fields: dict[str, str] = {}
        for line in lines:
            match = re.match(r"^(VERDICT|CONFIDENCE|REASONING|CONCERNS|MET|MISSED):\s*(.+)", line, re.IGNORECASE)
            if match:
                fields[match.group(1).upper()] = match.group(2).strip()

        if "VERDICT" not in fields:
            return JudgeVerdict(
                passed=True,  # orchestrator gates on judge_error; no silent approval
                confidence=0.0,
                reasoning=f"Judge response unparseable: {response[:200]}",
                concerns=["judge_error", "judge_parse_error"],
            )

        passed = fields["VERDICT"].upper() == "PASS"
        try:
            confidence = float(fields.get("CONFIDENCE", "0.5"))
            confidence = max(0.0, min(1.0, confidence))
        except ValueError:
            confidence = 0.5

        reasoning = fields.get("REASONING", "No reasoning provided.")
        concerns = _parse_csv(fields.get("CONCERNS", "none"))
        met = _parse_csv(fields.get("MET", "none"))
        missed = _parse_csv(fields.get("MISSED", "none"))

        return JudgeVerdict(
            passed=passed,
            confidence=confidence,
            reasoning=reasoning,
            concerns=concerns,
            requirements_met=met,
            requirements_missed=missed,
        )


def _parse_csv(value: str) -> list[str]:
    """Parse comma-separated value, filtering 'none' and empty strings."""
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item and item.lower() != "none"]


# ── Degenerate / "master-key" output guard ──────────────────────────
#
# Generalizes the SKIP-as-pass and placeholder-leak lessons to the LLM judge.
# *One Token to Fool LLM-as-a-Judge* (arXiv:2507.08794) shows that empty,
# whitespace-only, punctuation-only ("`:`"), or generic-filler ("Let's solve
# this step by step.") judge outputs can force a false-positive reward in a
# reward model. The structured parser below already requires an explicit
# `VERDICT: PASS` line, but truth-first demands an *explicit, named, logged*
# rejection of these degenerate payloads so they can never be silently treated
# as a low-confidence pass — they must abstain (judge_error) and escalate.

# Leading markup/quoting noise trimmed before the filler-opener check (markdown
# fences, bullets, blockquotes, headers, emphasis, stray quotes/brackets) so a
# reply like ``"Let's …"`` or ``> Sure …`` is still recognized as filler.
_EDGE_NOISE = "`*_>#~ \t\r\n\"'.,:;!?-([{"

# A genuine verdict must contain one of these tokens somewhere.
_VERDICT_TOKEN_RE = re.compile(r"\b(?:VERDICT|PASS|FAIL)\b", re.IGNORECASE)

# Generic "I'm starting to reason" filler that carries no verdict. Anchored at
# the start of the (edge-trimmed) text so it only fires on filler-led replies
# that never reach a verdict, not on a real verdict that opens with reasoning.
_FILLER_OPENER_RE = re.compile(
    r"^(?:ok(?:ay)?|sure|alright|well|hmm+|"
    r"let'?s|let me|i'?ll|i will|i'?m|here(?:'?s)?|"
    r"to (?:begin|start)|first(?:ly)?|"
    r"thinking|step[\s-]by[\s-]step|of course)\b",
    re.IGNORECASE,
)


def degenerate_response_reason(response: str) -> str | None:
    """Return a short reason string if ``response`` is a degenerate / master-key
    judge payload that must NOT be accepted as a verdict, else ``None``.

    Detects: empty / whitespace-only, punctuation-or-markup-only, and
    generic-filler-with-no-verdict-token. Deliberately conservative — a reply
    that contains an explicit PASS/FAIL/VERDICT token is never flagged here
    (that is the parser's job), and an ordinary unparseable reply like
    "I don't understand the format" is left to the parser's missing-VERDICT
    path so it keeps its judge_parse_error tag.
    """
    if response is None:
        return "empty"
    stripped = response.strip()
    if not stripped:
        return "empty_or_whitespace"
    # No letters/digits at all → punctuation, markup fences, or symbols only.
    if not re.search(r"[A-Za-z0-9]", stripped):
        return "punctuation_or_markup_only"
    # No verdict token anywhere AND the reply opens with stock filler → the
    # model never actually decided (the master-key failure mode).
    opener = stripped.lstrip(_EDGE_NOISE)
    if not _VERDICT_TOKEN_RE.search(stripped) and _FILLER_OPENER_RE.match(opener):
        return "filler_without_verdict"
    return None


# ── Quorum judge ────────────────────────────────────────────────────


@dataclass(slots=True)
class QuorumVerdict:
    passed: bool
    confidence: float
    reasoning: str
    backend_verdicts: list[JudgeVerdict] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    # Panel independence (audit A2): nominal judge count vs decorrelated estimate.
    # effective_votes < nominal_votes means same-family judges over-count
    # independence — surfaced so a "9-judge" panel that is really ~2 votes is
    # visible in the bundle, not hidden behind the headline count.
    nominal_votes: int = 0
    effective_votes: float = 0.0
    distinct_families: int = 0


class QuorumJudge:
    """Run a task through multiple LLM backends and require agreement.

    Mitigates single-vendor bias, single-vendor outages, and prompt-specific
    blind spots (a Claude-backed judge missing something a Gemini-backed judge
    catches, and vice versa). Quorum policy: the verdict passes iff
    ≥`quorum_threshold` of available backends agree on PASS. Backends that
    error are excluded from the denominator; if fewer than
    `min_backends` succeed, returns `judge_error` concern so the orchestrator
    falls back to tests-only verification.
    """

    def __init__(
        self,
        judges: list[LLMJudge],
        quorum_threshold: float = 0.5,
        min_backends: int = 1,
        nominal_votes: int | None = None,
        effective_votes: float | None = None,
        distinct_families: int | None = None,
        panel_warning: str | None = None,
    ) -> None:
        if not judges:
            raise ValueError("QuorumJudge requires at least one LLMJudge")
        self.judges = judges
        self.quorum_threshold = quorum_threshold
        self.min_backends = min_backends
        # Panel-independence metadata (filled in by the factory). Defaults assume
        # every judge is independent when not supplied.
        self.nominal_votes = nominal_votes if nominal_votes is not None else len(judges)
        self.effective_votes = effective_votes if effective_votes is not None else float(len(judges))
        self.distinct_families = distinct_families if distinct_families is not None else len(judges)
        self.panel_warning = panel_warning

    def judge(
        self,
        task: TaskRecord,
        project: ProjectRecord,
        verification_result: VerificationResult,
        transcript_lines: list[str] | None = None,
    ) -> QuorumVerdict:
        verdicts: list[JudgeVerdict] = []
        for judge in self.judges:
            try:
                verdicts.append(judge.judge(task, project, verification_result, transcript_lines))
            except Exception as exc:  # noqa: BLE001 — backend-specific failure, isolate
                verdicts.append(JudgeVerdict(
                    passed=True, confidence=0.0,
                    reasoning=f"Judge backend raised: {type(exc).__name__}: {exc}",
                    concerns=["judge_error", "backend_exception"],
                ))

        available = [v for v in verdicts if "judge_error" not in v.concerns]
        if len(available) < self.min_backends:
            return QuorumVerdict(
                passed=True,  # orchestrator gates on judge_error, not passed.
                confidence=0.0,
                reasoning=(
                    f"Quorum unavailable: {len(available)}/{len(self.judges)} "
                    "backends returned usable verdicts."
                ),
                backend_verdicts=verdicts,
                concerns=["judge_error", "quorum_unreachable"],
                nominal_votes=self.nominal_votes,
                effective_votes=self.effective_votes,
                distinct_families=self.distinct_families,
            )

        pass_count = sum(1 for v in available if v.passed)
        pass_ratio = pass_count / len(available)
        passed = pass_ratio >= self.quorum_threshold
        avg_confidence = sum(v.confidence for v in available) / len(available)
        disagreement = len({v.passed for v in available}) > 1
        reasoning = (
            f"Quorum: {pass_count}/{len(available)} backends PASS "
            f"(threshold={self.quorum_threshold:.0%}, avg_conf={avg_confidence:.2f}; "
            f"~{self.effective_votes:.1f} effective independent votes across "
            f"{self.distinct_families} model families)"
        )
        concerns: list[str] = []
        if disagreement:
            concerns.append("quorum_disagreement")
        # Correlated-panel flag (A2): same-family judges over-count independence.
        if self.effective_votes < self.nominal_votes:
            concerns.append("quorum_correlated_panel")
        # Aggregate distinctive concerns from ALL backends (not just available)
        # so a transient backend_exception surfaces even when another backend
        # succeeded and the quorum passed.
        seen = set(concerns)
        for v in verdicts:
            for c in v.concerns:
                if c not in seen:
                    concerns.append(c)
                    seen.add(c)
        return QuorumVerdict(
            passed=passed,
            confidence=avg_confidence,
            reasoning=reasoning,
            backend_verdicts=verdicts,
            concerns=concerns,
            nominal_votes=self.nominal_votes,
            effective_votes=self.effective_votes,
            distinct_families=self.distinct_families,
        )
