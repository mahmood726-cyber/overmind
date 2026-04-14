from __future__ import annotations

import sys

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
