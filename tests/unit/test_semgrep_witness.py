"""Tests for SemgrepWitness — third-party security scan as an Overmind witness.

Why this witness exists:
  Overmind's existing rule-driven witnesses (Sentinel pre-push + numerical
  baseline) are excellent for project-specific past-incident bugs but
  thin on the generic OWASP / supply-chain surface. Semgrep ships ~thousands
  of community-maintained rules covering exactly that gap. We invoke it as
  one more witness so a security regression in any portfolio repo blocks
  CERTIFIED.

Verdict mapping:
  - ERROR-severity findings   -> FAIL (blocking)
  - WARNING-severity findings -> PASS but stderr-noted (visible, non-blocking)
  - INFO-severity findings    -> PASS silently
  - semgrep not installed     -> SKIP (graceful degradation; portfolios that
                                 haven't installed semgrep yet shouldn't
                                 silently fail their entire nightly run)
  - subprocess timeout        -> FAIL with explicit timeout detail
  - subprocess crashed        -> FAIL with stderr captured

Tests use mocks for the bulk-and-speed cases; one integration-style test
hits real semgrep against a fixture repo to catch parser/CLI breakage on
upstream version bumps.
"""
from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from overmind.verification.semgrep_witness import SemgrepWitness


# ── helpers ──────────────────────────────────────────────────────────


def _fake_semgrep_output(results: list[dict], errors: list[dict] | None = None) -> str:
    """Minimal semgrep --json shape Overmind cares about."""
    return json.dumps({
        "results": results,
        "errors": errors or [],
        "paths": {"scanned": ["dummy.py"]},
        "version": "1.161.0",
    })


def _finding(severity: str, check_id: str = "test.rule",
             path: str = "src/foo.py", line: int = 1) -> dict:
    return {
        "check_id": check_id,
        "path": path,
        "start": {"line": line, "col": 1},
        "end": {"line": line, "col": 10},
        "extra": {"severity": severity, "message": f"{check_id} fired"},
    }


def _mock_run(stdout: str, returncode: int = 0,
              stderr: str = "") -> MagicMock:
    """Build a CompletedProcess-shaped mock for subprocess.run."""
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


# ── verdict mapping ──────────────────────────────────────────────────


def test_no_findings_is_pass(tmp_path: Path):
    output = _fake_semgrep_output(results=[])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "PASS"
    assert result.exit_code == 0


def test_error_severity_finding_is_fail(tmp_path: Path):
    output = _fake_semgrep_output(results=[
        _finding("ERROR", check_id="python.lang.security.subprocess-shell-true"),
    ])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"
    assert "subprocess-shell-true" in result.stderr or \
           "subprocess-shell-true" in result.stdout


def test_warning_severity_only_is_pass_with_note(tmp_path: Path):
    """WARNING-only findings should not block — they're advisory.
    But the stdout/stderr should mention them so reviewers can see."""
    output = _fake_semgrep_output(results=[
        _finding("WARNING", check_id="python.lang.best-practice.example"),
    ])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "PASS"
    combined = (result.stdout + result.stderr).lower()
    assert "warning" in combined or "1 advisory" in combined


def test_info_severity_only_is_pass_silent(tmp_path: Path):
    output = _fake_semgrep_output(results=[_finding("INFO")])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "PASS"


def test_mixed_error_and_warning_is_fail(tmp_path: Path):
    """Any single ERROR is enough to FAIL even if surrounded by warnings."""
    output = _fake_semgrep_output(results=[
        _finding("WARNING", check_id="advisory.one"),
        _finding("ERROR", check_id="critical.one"),
        _finding("WARNING", check_id="advisory.two"),
    ])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"


# ── graceful-degradation paths ───────────────────────────────────────


def test_semgrep_not_installed_is_skip(tmp_path: Path):
    """Missing-binary should SKIP, not FAIL — portfolios that haven't
    installed semgrep yet shouldn't see entire nightly runs collapse.
    Sentinel UNVERIFIED-vs-PASS lesson applies here."""
    with patch("subprocess.run", side_effect=FileNotFoundError("semgrep")):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "SKIP"
    assert "semgrep" in result.stderr.lower()


def test_timeout_is_fail_with_explicit_note(tmp_path: Path):
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="semgrep", timeout=300),
    ):
        result = SemgrepWitness(timeout=300).run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"
    assert "timed out" in result.stderr.lower() or \
           "timeout" in result.stderr.lower()


def test_unparseable_json_is_fail(tmp_path: Path):
    """If semgrep emits non-JSON garbage we must FAIL, not silently
    treat as no-findings (which would be a false-positive PASS)."""
    with patch("subprocess.run", return_value=_mock_run(
        stdout="not valid json", returncode=1, stderr="semgrep crashed",
    )):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"


def test_nonzero_exit_with_error_findings_is_fail(tmp_path: Path):
    """Semgrep returns exit 1 when findings are present at default
    severity threshold. Don't double-count: this should be a FAIL once,
    based on the ERROR finding, not a FAIL for exit-1 + a separate
    FAIL for ERROR."""
    output = _fake_semgrep_output(results=[_finding("ERROR")])
    with patch("subprocess.run", return_value=_mock_run(
        stdout=output, returncode=1,
    )):
        result = SemgrepWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"


# ── configuration ────────────────────────────────────────────────────


def test_default_configs_include_security_audit(tmp_path: Path):
    """Default config set should include security-audit so we catch
    the OWASP-shaped issues that motivated adopting Semgrep at all."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _mock_run(_fake_semgrep_output(results=[]))

    with patch("subprocess.run", side_effect=fake_run):
        SemgrepWitness().run(cwd=str(tmp_path))

    cmd_str = " ".join(captured.get("cmd", []))
    assert "p/security-audit" in cmd_str


def test_custom_configs_passed_through(tmp_path: Path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _mock_run(_fake_semgrep_output(results=[]))

    with patch("subprocess.run", side_effect=fake_run):
        SemgrepWitness(configs=["p/django", "p/secrets"]).run(cwd=str(tmp_path))

    cmd_str = " ".join(captured.get("cmd", []))
    assert "p/django" in cmd_str
    assert "p/secrets" in cmd_str
    # default should be replaced, not appended-to
    assert "p/security-audit" not in cmd_str


# ── one real-binary integration test ─────────────────────────────────


@pytest.mark.skipif(
    subprocess.run(["semgrep", "--version"], capture_output=True).returncode != 0,
    reason="semgrep CLI not on PATH",
)
def test_real_semgrep_catches_subprocess_shell_true(tmp_path: Path):
    """Live test: write a known-bad file, run real semgrep, expect FAIL
    on the well-known python.lang.security.audit.subprocess-shell-true rule.
    Skipped if semgrep not installed."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    bad = tmp_path / "bad.py"
    # Use sys.argv[1] as the taint source — semgrep does constant
    # propagation, so a literal `user_input = 'foo'` would be folded and
    # the shell-injection rule would not fire on a benign-looking command.
    bad.write_text(
        "import subprocess\n"
        "import sys\n"
        "subprocess.run('rm -rf /' + sys.argv[1], shell=True)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    # Use the realistic default config set; security-audit alone doesn't
    # include the python.lang.security.audit.subprocess-shell-true rule
    # (that one ships in p/python).
    result = SemgrepWitness(
        configs=["p/python", "p/security-audit"],
        timeout=300,
    ).run(cwd=str(tmp_path))
    assert result.verdict == "FAIL", \
        f"expected FAIL on shell=True; got {result.verdict}: {result.stderr}"
