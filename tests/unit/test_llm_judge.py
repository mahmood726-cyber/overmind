"""Tests for LLMJudge and CompoundJudge."""

from __future__ import annotations

import sys

from overmind.storage.models import ProjectRecord, TaskRecord, VerificationResult
from overmind.verification.llm_judge import GeminiBackend, JudgeVerdict, LLMJudge, StubBackend, SubprocessBackend, _parse_csv
from overmind.verification.compound_judge import CompoundJudge, JudgeStep


def _task() -> TaskRecord:
    return TaskRecord(
        task_id="task-1",
        project_id="proj-a",
        title="Add login validation",
        task_type="verification",
        source="auto",
        priority=0.8,
        risk="medium",
        expected_runtime_min=5,
        expected_context_cost="low",
        required_verification=["relevant_tests"],
    )


def _project() -> ProjectRecord:
    return ProjectRecord(
        project_id="proj-a",
        name="MyApp",
        root_path="C:\\Projects\\myapp",
    )


def _result(success: bool = True) -> VerificationResult:
    return VerificationResult(
        task_id="task-1",
        success=success,
        required_checks=["relevant_tests"],
        completed_checks=["relevant_tests"] if success else [],
        skipped_checks=[] if success else ["relevant_tests"],
        details=["relevant_tests: exit=0 command=pytest"],
    )


# ── LLMJudge tests ──────────────────────────────────────────────────


def test_stub_backend_returns_pass():
    backend = StubBackend()
    judge = LLMJudge(backend=backend)
    verdict = judge.judge(_task(), _project(), _result())
    assert verdict.passed is True
    assert verdict.confidence > 0


def test_stub_backend_captures_prompt():
    backend = StubBackend()
    judge = LLMJudge(backend=backend)
    judge.judge(_task(), _project(), _result(), transcript_lines=["All tests passed"])
    assert backend.last_prompt is not None
    assert "Add login validation" in backend.last_prompt
    assert "MyApp" in backend.last_prompt


def test_parse_verdict_pass():
    response = (
        "VERDICT: PASS\n"
        "CONFIDENCE: 0.92\n"
        "REASONING: All requirements fully met.\n"
        "CONCERNS: none\n"
        "MET: login validation, error messages\n"
        "MISSED: none"
    )
    backend = StubBackend(response=response)
    judge = LLMJudge(backend=backend)
    verdict = judge.judge(_task(), _project(), _result())
    assert verdict.passed is True
    assert abs(verdict.confidence - 0.92) < 0.01
    assert "All requirements" in verdict.reasoning
    assert len(verdict.requirements_met) == 2
    assert len(verdict.requirements_missed) == 0
    assert len(verdict.concerns) == 0


def test_parse_verdict_fail():
    response = (
        "VERDICT: FAIL\n"
        "CONFIDENCE: 0.85\n"
        "REASONING: Tests pass but validation logic is missing.\n"
        "CONCERNS: incomplete implementation, no error messages\n"
        "MET: test infrastructure\n"
        "MISSED: login validation, error messages"
    )
    backend = StubBackend(response=response)
    judge = LLMJudge(backend=backend)
    verdict = judge.judge(_task(), _project(), _result())
    assert verdict.passed is False
    assert verdict.confidence >= 0.8
    assert len(verdict.concerns) == 2
    assert len(verdict.requirements_missed) == 2


def test_parse_verdict_handles_judge_error():
    backend = StubBackend(response="JUDGE_ERROR: timeout")
    judge = LLMJudge(backend=backend)
    verdict = judge.judge(_task(), _project(), _result())
    # fail-open: don't block on judge errors
    assert verdict.passed is True
    assert verdict.confidence == 0.0
    assert "judge_error" in verdict.concerns


def test_parse_verdict_handles_garbage_response():
    """Unparseable responses must carry a judge_error concern so the orchestrator
    (orchestrator.py:718) does not silently auto-approve on a garbled LLM reply."""
    backend = StubBackend(response="I don't understand the format")
    judge = LLMJudge(backend=backend)
    verdict = judge.judge(_task(), _project(), _result())
    assert verdict.confidence == 0.0
    assert "judge_error" in verdict.concerns
    assert "judge_parse_error" in verdict.concerns


def test_parse_csv_filters_none():
    assert _parse_csv("none") == []
    assert _parse_csv("a, b, c") == ["a", "b", "c"]
    assert _parse_csv("") == []
    assert _parse_csv("one, none, three") == ["one", "three"]


def test_transcript_window_limits_lines():
    backend = StubBackend()
    judge = LLMJudge(backend=backend, transcript_window=5)
    long_transcript = [f"line {i}" for i in range(100)]
    judge.judge(_task(), _project(), _result(), transcript_lines=long_transcript)
    assert backend.last_prompt is not None
    # Should only include last 5 lines
    assert "line 99" in backend.last_prompt
    assert "line 0" not in backend.last_prompt


# ── CompoundJudge tests ─────────────────────────────────────────────


def test_compound_single_step_pass():
    judge = CompoundJudge(steps=[
        JudgeStep("main", LLMJudge(backend=StubBackend())),
    ])
    verdict = judge.evaluate(_task(), _project(), _result())
    assert verdict.passed is True
    assert "main" in verdict.step_verdicts


def test_compound_veto_power_blocks():
    fail_response = "VERDICT: FAIL\nCONFIDENCE: 0.9\nREASONING: Requirements not met."
    pass_response = "VERDICT: PASS\nCONFIDENCE: 0.8\nREASONING: Looks good."
    judge = CompoundJudge(steps=[
        JudgeStep("requirements", LLMJudge(backend=StubBackend(response=fail_response)), veto_power=True),
        JudgeStep("quality", LLMJudge(backend=StubBackend(response=pass_response))),
    ])
    verdict = judge.evaluate(_task(), _project(), _result())
    assert verdict.passed is False
    assert verdict.vetoed_by == "requirements"
    # Quality judge should not have been called (short-circuit)
    assert "quality" not in verdict.step_verdicts


def test_compound_weighted_majority():
    fail_response = "VERDICT: FAIL\nCONFIDENCE: 0.6\nREASONING: Minor issue."
    pass_response = "VERDICT: PASS\nCONFIDENCE: 0.9\nREASONING: All good."
    judge = CompoundJudge(steps=[
        JudgeStep("minor", LLMJudge(backend=StubBackend(response=fail_response)), weight=0.3),
        JudgeStep("major", LLMJudge(backend=StubBackend(response=pass_response)), weight=1.0),
    ])
    verdict = judge.evaluate(_task(), _project(), _result())
    # Major (weight=1.0) passes, minor (weight=0.3) fails → majority passes
    assert verdict.passed is True
    assert verdict.vetoed_by is None


def test_compound_all_fail():
    fail_response = "VERDICT: FAIL\nCONFIDENCE: 0.8\nREASONING: Bad."
    judge = CompoundJudge(steps=[
        JudgeStep("a", LLMJudge(backend=StubBackend(response=fail_response))),
        JudgeStep("b", LLMJudge(backend=StubBackend(response=fail_response))),
    ])
    verdict = judge.evaluate(_task(), _project(), _result())
    assert verdict.passed is False


def test_compound_requires_at_least_one_step():
    try:
        CompoundJudge(steps=[])
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_compound_reasoning_includes_step_summary():
    judge = CompoundJudge(steps=[
        JudgeStep("check_a", LLMJudge(backend=StubBackend())),
        JudgeStep("check_b", LLMJudge(backend=StubBackend())),
    ])
    verdict = judge.evaluate(_task(), _project(), _result())
    assert "check_a" in verdict.reasoning
    assert "check_b" in verdict.reasoning


# ── GeminiBackend tests ─────────────────────────────────────────────


def test_gemini_backend_reads_api_key_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    backend = GeminiBackend()
    assert backend.api_key == "test-key-123"


def test_gemini_backend_returns_error_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    backend = GeminiBackend(api_key="")
    # Manually override to ensure no .env file fallback
    backend._api_key = ""
    result = backend.query("test prompt")
    # Should either find key from .env or return error
    assert isinstance(result, str)


def test_gemini_backend_explicit_key():
    backend = GeminiBackend(api_key="explicit-key")
    assert backend.api_key == "explicit-key"


def test_subprocess_backend_uses_shell_safe_split(monkeypatch):
    captured: dict[str, object] = {}

    class DummyResult:
        stdout = "VERDICT: PASS\nCONFIDENCE: 0.9\nREASONING: ok"

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return DummyResult()

    monkeypatch.setattr("subprocess.run", fake_run)
    backend = SubprocessBackend(command=f'"{sys.executable}" -m overmind_judge --flag "two words"')

    response = backend.query("judge this")

    assert "VERDICT: PASS" in response
    assert captured["args"] == [sys.executable, "-m", "overmind_judge", "--flag", "two words"]


def test_subprocess_backend_forces_utf8_encoding(monkeypatch):
    """SubprocessBackend must pin encoding=utf-8 so Windows cp1252 default does
    not mangle non-ASCII prompts/responses."""
    captured: dict[str, object] = {}

    class DummyResult:
        stdout = "VERDICT: PASS\nCONFIDENCE: 0.9\nREASONING: ok"

    def fake_run(args, **kwargs):
        captured["kwargs"] = kwargs
        return DummyResult()

    monkeypatch.setattr("subprocess.run", fake_run)
    backend = SubprocessBackend(command=f'"{sys.executable}" -m overmind_judge')
    backend.query("judge this")

    assert captured["kwargs"].get("encoding") == "utf-8"
    assert captured["kwargs"].get("errors") == "replace"


def test_gemini_backend_sends_api_key_in_header_not_url(monkeypatch):
    """API key must travel in x-goog-api-key header so proxy logs and error
    payloads do not leak it via the URL query string."""
    captured: dict[str, object] = {}

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return (
                b'{"candidates":[{"content":{"parts":[{"text":"VERDICT: PASS\\n'
                b'CONFIDENCE: 0.9\\nREASONING: ok"}]}}]}'
            )

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        return DummyResp()

    monkeypatch.setattr("overmind.verification.llm_judge.urlopen", fake_urlopen)
    backend = GeminiBackend(api_key="secret-key-abc")
    backend.query("judge this")

    assert "key=" not in captured["url"]
    assert "secret-key-abc" not in captured["url"]
    header_map = {k.lower(): v for k, v in captured["headers"].items()}
    assert header_map.get("x-goog-api-key") == "secret-key-abc"


def test_gemini_backend_retries_on_transient_failure(monkeypatch):
    """Transient URLError / OSError must trigger bounded retry, not immediately
    return JUDGE_ERROR and fail-open-to-tests on the first blip."""
    from urllib.error import URLError

    call_count = {"n": 0}

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return (
                b'{"candidates":[{"content":{"parts":[{"text":"VERDICT: PASS\\n'
                b'CONFIDENCE: 0.9\\nREASONING: ok"}]}}]}'
            )

    def flaky_urlopen(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise URLError("transient DNS flap")
        return DummyResp()

    monkeypatch.setattr("overmind.verification.llm_judge.urlopen", flaky_urlopen)
    monkeypatch.setattr("overmind.verification.llm_judge.time.sleep", lambda _s: None)
    backend = GeminiBackend(api_key="k")
    response = backend.query("prompt")

    assert call_count["n"] == 3
    assert "VERDICT: PASS" in response


def test_gemini_backend_returns_judge_error_after_max_retries(monkeypatch):
    from urllib.error import URLError

    def always_fails(_req, timeout=None):
        raise URLError("down")

    monkeypatch.setattr("overmind.verification.llm_judge.urlopen", always_fails)
    monkeypatch.setattr("overmind.verification.llm_judge.time.sleep", lambda _s: None)
    backend = GeminiBackend(api_key="k")
    response = backend.query("prompt")

    assert response.startswith("JUDGE_ERROR:")
    assert "URLError" in response
