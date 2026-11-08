from __future__ import annotations

import sys

import subprocess

import pytest

from overmind.storage.models import ProjectRecord, TaskRecord
from overmind.verification.verifier import VerificationEngine


def test_verifier_reuses_identical_test_command_for_multiple_checks(tmp_path):
    counter_file = tmp_path / "count.txt"
    script_path = tmp_path / "count_runs.py"
    script_path.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "path = Path(sys.argv[1])\n"
        "count = int(path.read_text() if path.exists() else '0') + 1\n"
        "path.write_text(str(count))\n"
        "print('tests passed')\n",
        encoding="utf-8",
    )

    command = f'"{sys.executable}" "{script_path}" "{counter_file}"'
    project = ProjectRecord(
        project_id="math-project",
        name="Math Project",
        root_path=str(tmp_path),
        project_type="python_tool",
        stack=["python"],
        test_commands=[command],
    )
    task = TaskRecord(
        task_id="task-verify",
        project_id=project.project_id,
        title="Verify math project",
        task_type="verification",
        source="test",
        priority=0.9,
        risk="high",
        expected_runtime_min=5,
        expected_context_cost="medium",
        required_verification=[
            "relevant_tests",
            "numeric_regression",
            "deterministic_fixture_tests",
            "edge_case_tests",
        ],
        trace_id="trace-verify",
    )

    artifacts_dir = tmp_path / "artifacts"
    result = VerificationEngine(artifacts_dir).run(task, project)

    assert result.success is True
    assert result.trace_id == "trace-verify"
    assert counter_file.read_text() == "1"
    assert set(result.completed_checks) == {
        "relevant_tests",
        "numeric_regression",
        "deterministic_fixture_tests",
        "edge_case_tests",
    }
    assert any("reused verification evidence" in detail for detail in result.details)
    assert (artifacts_dir / "trace-verify_task-verify_relevant_tests_1.log").exists()


def test_verifier_routes_numeric_checks_to_distinct_validation_command_and_reuses_per_command(tmp_path):
    smoke_counter = tmp_path / "smoke_count.txt"
    broad_counter = tmp_path / "broad_count.txt"
    numeric_counter = tmp_path / "numeric_count.txt"

    tests_dir = tmp_path / "tests"
    scripts_dir = tmp_path / "scripts"
    tests_dir.mkdir()
    scripts_dir.mkdir()

    def write_counter_script(path, label):
        path.write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "counter = Path(sys.argv[1])\n"
            "count = int(counter.read_text() if counter.exists() else '0') + 1\n"
            "counter.write_text(str(count))\n"
            f"print('{label} passed')\n",
            encoding="utf-8",
        )

    smoke_script = tests_dir / "test_smoke.py"
    broad_script = scripts_dir / "module_functional_test.py"
    numeric_script = scripts_dir / "prognostic_r_validation.py"

    write_counter_script(smoke_script, "smoke")
    write_counter_script(broad_script, "broad")
    write_counter_script(numeric_script, "numeric")

    smoke_command = f'"{sys.executable}" "{smoke_script}" "{smoke_counter}"'
    broad_command = f'"{sys.executable}" "{broad_script}" "{broad_counter}"'
    numeric_command = f'"{sys.executable}" "{numeric_script}" "{numeric_counter}"'

    project = ProjectRecord(
        project_id="prognostic-meta",
        name="prognostic-meta",
        root_path=str(tmp_path),
        project_type="browser_app",
        stack=["html", "javascript"],
        test_commands=[smoke_command, broad_command, numeric_command],
    )
    task = TaskRecord(
        task_id="task-prognostic-verify",
        project_id=project.project_id,
        title="Verify prognostic-meta",
        task_type="verification",
        source="test",
        priority=0.9,
        risk="high",
        expected_runtime_min=5,
        expected_context_cost="medium",
        required_verification=[
            "relevant_tests",
            "numeric_regression",
            "regression_checks",
        ],
    )

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is True
    assert smoke_counter.read_text() == "1"
    assert broad_counter.read_text() == "1"
    assert numeric_counter.read_text() == "1"
    assert set(result.completed_checks) == {
        "relevant_tests",
        "numeric_regression",
        "regression_checks",
    }
    assert any(
        "reused verification evidence from relevant_tests command=" in detail
        for detail in result.details
    )
    assert any(
        "reused verification evidence from numeric_regression command=" in detail
        for detail in result.details
    )


def test_verifier_blocks_disallowed_command_prefix(tmp_path):
    project = ProjectRecord(
        project_id="blocked-project",
        name="Blocked Project",
        root_path=str(tmp_path),
        project_type="python_tool",
        stack=["python"],
        test_commands=["git status"],
    )
    task = TaskRecord(
        task_id="task-blocked",
        project_id=project.project_id,
        title="Verify blocked project",
        task_type="verification",
        source="test",
        priority=0.9,
        risk="medium",
        expected_runtime_min=1,
        expected_context_cost="low",
        required_verification=["relevant_tests"],
    )

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is False
    assert any("Blocked: command prefix not allowlisted" in detail for detail in result.details)


def test_verifier_runs_unquoted_absolute_python_command(tmp_path):
    script_path = tmp_path / "ok.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")

    project = ProjectRecord(
        project_id="absolute-python-project",
        name="Absolute Python Project",
        root_path=str(tmp_path),
        project_type="python_tool",
        stack=["python"],
        test_commands=[f"{sys.executable} {script_path}"],
    )
    task = TaskRecord(
        task_id="task-absolute-python",
        project_id=project.project_id,
        title="Verify absolute python path command",
        task_type="verification",
        source="test",
        priority=0.9,
        risk="medium",
        expected_runtime_min=1,
        expected_context_cost="low",
        required_verification=["relevant_tests"],
    )

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is True
    assert "relevant_tests" in result.completed_checks


def test_verifier_blocks_shell_wrapper_chaining(tmp_path):
    script_path = tmp_path / "safe.cmd"
    script_path.write_text("@echo off\r\necho ok\r\n", encoding="utf-8")

    project = ProjectRecord(
        project_id="wrapper-block-project",
        name="Wrapper Block Project",
        root_path=str(tmp_path),
        project_type="python_tool",
        stack=["python"],
        test_commands=[f'cmd /c "{script_path}" && del /s /q C:\\*'],
    )
    task = TaskRecord(
        task_id="task-wrapper-block",
        project_id=project.project_id,
        title="Reject chained cmd wrapper",
        task_type="verification",
        source="test",
        priority=0.9,
        risk="medium",
        expected_runtime_min=1,
        expected_context_cost="low",
        required_verification=["relevant_tests"],
    )

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is False
    assert any("unsafe shell control operator" in detail for detail in result.details)


def test_verifier_decodes_utf8_subprocess_output_on_windows(tmp_path):
    script_path = tmp_path / "utf8_probe.py"
    script_path.write_text(
        "import sys\n"
        "sys.stdout.buffer.write(b'\\xc5\\x8f verification ok\\n')\n",
        encoding="utf-8",
    )

    project = ProjectRecord(
        project_id="utf8-project",
        name="UTF8 Project",
        root_path=str(tmp_path),
        project_type="python_tool",
        stack=["python"],
        test_commands=[f'"{sys.executable}" "{script_path}"'],
    )
    task = TaskRecord(
        task_id="task-utf8-output",
        project_id=project.project_id,
        title="Verify UTF-8 subprocess output",
        task_type="verification",
        source="test",
        priority=0.9,
        risk="medium",
        expected_runtime_min=1,
        expected_context_cost="low",
        required_verification=["relevant_tests"],
    )

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is True
    assert "relevant_tests" in result.completed_checks


def test_verifier_scrubs_env_to_allowlist(tmp_path, monkeypatch):
    """LD_PRELOAD, PYTHONSTARTUP, GIT_DIR and other inheritance vectors must not
    pass through to the verification subprocess."""
    from overmind.verification import verifier as verifier_mod

    monkeypatch.setenv("LD_PRELOAD", "/tmp/evil.so")
    monkeypatch.setenv("PYTHONSTARTUP", "/tmp/evil.py")
    monkeypatch.setenv("GIT_DIR", "/tmp/evil-git")
    monkeypatch.setenv("PATH", "/usr/bin")

    scrubbed = verifier_mod._safe_env()

    assert "LD_PRELOAD" not in scrubbed
    assert "PYTHONSTARTUP" not in scrubbed
    assert "GIT_DIR" not in scrubbed
    assert "PATH" in scrubbed


def test_verifier_uses_new_process_group_on_windows(tmp_path, monkeypatch):
    """Popen must be invoked with CREATE_NEW_PROCESS_GROUP on Windows so the
    timeout handler can kill pytest-xdist workers via taskkill /T."""
    import subprocess as _subprocess
    import sys as _sys

    if _sys.platform != "win32":
        import pytest
        pytest.skip("Windows-specific process group behavior")

    captured: dict[str, object] = {}

    class DummyProc:
        pid = 12345
        returncode = 0

        def communicate(self, timeout=None):
            return ("ok", "")

    def fake_popen(args, **kwargs):
        captured["kwargs"] = kwargs
        return DummyProc()

    monkeypatch.setattr(_subprocess, "Popen", fake_popen)

    from overmind.verification.verifier import VerificationEngine
    engine = VerificationEngine(tmp_path / "artifacts")
    engine._run_command(f'"{_sys.executable}" -c "print(1)"', str(tmp_path))

    flags = captured["kwargs"].get("creationflags", 0)
    assert flags & _subprocess.CREATE_NEW_PROCESS_GROUP

    env = captured["kwargs"].get("env")
    assert env is not None
    assert "LD_PRELOAD" not in env


def _synthetic_verification_task(project, checks):
    return TaskRecord(
        task_id="synthetic-verification",
        project_id=project.project_id,
        title="Verify synthetic fixture",
        task_type="verification",
        source="test",
        priority=0.9,
        risk="medium",
        expected_runtime_min=1,
        expected_context_cost="low",
        required_verification=checks,
    )


def test_verifier_refuses_success_when_no_checks_are_required(tmp_path):
    project = ProjectRecord(
        project_id="no-plan",
        name="No plan",
        root_path=str(tmp_path),
    )
    task = _synthetic_verification_task(project, [])

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is False
    assert result.completed_checks == []
    assert any("no verification command executed" in detail for detail in result.details)


def test_verifier_refuses_success_when_only_optional_build_is_unavailable(tmp_path):
    project = ProjectRecord(
        project_id="missing-optional",
        name="No build command",
        root_path=str(tmp_path),
    )
    task = _synthetic_verification_task(project, ["build_or_direct_evidence"])

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is False
    assert result.completed_checks == []
    assert "build_or_direct_evidence: no command discovered" in result.skipped_checks
    assert any("no verification command executed" in detail for detail in result.details)


def test_verifier_allows_optional_build_skip_if_real_test_executes(tmp_path):
    script = tmp_path / "test_synthetic_proof.py"
    script.write_text("print('synthetic test passed')\n", encoding="utf-8")
    project = ProjectRecord(
        project_id="optional-and-test",
        name="Test-backed",
        root_path=str(tmp_path),
        test_commands=[f'"{sys.executable}" "{script}"'],
    )
    task = _synthetic_verification_task(
        project, ["build_or_direct_evidence", "relevant_tests"]
    )

    result = VerificationEngine(tmp_path / "artifacts").run(task, project)

    assert result.success is True
    assert result.completed_checks == ["relevant_tests"]
    assert "build_or_direct_evidence: no command discovered" in result.skipped_checks
    assert any("relevant_tests: exit=0" in detail for detail in result.details)


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [("", ""), ("  \n", "\t")],
)
def test_verifier_refuses_silent_success_and_cached_reuse(tmp_path, monkeypatch, stdout, stderr):
    """A zero exit without observed output must not satisfy either reused check."""
    project = ProjectRecord(
        project_id="synthetic-silent",
        name="Synthetic silent check",
        root_path=str(tmp_path),
        test_commands=["python -m pytest -q"],
    )
    task = _synthetic_verification_task(
        project, ["relevant_tests", "numeric_regression"]
    )
    engine = VerificationEngine(tmp_path / "artifacts")
    calls = []

    def silent_command(command, cwd):
        calls.append((command, cwd))
        return 0, stdout, stderr

    monkeypatch.setattr(engine, "_run_command", silent_command)
    result = engine.run(task, project)

    assert result.success is False
    assert result.completed_checks == []
    assert len(calls) == 1  # same command is cached, not rerun
    assert any("unverified; command exited 0 with empty stdout/stderr" in detail
               for detail in result.details)
    assert any("reused verification evidence" in detail for detail in result.details)
    assert len(list((tmp_path / "artifacts").glob("*.log"))) == 1


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [("synthetic test passed", ""), ("", "synthetic test passed")],
)
def test_verifier_accepts_observable_zero_exit_control(tmp_path, monkeypatch, stdout, stderr):
    """Non-empty stdout OR stderr remains valid command evidence."""
    project = ProjectRecord(
        project_id="synthetic-visible",
        name="Synthetic observable check",
        root_path=str(tmp_path),
        test_commands=["python -m pytest -q"],
    )
    task = _synthetic_verification_task(project, ["relevant_tests"])
    engine = VerificationEngine(tmp_path / "artifacts")
    monkeypatch.setattr(
        engine, "_run_command", lambda command, cwd: (0, stdout, stderr)
    )
    result = engine.run(task, project)

    assert result.success is True
    assert result.completed_checks == ["relevant_tests"]
    assert not any("unverified" in detail for detail in result.details)


@pytest.mark.parametrize(
    "command", ["node -c app.js", "node --check app.js", "node -c src/app.js"]
)
def test_verifier_accepts_quiet_node_syntax_check(tmp_path, monkeypatch, command):
    """`node -c`/`--check` legitimately exits 0 with no output (verified with a
    real node run); project_scanner emits it as the html+app.js build command."""
    project = ProjectRecord(
        project_id="synthetic-node", name="Synthetic node syntax check",
        root_path=str(tmp_path), build_commands=[command],
    )
    task = _synthetic_verification_task(project, ["build_or_direct_evidence"])
    engine = VerificationEngine(tmp_path / "artifacts")
    monkeypatch.setattr(engine, "_run_command", lambda c, cwd: (0, "", ""))
    result = engine.run(task, project)

    assert result.success is True
    assert result.completed_checks == ["build_or_direct_evidence"]
    assert not any("unverified" in detail for detail in result.details)


@pytest.mark.parametrize(
    "command",
    [
        "node app.js",
        "node -c app.js && echo done",
        "node -c app.js; rm -rf x",
        "node -c",
        "node -e 1",
        "node -C bad.js",
        "node -c -",
        "node -c --no-warnings",
        "node -c app.txt",
        "python -c pass",
        "mybuild --check app.js",
    ],
)
def test_verifier_still_refuses_other_silent_commands(tmp_path, monkeypatch, command):
    """The exemption is narrow: any other silent zero-exit stays UNVERIFIED."""
    project = ProjectRecord(
        project_id="synthetic-quiet", name="Synthetic quiet command",
        root_path=str(tmp_path), build_commands=[command],
    )
    task = _synthetic_verification_task(project, ["build_or_direct_evidence"])
    engine = VerificationEngine(tmp_path / "artifacts")
    monkeypatch.setattr(engine, "_run_command", lambda c, cwd: (0, "", ""))
    result = engine.run(task, project)

    assert result.success is False
    assert any("unverified; command exited 0 with empty stdout/stderr" in d
               for d in result.details)


def _synthetic_artifact_fixture(tmp_path):
    project = ProjectRecord(
        project_id="synthetic-logs", name="Synthetic logging", root_path=str(tmp_path)
    )
    return project, _synthetic_verification_task(project, ["relevant_tests"])


def test_verifier_artifact_log_paths_stay_inside_directory_for_unsafe_ids(tmp_path):
    """A synthetic trace/check containing separators must not escape or crash logging."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.trace_id = "nested/trace"
    task.required_verification = ["check/with/slash"]
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"check/with/slash": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic command passed", "")
    result = engine.run(task, project)
    assert result.success is True
    logs = list(engine.artifacts_dir.glob("*.log"))
    assert len(logs) == 1
    assert logs[0].parent == engine.artifacts_dir
    assert "synthetic command passed" in logs[0].read_text(encoding="utf-8")


def test_verifier_artifact_log_names_are_portable_and_bounded(tmp_path):
    """Long and non-portable trace identifiers need a short ASCII log basename."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.trace_id = "x" * 280 + ":β"
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic command passed", "")
    result = engine.run(task, project)
    assert result.success is True
    logs = list(engine.artifacts_dir.glob("*.log"))
    assert len(logs) == 1
    assert len(logs[0].name.encode("utf-8")) < 200
    assert logs[0].name.isascii()


def test_verifier_unpersisted_command_log_cannot_yield_completion(tmp_path, monkeypatch):
    """Zero exit with output is unverified when the evidence log cannot be written."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic command passed", "")
    from pathlib import Path

    def failed_write(self, *args, **kwargs):
        raise OSError("synthetic read-only evidence directory")

    monkeypatch.setattr(Path, "open", failed_write)
    result = engine.run(task, project)
    assert result.success is False
    assert result.completed_checks == []
    assert any("unverified" in detail and "log" in detail for detail in result.details)


def test_verifier_underscore_components_cannot_alias_evidence_log_names(tmp_path):
    """Different task/trace tuples must never reuse the same saved evidence path."""
    engine = VerificationEngine(tmp_path / "artifacts")
    left = engine._artifact_log_path("nightly_one", "worker", "relevant_tests", 1)
    right = engine._artifact_log_path("nightly", "one_worker", "relevant_tests", 1)

    assert left != right
    assert left.parent == right.parent == engine.artifacts_dir


def test_verifier_log_names_remain_unique_on_case_insensitive_windows(tmp_path):
    """Windows cannot distinguish case-only filename differences."""
    engine = VerificationEngine(tmp_path / "artifacts")
    left = engine._artifact_log_path("Nightly", "worker", "relevant_tests", 1)
    right = engine._artifact_log_path("nightly", "worker", "relevant_tests", 1)

    assert left.name.casefold() != right.name.casefold()


def test_verifier_different_tasks_preserve_both_command_logs(tmp_path):
    """A later synthetic task must not overwrite an earlier task's evidence."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.trace_id = "nightly_one"
    task.task_id = "worker"
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}

    engine._run_command = lambda *_: (0, "first task passed", "")
    first = engine.run(task, project)
    task.trace_id = "nightly"
    task.task_id = "one_worker"
    engine._run_command = lambda *_: (0, "second task passed", "")
    second = engine.run(task, project)

    assert first.success is True and second.success is True
    logs = list(engine.artifacts_dir.glob("*.log"))
    assert len(logs) == 2
    evidence = [p.read_text(encoding="utf-8") for p in logs]
    assert sum("first task passed" in log for log in evidence) == 1
    assert sum("second task passed" in log for log in evidence) == 1


def test_verifier_repeated_same_task_preserves_previous_run_log(tmp_path):
    """Reverification cannot replace evidence from an earlier run of the same task."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}

    engine._run_command = lambda *_: (0, "first run passed", "")
    first = engine.run(task, project)
    engine._run_command = lambda *_: (1, "", "second run failed")
    second = engine.run(task, project)

    original = engine._artifact_log_path(task.task_id, task.task_id, "relevant_tests", 1)
    second_path = original.with_name(f"{original.stem}.1{original.suffix}")
    assert first.success is True
    assert second.success is False
    assert original.read_text(encoding="utf-8").count("first run passed") == 1
    assert "second run failed" not in original.read_text(encoding="utf-8")
    assert "second run failed" in second_path.read_text(encoding="utf-8")
    assert any(f"log={original.name}" in d for d in first.details)
    assert any(f"log={second_path.name}" in d for d in second.details)


def test_verifier_concurrent_log_creation_preserves_both_outputs(tmp_path):
    """O_EXCL assigns unique log paths even when two writers start together."""
    from concurrent.futures import ThreadPoolExecutor

    engine = VerificationEngine(tmp_path / "artifacts")
    base = engine._artifact_log_path("synthetic", "task", "relevant_tests", 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(pool.map(
            lambda payload: engine._write_artifact_log(base, payload),
            ("first transcript", "second transcript"),
        ))

    assert paths[0] != paths[1]
    assert {p.read_text(encoding="utf-8") for p in paths} == {
        "first transcript", "second transcript"
    }
    assert all(p.parent == engine.artifacts_dir for p in paths)


def test_verifier_preexisting_log_symlink_cannot_overwrite_target(tmp_path):
    """Preexisting symlink paths are occupied, never followed for writing."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic pass", "")

    target = tmp_path / "do-not-modify.txt"
    target.write_text("outside unchanged", encoding="utf-8")
    original = engine._artifact_log_path(task.task_id, task.task_id, "relevant_tests", 1)
    try:
        original.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlink creation unavailable on this platform: {exc}")

    result = engine.run(task, project)

    assert result.success is True
    assert target.read_text(encoding="utf-8") == "outside unchanged"
    assert original.is_symlink()
    new_log = original.with_name(f"{original.stem}.1{original.suffix}")
    assert "synthetic pass" in new_log.read_text(encoding="utf-8")


def test_verifier_exhausted_log_names_never_claim_completion(tmp_path, monkeypatch):
    """If all candidate names are occupied, verification stays UNVERIFIED."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic pass", "")
    from pathlib import Path

    attempts = []
    def occupied(self, *args, **kwargs):
        attempts.append(self.name)
        raise FileExistsError("synthetic exclusive-create collision")

    monkeypatch.setattr(Path, "open", occupied)
    result = engine.run(task, project)

    assert result.success is False
    assert result.completed_checks == []
    assert len(attempts) == 1000
    assert len(set(attempts)) == 1000
    assert any("unverified" in d and "log" in d for d in result.details)


def test_verifier_rejects_omitted_required_plan_check_after_successful_command(tmp_path):
    """A partial planner must not certify the full list of required checks."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.required_verification = ["relevant_tests", "numeric_regression"]
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic check passed", "")

    result = engine.run(task, project)

    assert result.success is False
    assert result.completed_checks == ["relevant_tests"]
    assert any(
        "unverified" in detail and "numeric_regression" in detail
        for detail in result.details
    )


def test_verifier_rejects_omitted_optional_plan_check(tmp_path):
    """An optional check can be skipped, but may not silently disappear."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.required_verification = ["build_or_direct_evidence", "relevant_tests"]
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic check passed", "")

    result = engine.run(task, project)

    assert result.success is False
    assert "relevant_tests" in result.completed_checks
    assert any(
        "unverified" in detail and "build_or_direct_evidence" in detail
        for detail in result.details
    )


def test_verifier_rejects_spurious_planner_command_with_no_required_checks(tmp_path):
    """A planner-injected command cannot convert an empty contract to PASS."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.required_verification = []
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["dummy synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic check passed", "")

    result = engine.run(task, project)

    assert result.success is False
    assert result.required_checks == []
    assert any("unverified" in detail and "required" in detail for detail in result.details)


def test_verifier_accepts_complete_synthetic_plan_control(tmp_path):
    """The gap detector must not reject a complete, evidenced check plan."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.required_verification = ["relevant_tests", "numeric_regression"]
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {
        "relevant_tests": ["dummy synthetic command"],
        "numeric_regression": ["dummy synthetic command"],
    }
    engine._run_command = lambda *_: (0, "synthetic check passed", "")

    result = engine.run(task, project)

    assert result.success is True
    assert result.completed_checks == ["relevant_tests", "numeric_regression"]


def test_verifier_rejects_unrequired_planner_check_even_if_required_passes(tmp_path):
    """An extra planner check is not a declared proof obligation or authorized command."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {
        "relevant_tests": ["synthetic required command"],
        "numeric_regression": ["synthetic undeclared command"],
    }
    executed = []

    def execute(command, cwd):
        executed.append(command)
        return 0, "synthetic pass", ""

    engine._run_command = execute
    result = engine.run(task, project)

    assert result.success is False
    assert result.completed_checks == ["relevant_tests"]
    assert executed == ["synthetic required command"]
    assert any(
        "numeric_regression" in detail and "unverified" in detail
        for detail in result.details
    )


def test_verifier_optional_only_plan_cannot_pass_from_unrequired_check(tmp_path):
    """An injected command must not make an omitted optional build appear verified."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    task.required_verification = ["build_or_direct_evidence"]
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {
        "build_or_direct_evidence": [],
        "relevant_tests": ["synthetic undeclared command"],
    }
    executed = []
    engine._run_command = lambda command, cwd: (
        executed.append(command) or 0, "synthetic pass", ""
    )

    result = engine.run(task, project)

    assert result.success is False
    assert result.completed_checks == []
    assert executed == []
    assert any("unverified" in detail for detail in result.details)


def test_verifier_exact_declared_plan_still_succeeds_without_extra_execution(tmp_path):
    """A complete declared synthetic proof remains valid, with no extra commands."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {
        "relevant_tests": ["synthetic declared command"],
    }
    executed = []
    engine._run_command = lambda command, cwd: (
        executed.append(command) or 0, "synthetic passed", ""
    )

    result = engine.run(task, project)

    assert result.success is True
    assert result.completed_checks == ["relevant_tests"]
    assert executed == ["synthetic declared command"]


def test_verifier_fails_closed_when_requirements_change_while_command_runs(tmp_path):
    """A check run under an obsolete proof contract cannot certify the new one."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["synthetic command"]}

    def change_contract(command, cwd):
        task.required_verification.append("numeric_regression")
        return 0, "synthetic pass", ""

    engine._run_command = change_contract
    result = engine.run(task, project)

    assert result.success is False
    assert result.required_checks == ["relevant_tests"]
    assert result.completed_checks == ["relevant_tests"]
    assert task.required_verification == ["relevant_tests", "numeric_regression"]
    assert any("unverified" in detail and "contract changed" in detail
               for detail in result.details)


def test_verifier_refuses_execution_when_planner_mutates_requirements(tmp_path):
    """An altered task contract during planning must not authorize commands."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")

    def mutate_during_plan(task, project):
        task.required_verification.append("numeric_regression")
        return {"relevant_tests": ["synthetic command"]}

    engine.planner.plan = mutate_during_plan
    executed = []
    engine._run_command = lambda command, cwd: (
        executed.append(command) or 0, "synthetic pass", ""
    )
    result = engine.run(task, project)

    assert result.success is False
    assert result.required_checks == ["relevant_tests"]
    assert result.completed_checks == []
    assert executed == []
    assert any("unverified" in detail and "contract changed" in detail
               for detail in result.details)


def test_verifier_unchanged_contract_remains_valid_during_command(tmp_path):
    """The contract fence must not reject an unchanged, fully evidenced plan."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["synthetic command"]}
    engine._run_command = lambda *_: (0, "synthetic pass", "")

    result = engine.run(task, project)

    assert result.success is True
    assert result.required_checks == ["relevant_tests"]
    assert result.completed_checks == ["relevant_tests"]
    assert not any("contract changed" in detail for detail in result.details)


# Synthetic Git-head binding controls. No live repository state is opened.
_SYNTHETIC_HEAD_A = "a" * 40
_SYNTHETIC_HEAD_B = "b" * 40


def _git_bound_synthetic_verifier(tmp_path):
    project, task = _synthetic_artifact_fixture(tmp_path)
    project.is_git_repo = True
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {"relevant_tests": ["synthetic verification command"]}
    return project, task, engine


def test_verifier_rejects_head_change_during_command(tmp_path):
    """A passing command for commit A cannot certify changed commit B."""
    project, task, engine = _git_bound_synthetic_verifier(tmp_path)
    heads = iter([_SYNTHETIC_HEAD_A, _SYNTHETIC_HEAD_A, _SYNTHETIC_HEAD_B])
    engine._read_git_head = lambda *_: next(heads)
    engine._run_command = lambda *_: (0, "synthetic pass", "")

    result = engine.run(task, project)

    assert result.success is False
    assert result.completed_checks == ["relevant_tests"]
    assert any("unverified" in d and "HEAD changed" in d for d in result.details)


def test_verifier_rejects_head_change_during_planning_without_execution(tmp_path):
    """Planner-time ref drift must abort before executing the command."""
    project, task, engine = _git_bound_synthetic_verifier(tmp_path)
    heads = iter([_SYNTHETIC_HEAD_A, _SYNTHETIC_HEAD_B])
    engine._read_git_head = lambda *_: next(heads)
    executed = []
    engine._run_command = lambda command, *_: (
        executed.append(command) or 0, "synthetic pass", ""
    )

    result = engine.run(task, project)

    assert result.success is False
    assert executed == []
    assert any("unverified" in d and "HEAD changed" in d for d in result.details)


def test_verifier_rejects_unavailable_git_head_without_execution(tmp_path):
    """An unavailable Git checkout cannot certify a Git-marked project."""
    project, task, engine = _git_bound_synthetic_verifier(tmp_path)
    engine._read_git_head = lambda *_: None
    executed = []
    engine._run_command = lambda command, *_: (
        executed.append(command) or 0, "synthetic pass", ""
    )

    result = engine.run(task, project)

    assert result.success is False
    assert executed == []
    assert any("unverified" in d and "HEAD unavailable" in d for d in result.details)


def test_verifier_rejects_expected_commit_mismatch_before_execution(tmp_path):
    """The caller's expected head is a binding input, not a hint."""
    project, task, engine = _git_bound_synthetic_verifier(tmp_path)
    engine._read_git_head = lambda *_: _SYNTHETIC_HEAD_B
    executed = []
    engine._run_command = lambda command, *_: (
        executed.append(command) or 0, "synthetic pass", ""
    )

    result = engine.run(task, project, expected_commit_sha=_SYNTHETIC_HEAD_A)

    assert result.success is False
    assert executed == []
    assert any("unverified" in d and "expected" in d for d in result.details)


def test_verifier_rejects_invalid_expected_commit_sha(tmp_path):
    """Malformed expected revisions cannot silently disable the Git fence."""
    project, task, engine = _git_bound_synthetic_verifier(tmp_path)
    engine._read_git_head = lambda *_: _SYNTHETIC_HEAD_A
    engine._run_command = lambda *_: (0, "synthetic pass", "")

    result = engine.run(task, project, expected_commit_sha="not-a-sha")

    assert result.success is False
    assert any("unverified" in d and "invalid expected" in d for d in result.details)


def test_verifier_accepts_stable_expected_git_commit(tmp_path):
    """Stable, explicitly bound Git checks remain eligible for PASS."""
    project, task, engine = _git_bound_synthetic_verifier(tmp_path)
    heads = iter([_SYNTHETIC_HEAD_A] * 3)
    engine._read_git_head = lambda *_: next(heads)
    engine._run_command = lambda *_: (0, "synthetic pass", "")

    result = engine.run(task, project, expected_commit_sha=_SYNTHETIC_HEAD_A.upper())

    assert result.success is True
    assert result.completed_checks == ["relevant_tests"]
    assert any(_SYNTHETIC_HEAD_A in d for d in result.details)


def test_verifier_reads_git_head_from_isolated_synthetic_checkout(tmp_path):
    """Exercise the actual metadata reader (not only a mocked HEAD supplier)."""
    import shutil
    import subprocess

    git = shutil.which("git")
    if git is None:
        pytest.skip("Git executable unavailable")

    subprocess.run([git, "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    subprocess.run(
        [
            git, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "fixture",
        ],
        cwd=tmp_path, check=True, timeout=15,
    )
    expected = subprocess.run(
        [git, "rev-parse", "--verify", "HEAD"], cwd=tmp_path,
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout.strip().lower()

    engine = VerificationEngine(tmp_path / "artifacts")

    assert engine._read_git_head(str(tmp_path)) == expected
    assert engine._read_git_head(str(tmp_path / "missing-directory")) is None


def test_verifier_rejects_plan_appended_during_execution_without_running_injected_command(tmp_path):
    """An appended planner command must not execute or certify a moving plan."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    plan = {"relevant_tests": ["synthetic approved command"]}
    engine.planner.plan = lambda *_: plan
    executed = []

    def change_plan(command, cwd):
        executed.append(command)
        if command == "synthetic approved command":
            plan["relevant_tests"].append("synthetic injected command")
        return 0, "synthetic pass", ""

    engine._run_command = change_plan
    result = engine.run(task, project)

    assert result.success is False
    assert executed == ["synthetic approved command"]
    assert any("unverified" in d and "plan changed" in d for d in result.details)


def test_verifier_rejects_plan_replaced_during_execution(tmp_path):
    """A planner replacing its already-executed check cannot leave a PASS."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    plan = {"relevant_tests": ["synthetic approved command"]}
    engine.planner.plan = lambda *_: plan

    def replace_plan(command, cwd):
        plan["relevant_tests"][0] = "synthetic replacement command"
        return 0, "synthetic pass", ""

    engine._run_command = replace_plan
    result = engine.run(task, project)

    assert result.success is False
    assert any("unverified" in d and "plan changed" in d for d in result.details)


def test_verifier_unchanged_planned_commands_still_pass(tmp_path):
    """A stable declared command plan is eligible for a verified success."""
    project, task = _synthetic_artifact_fixture(tmp_path)
    engine = VerificationEngine(tmp_path / "artifacts")
    engine.planner.plan = lambda *_: {
        "relevant_tests": ["synthetic approved command"],
    }
    engine._run_command = lambda *_: (0, "synthetic pass", "")

    result = engine.run(task, project)

    assert result.success is True
    assert result.completed_checks == ["relevant_tests"]
    assert not any("plan changed" in d for d in result.details)


_SYNTHETIC_HEAD_C = "c" * 40


class _FakeCompleted:
    def __init__(self, returncode, stdout):
        self.returncode, self.stdout = returncode, stdout


def test_read_git_head_uses_30s_timeout_and_retries_once_on_timeout(monkeypatch):
    """A saturated box must not flip a passing run to FAILED on one slow git."""
    import overmind.verification.verifier as verifier_module

    calls = []

    def flaky_run(cmd, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        return _FakeCompleted(0, _SYNTHETIC_HEAD_C + "\n")

    monkeypatch.setattr(verifier_module.subprocess, "run", flaky_run)
    assert VerificationEngine._read_git_head("synthetic") == _SYNTHETIC_HEAD_C
    assert calls == [30, 30]


def test_read_git_head_still_fails_closed_after_repeated_timeout(monkeypatch):
    import overmind.verification.verifier as verifier_module

    calls = []

    def always_timeout(cmd, **kwargs):
        calls.append(kwargs["timeout"])
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(verifier_module.subprocess, "run", always_timeout)
    assert VerificationEngine._read_git_head("synthetic") is None
    assert len(calls) == 2  # exactly one retry


def test_read_git_head_does_not_retry_a_real_git_failure(monkeypatch):
    import overmind.verification.verifier as verifier_module

    calls = []

    def not_a_repo(cmd, **kwargs):
        calls.append(1)
        return _FakeCompleted(128, "")

    monkeypatch.setattr(verifier_module.subprocess, "run", not_a_repo)
    assert VerificationEngine._read_git_head("synthetic") is None
    assert len(calls) == 1
