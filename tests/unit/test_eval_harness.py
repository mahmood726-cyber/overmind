from __future__ import annotations

from overmind.config import AppConfig
from overmind.core.orchestrator import Orchestrator
from overmind.intelligence.eval_harness import EvalHarness
from overmind.storage.models import ProjectRecord


def test_eval_harness_writes_reproducible_report(tmp_path):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()

    (config_dir / "roots.yaml").write_text(
        "scan_roots: []\n"
        "scan_rules:\n"
        "  include_git_repos: true\n"
        "  include_non_git_apps: true\n"
        "  incremental_scan: true\n"
        "  max_depth: 2\n"
        "guidance_filenames:\n"
        "  - \"README.md\"\n",
        encoding="utf-8",
    )
    (config_dir / "runners.yaml").write_text("runners: []\n", encoding="utf-8")
    (config_dir / "policies.yaml").write_text(
        "concurrency:\n  default_active_sessions: 1\n  max_active_sessions: 1\n  degraded_sessions: 1\n"
        "limits:\n  idle_timeout_min: 10\n  summary_trigger_output_lines: 400\n"
        "routing: {}\n"
        "risk_policy: {}\n"
        "isolation:\n  mode: high_risk\n",
        encoding="utf-8",
    )
    (config_dir / "projects_ignore.yaml").write_text(
        "ignored_directories: []\nignored_file_suffixes: []\n",
        encoding="utf-8",
    )
    (config_dir / "verification_profiles.yaml").write_text(
        "profiles: {}\nproject_rules: []\n",
        encoding="utf-8",
    )

    config = AppConfig.from_directory(config_dir=config_dir, data_dir=data_dir, db_path=data_dir / "state.db")
    orchestrator = Orchestrator(config)
    try:
        orchestrator.db.upsert_project(
            ProjectRecord(
                project_id="eval-project",
                name="Eval Project",
                root_path=str(tmp_path / "project"),
                project_type="python_tool",
                stack=["python"],
                test_commands=['python -c "print(\'ok\')"'],
                risk_profile="high",
            )
        )

        report = EvalHarness(orchestrator, config.data_dir / "artifacts").run(
            focus_project_id="eval-project"
        )

        assert report["focus_project_id"] == "eval-project"
        assert report["isolation_policy"]["mode"] == "high_risk"
        assert report["state"]["project_count"] == 1
        assert "artifact" in report
        assert (config.data_dir / "artifacts" / "eval_harness_eval-project.json").exists()
    finally:
        orchestrator.close()
