from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from overmind.config import AppConfig
from overmind.discovery.indexer import ProjectIndexer
from overmind.nightly import runner, selection
from overmind.nightly.reporting import write_selection_report, _promote_progress_to_partial_report
from overmind.storage.db import StateDatabase
from overmind.storage.models import ProjectRecord


@pytest.fixture
def db(tmp_path):
    database = StateDatabase(tmp_path / "state.db")
    yield database
    database.close()


def add_project(db, path, project_id, name=None, exists=False):
    if exists:
        path.mkdir(parents=True)
    record = ProjectRecord(project_id, name or project_id, str(path),
                           test_commands=["python -m pytest"], risk_profile="high")
    db.upsert_project(record)
    return record


def test_select_stale_rows_do_not_consume_limit_or_duplicate_name(db, tmp_path):
    stale = add_project(db, tmp_path / "old", "a", "same")
    live = add_project(db, tmp_path / "new", "z", "same", exists=True)
    selected = selection.select_projects(db, "medium", 1)
    assert [p.project_id for p in selected] == [live.project_id]
    assert selected.stale_index == [{"project_id": stale.project_id, "path": stale.root_path}]
    assert len(db.list_projects()) == 2


def test_select_all_stale_fails_loudly(db, tmp_path):
    add_project(db, tmp_path / "missing", "a")
    with pytest.raises(RuntimeError, match="project index is stale: 1 of 1 root paths missing; run a scan"):
        selection.select_projects(db, "medium", 50)


def test_select_empty_filter_is_not_stale(db, tmp_path):
    add_project(db, tmp_path / "missing", "a")
    assert selection.select_projects(db, "medium", 50, paths_filter=set()) == []


def test_select_limit_fifty_counts_only_existing_projects(db, tmp_path):
    for index in range(51):
        add_project(db, tmp_path / f"missing-{index}", f"a-{index}")
        add_project(db, tmp_path / f"live-{index}", f"z-{index}", exists=True)
    selected = selection.select_projects(db, "medium", 50)
    assert len(selected) == 50
    assert all(Path(p.root_path).exists() for p in selected)
    assert len(selected.stale_index) == 51


def test_nightly_partial_report_preserves_stale_audit_not_old_failures(tmp_path):
    now = datetime.now(UTC)
    stale = [{"project_id": "missing", "path": str(tmp_path / "missing")}]
    write_selection_report(tmp_path, now, False, stale)
    (tmp_path / f".progress_{now:%Y-%m-%d}.json").write_text(
        json.dumps({"existing": "CERTIFIED", "missing": "FAIL"}), encoding="utf-8")
    _promote_progress_to_partial_report(f"{now:%Y-%m-%d}", report_dir=tmp_path)
    report = json.loads((tmp_path / f"nightly_{now:%Y-%m-%d}.json").read_text())
    assert report["total_projects"] == report["certified"] == 1
    assert report["failed"] == 0
    assert report["stale_index"] == 1
    assert report["stale_index_projects"] == stale


def test_nightly_main_exits_nonzero_on_stale_index(db, tmp_path, monkeypatch):
    from scripts import nightly_verify
    import atexit

    add_project(db, tmp_path / "missing", "a")
    monkeypatch.setattr(atexit, "register", lambda *args: None)
    monkeypatch.setattr(nightly_verify, "StateDatabase", lambda path: db)
    monkeypatch.setattr(nightly_verify, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(runner, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(nightly_verify, "parse_args", lambda: SimpleNamespace(
        limit=50, timeout=1, min_risk="medium", dry_run=False,
        create_baselines=False, projects_from_file=None))
    with pytest.raises(SystemExit) as exc:
        nightly_verify.main()
    assert exc.value.code == 1


def make_indexer(tmp_path, db):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    scan_root = tmp_path / "projects"
    scan_root.mkdir()
    (config_dir / "roots.yaml").write_text(
        f"scan_roots:\n  - {scan_root.as_posix()}\n", encoding="utf-8")
    config = AppConfig.from_directory(config_dir=config_dir, data_dir=tmp_path / "data",
                                      db_path=tmp_path / "state.db")
    return ProjectIndexer(config, db), scan_root


@pytest.mark.parametrize("focused", [False, True])
def test_indexer_marks_missing_and_reuses_id_after_move(db, tmp_path, focused):
    indexer, scan_root = make_indexer(tmp_path, db)
    stale = add_project(db, tmp_path / "old" / "sample", "original", "sample")
    indexer.incremental_refresh()
    assert db.get_project(stale.project_id).root_path_missing is True
    moved = scan_root / "sample"
    moved.mkdir()
    (moved / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
    records = indexer.incremental_refresh(stale.project_id if focused else None)
    assert [p.project_id for p in records] == [stale.project_id]
    assert len(db.list_projects()) == 1
    assert db.get_project(stale.project_id).root_path == str(moved.resolve())
    assert db.get_project(stale.project_id).root_path_missing is False
    # A changed signature must not restore the scanner's path-derived ID.
    (moved / "README.md").write_text("changed", encoding="utf-8")
    indexer.incremental_refresh(stale.project_id if focused else None)
    assert len(db.list_projects()) == 1


def test_nightly_all_stale_writes_reports_without_verifying(db, tmp_path, monkeypatch):
    stale = add_project(db, tmp_path / "missing", "a")
    monkeypatch.setattr(runner, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(runner, "DATA_DIR", tmp_path / "data")
    def forbidden(*args, **kwargs):
        pytest.fail("stale projects must not initialize verification")
    monkeypatch.setattr(runner, "TruthCertEngine", forbidden)
    args = SimpleNamespace(projects_from_file=None, min_risk="medium", limit=50,
                           dry_run=False, timeout=1)
    now = datetime.now(UTC)
    with pytest.raises(RuntimeError, match="project index is stale"):
        runner._run_verification(db, args, now)
    report = json.loads((runner.REPORT_DIR / f"nightly_{now:%Y-%m-%d}.json").read_text())
    assert report["total_projects"] == report["failed"] == 0
    assert report["stale_index"] == 1
    assert report["stale_index_projects"] == [{"project_id": "a", "path": stale.root_path}]
    md = (runner.REPORT_DIR / f"nightly_{now:%Y-%m-%d}.md").read_text()
    assert "1 stale_index" in md
    assert stale.root_path in md
    assert "run a scan" in md
