"""Tests for ecosystem_eval config-consistency (P3-c)."""
from __future__ import annotations

from overmind.intelligence.ecosystem_eval import eval_config_consistency


def _agent(home, name, agents_md, index_yaml=None, rules_md="# R\ncommon\n"):
    d = home / name
    (d / "rules").mkdir(parents=True)
    (d / "AGENTS.md").write_text(agents_md, encoding="utf-8")
    (d / "rules" / "rules.md").write_text(rules_md, encoding="utf-8")
    if index_yaml is not None:
        (d / "rules" / "_index.yaml").write_text(index_yaml, encoding="utf-8")


def test_detects_agents_md_drift_and_missing_index(tmp_path):
    # claude has new AGENTS.md + _index.yaml; gemini/codex have the old AGENTS.md and no index.
    _agent(tmp_path, ".claude", "# Agents v2\n", index_yaml="always: []\n")
    _agent(tmp_path, ".gemini", "# Agents v1\n")
    _agent(tmp_path, ".codex", "# Agents v1\n")
    r = eval_config_consistency(home=tmp_path)
    assert r["status"] == "drift"
    drift_files = {d["file"] for d in r["drift"]}
    assert "AGENTS.md" in drift_files            # content differs across agents
    assert "rules/_index.yaml" in drift_files    # present only in .claude
    # rules.md is identical everywhere → consistent
    assert "rules/rules.md" not in drift_files


def test_eol_normalized_not_flagged(tmp_path):
    # write_bytes (not write_text) so the CRLF is truly on disk.
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".gemini" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "AGENTS.md").write_bytes(b"# Agents\nx\n")
    (tmp_path / ".gemini" / "AGENTS.md").write_bytes(b"# Agents\r\nx\r\n")   # CRLF, same content
    (tmp_path / ".claude" / "rules" / "rules.md").write_bytes(b"# R\ny\n")
    (tmp_path / ".gemini" / "rules" / "rules.md").write_bytes(b"# R\r\ny\r\n")
    r = eval_config_consistency(home=tmp_path)
    assert r["status"] == "ok"  # CRLF vs LF must not read as drift
