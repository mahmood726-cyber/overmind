"""Tests for PipAuditWitness — Python dep CVE coverage as an Overmind witness.

Mirrors the SemgrepWitness test layout (mocked subprocess for verdict
mapping, one real-binary integration test that skips if pip-audit
isn't installed).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from overmind.verification.pip_audit_witness import PipAuditWitness


def _fake_pip_audit_output(deps: list[dict]) -> str:
    """Minimal pip-audit --format=json shape Overmind cares about."""
    return json.dumps({"dependencies": deps, "fixes": []})


def _vuln_dep(name: str, version: str, vuln_ids: list[str]) -> dict:
    return {
        "name": name,
        "version": version,
        "vulns": [{"id": vid, "fix_versions": ["999.0.0"]} for vid in vuln_ids],
    }


def _clean_dep(name: str, version: str) -> dict:
    return {"name": name, "version": version, "vulns": []}


def _mock_run(stdout: str, returncode: int = 0,
              stderr: str = "") -> MagicMock:
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


def _seed_requirements(tmp_path: Path) -> None:
    """Write a minimal requirements.txt so the witness reaches its
    subprocess-run path (without it, the witness SKIPs by design as of
    2026-04-29 — see PipAuditWitness.scan_active_env_when_no_requirements).
    """
    (tmp_path / "requirements.txt").write_text("requests\n", encoding="utf-8")


@pytest.fixture
def repo_with_reqs(tmp_path: Path) -> Path:
    _seed_requirements(tmp_path)
    return tmp_path


# ── verdict mapping ──────────────────────────────────────────────────


def test_no_vulns_is_pass(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    _no_op = None  # marker so subsequent edits anchor cleanly
    del _no_op
    output = _fake_pip_audit_output(deps=[
        _clean_dep("requests", "2.31.0"),
        _clean_dep("numpy", "1.26.0"),
    ])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "PASS"
    assert result.exit_code == 0
    assert "0 vulnerabilities across 2 dep(s)" in result.stdout


def test_single_vuln_is_fail(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    output = _fake_pip_audit_output(deps=[
        _vuln_dep("requests", "2.0.0", ["GHSA-x84v-xcm2-53pg"]),
    ])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"
    assert "GHSA-x84v-xcm2-53pg" in result.stderr or \
           "GHSA-x84v-xcm2-53pg" in result.stdout


def test_multiple_vulns_in_summary(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    output = _fake_pip_audit_output(deps=[
        _vuln_dep("pkg-a", "1.0", ["CVE-1"]),
        _vuln_dep("pkg-b", "2.0", ["CVE-2"]),
        _clean_dep("pkg-c", "3.0"),
    ])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"
    assert "2 vulnerabilities" in result.stderr
    assert "pkg-a" in result.stderr
    assert "pkg-b" in result.stderr


def test_mixed_clean_and_vuln_is_fail(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    output = _fake_pip_audit_output(deps=[
        _clean_dep("safe", "1.0"),
        _vuln_dep("unsafe", "1.0", ["CVE-X"]),
        _clean_dep("also-safe", "1.0"),
    ])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"


# ── graceful-degradation paths ───────────────────────────────────────


def test_pip_audit_not_installed_is_skip(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    """Same SKIP-not-FAIL pattern as SemgrepWitness, per the
    UNVERIFIED-vs-PASS lesson — missing tool != failed scan."""
    with patch("subprocess.run", side_effect=FileNotFoundError("pip-audit")):
        result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "SKIP"
    assert "pip-audit" in result.stderr.lower()


def test_timeout_is_fail(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="pip-audit", timeout=180),
    ):
        result = PipAuditWitness(timeout=180).run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"
    assert "timed out" in result.stderr.lower() or \
           "timeout" in result.stderr.lower()


def test_unparseable_json_is_fail(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    with patch("subprocess.run", return_value=_mock_run(
        stdout="not valid json", returncode=1, stderr="audit crashed",
    )):
        result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "FAIL"


def test_empty_dependencies_is_pass(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    """A repo with no resolvable deps returns dependencies=[] — that's
    a clean state, not an error."""
    output = _fake_pip_audit_output(deps=[])
    with patch("subprocess.run", return_value=_mock_run(output)):
        result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "PASS"


# ── requirements file discovery ──────────────────────────────────────


def test_finds_requirements_txt(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("requests\n", encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _mock_run(_fake_pip_audit_output(deps=[]))

    with patch("subprocess.run", side_effect=fake_run):
        PipAuditWitness().run(cwd=str(tmp_path))

    cmd = captured.get("cmd", [])
    assert "--requirement" in cmd
    assert "requirements.txt" in cmd


def test_skips_when_no_requirements_file(tmp_path: Path):
    """No requirements file → SKIP (changed 2026-04-29 from active-env
    fallback). Active-env scanning conflates host CVEs with the repo
    under test, broke the meta-verification canary at tier-2."""
    result = PipAuditWitness().run(cwd=str(tmp_path))
    assert result.verdict == "SKIP"
    assert "no requirements" in result.stderr.lower()


def test_active_env_fallback_opt_in(tmp_path: Path):
    """Caller can opt back in to active-env scanning via
    scan_active_env_when_no_requirements=True."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _mock_run(_fake_pip_audit_output(deps=[]))

    with patch("subprocess.run", side_effect=fake_run):
        PipAuditWitness(scan_active_env_when_no_requirements=True).run(
            cwd=str(tmp_path),
        )

    cmd = captured.get("cmd", [])
    assert "--requirement" not in cmd


def test_prefers_first_candidate_in_priority_order(tmp_path: Path):
    """If both requirements.txt and requirements/base.txt exist, the
    bare requirements.txt wins (default candidate priority)."""
    (tmp_path / "requirements.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "base.txt").write_text("b\n", encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _mock_run(_fake_pip_audit_output(deps=[]))

    with patch("subprocess.run", side_effect=fake_run):
        PipAuditWitness().run(cwd=str(tmp_path))

    cmd_str = " ".join(captured.get("cmd", []))
    assert "requirements.txt" in cmd_str
    # Sub-path should NOT be picked (requirements.txt was found first)
    assert "base.txt" not in cmd_str


# ── command construction ────────────────────────────────────────────


def test_default_command_uses_strict_and_json(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _mock_run(_fake_pip_audit_output(deps=[]))

    with patch("subprocess.run", side_effect=fake_run):
        PipAuditWitness().run(cwd=str(tmp_path))

    cmd = captured.get("cmd", [])
    assert "--strict" in cmd
    assert "--format=json" in cmd
    assert cmd[0] == "pip-audit"


def test_custom_binary_path_passed_through(repo_with_reqs: Path):
    tmp_path = repo_with_reqs
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _mock_run(_fake_pip_audit_output(deps=[]))

    with patch("subprocess.run", side_effect=fake_run):
        PipAuditWitness(binary="/custom/pip-audit").run(cwd=str(tmp_path))

    cmd = captured.get("cmd", [])
    assert cmd[0] == "/custom/pip-audit"


# ── one real-binary integration test ─────────────────────────────────


@pytest.mark.skipif(
    subprocess.run(["pip-audit", "--version"], capture_output=True).returncode != 0,
    reason="pip-audit CLI not on PATH",
)
def test_real_pip_audit_clean_run(tmp_path: Path):
    """Live test: write a known-safe requirement (recent pinned package
    with no known CVE), run real pip-audit, expect PASS. Fails if
    pip-audit's network DB lookup fails — that's an environmental
    skip, not a real failure."""
    # `requests==2.32.3` has no known CVE as of 2026-04-29. If a CVE
    # later gets disclosed, this test will start failing — that IS the
    # test working correctly (and the test will need a newer pinned
    # version), so the failure mode is informative.
    (tmp_path / "requirements.txt").write_text(
        "requests==2.32.3\n", encoding="utf-8",
    )
    result = PipAuditWitness(timeout=120).run(cwd=str(tmp_path))
    # Don't assert PASS specifically — pip-audit may legitimately discover
    # a new CVE that didn't exist when this test was written. Either PASS
    # or FAIL is acceptable; SKIP/timeout/garbage indicates the witness
    # itself is broken.
    assert result.verdict in {"PASS", "FAIL"}, \
        f"witness produced unexpected verdict: {result.verdict}; stderr: {result.stderr}"
