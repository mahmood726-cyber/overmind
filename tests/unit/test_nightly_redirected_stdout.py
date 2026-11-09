"""Exercise Windows stream ownership without pytest capture in the child."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("discovery_available", [True, False])
def test_nightly_summary_survives_discovery_import(tmp_path, discovery_available):
    # Reproduce the import-time side effect in the external push helper, without
    # scanning real repositories or requiring that machine-local helper.
    helper = "import io, sys\nsys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')\n"
    if discovery_available:
        helper += "from pathlib import Path\ndef discover_repos():\n    return [str(Path(__file__).parent)]\n"
        (tmp_path / "STUCK_FAILURES.jsonl").write_text(
            json.dumps({"rule_id": "fixture_rule", "file": "fixture.py", "line": 1}) + "\n",
            encoding="utf-8",
        )
    (tmp_path / "push_all_repos.py").write_text(helper, encoding="utf-8")
    driver = tmp_path / "driver.py"
    driver.write_text(textwrap.dedent("""
        import json
        import os
        from pathlib import Path
        import sys

        sys.path.insert(0, sys.argv[1])
        from scripts import nightly_verify
        from overmind.evolution.manager import EvolutionManager
        from overmind.evolution.skill_library import SkillLibrary
        from overmind.evolution.promotion import PromotionGate, SkillArchive
        from overmind.integrations import sentinel_aggregator

        data = Path(os.environ["OVERMIND_DATA_DIR"])
        data.mkdir()
        db = nightly_verify.StateDatabase(Path(os.environ["OVERMIND_DB_PATH"]))
        try:
            dream = nightly_verify.DreamEngine(db).dream()
            EvolutionManager(data / "wiki").evolve([])
            skills = SkillLibrary(data / "wiki" / "SKILLS.json")
            PromotionGate(skills, archive=SkillArchive(data / "archive.jsonl")).sweep()
            skills.demote_stale()
            db.prune_checkpoints(keep=100)
            print("end-of-run database steps complete", flush=True)
            # Do not fall back to any machine-local discovery module.
            sentinel_aggregator._DISCOVER_IMPORT_CANDIDATES = (str(data.parent),)
            report = {"dream": dream, "sentinel": sentinel_aggregator.collect()}
            nightly_verify._atomic_write_text(data / "latest.json", json.dumps(report))
            print("=" * 60)
            print("NIGHTLY VERIFICATION COMPLETE")
            print("=" * 60, flush=True)
            print("stderr still open", file=sys.stderr, flush=True)
            assert sys.stdout is sys.__stdout__
            assert sys.stderr is sys.__stderr__
        finally:
            db.close()
    """), encoding="utf-8")
    env = os.environ.copy()
    env.update(
        OVERMIND_DB_PATH=str(tmp_path / "data" / "state.db"),
        OVERMIND_DATA_DIR=str(tmp_path / "data"),
        OVERMIND_DISCOVER_IMPORT_ROOT=str(tmp_path),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
    )
    log = tmp_path / "nightly.log"
    # Same append-to-file stdout + merged stderr handles as nightly_verify.bat.
    with log.open("ab") as output:
        result = subprocess.run(
            [sys.executable, str(driver), str(ROOT)], cwd=tmp_path, env=env,
            stdout=output, stderr=subprocess.STDOUT, timeout=120,
        )
    output = log.read_text(encoding="utf-8")
    assert result.returncode == 0, output
    assert "=" * 60 + "\nNIGHTLY VERIFICATION COMPLETE\n" + "=" * 60 in output
    assert "stderr still open" in output
    report = json.loads((tmp_path / "data" / "latest.json").read_text(encoding="utf-8"))
    assert ("error" not in report["sentinel"]) == discovery_available
    if discovery_available:
        assert report["sentinel"]["total_block"] == 1
        assert report["sentinel"]["top_rules"] == [{"rule_id": "fixture_rule", "count": 1}]
