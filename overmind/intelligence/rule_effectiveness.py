"""Rule-effectiveness loop (Phase 2): join Sentinel rules ↔ portfolio hit-counts
↔ the lessons.md entries they trace to.

Answers three questions the ecosystem couldn't before:
  1. Which rules actually fire in the portfolio (and how often)?
  2. Which rules have NEVER fired (review candidates — stale, or a well-prevented
     class)?
  3. Which lessons.md sections have NO guarding rule (coverage gaps)?

Reads the Sentinel SOURCE checkout (rule metadata) + lessons.md + a
{rule_id: hits} map (from sentinel_aggregator.rule_hit_counts). Stdlib only;
no network. Paths default to the standard local layout, overridable via env.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_PLUGIN_ID = re.compile(r"^ID\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
_PLUGIN_SEV = re.compile(r"^SEVERITY\s*=\s*Severity\.(\w+)", re.MULTILINE)
_PLUGIN_SRC = re.compile(r"^SOURCE\s*=\s*\(?\s*[\"']([^\"']+)[\"']", re.MULTILINE)
_YAML_FIELD = lambda key: re.compile(rf"^{key}:\s*(.+?)\s*$", re.MULTILINE)
_HEADER = re.compile(r"^#{1,3}\s+(.*?)\s*$", re.MULTILINE)
_LESSON_REF = re.compile(r"lessons\.md#([A-Za-z0-9._:-]+)")


def default_sentinel_repo() -> Path:
    return Path(os.environ.get("SENTINEL_REPO", str(Path.home() / "code" / "Sentinel")))


def default_lessons_md() -> Path:
    return Path(os.environ.get("SENTINEL_LESSONS",
                               str(Path.home() / ".claude" / "rules" / "lessons.md")))


def _gh_anchor(header: str) -> str:
    s = header.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s)


def enumerate_rules(sentinel_repo: Path | None = None) -> list[dict]:
    repo = sentinel_repo or default_sentinel_repo()
    rules_dir = repo / "sentinel" / "rules"
    out: list[dict] = []
    plugins = rules_dir / "plugins"
    if plugins.is_dir():
        for p in sorted(plugins.glob("*.py")):
            if p.name == "__init__.py":
                continue
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            m_id = _PLUGIN_ID.search(t)
            if not m_id:
                continue
            m_sev = _PLUGIN_SEV.search(t)
            m_src = _PLUGIN_SRC.search(t)
            out.append({
                "id": m_id.group(1),
                "severity": m_sev.group(1) if m_sev else "?",
                "source": m_src.group(1) if m_src else "",
                "kind": "plugin",
            })
    yaml_dir = rules_dir / "yaml"
    if yaml_dir.is_dir():
        for p in sorted(yaml_dir.glob("*.yaml")):
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            m_id = _YAML_FIELD("id").search(t)
            if not m_id:
                continue
            m_sev = _YAML_FIELD("severity").search(t)
            m_src = _YAML_FIELD("source").search(t)
            out.append({
                "id": m_id.group(1).strip(),
                "severity": (m_sev.group(1).strip() if m_sev else "?"),
                "source": (m_src.group(1).strip() if m_src else ""),
                "kind": "yaml",
            })
    return out


def lesson_anchors(lessons_md: Path | None = None) -> list[str]:
    path = lessons_md or default_lessons_md()
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [_gh_anchor(h) for h in _HEADER.findall(text)]


def effectiveness(hit_counts: dict[str, int],
                  sentinel_repo: Path | None = None,
                  lessons_md: Path | None = None) -> dict:
    rules = enumerate_rules(sentinel_repo)
    anchors = lesson_anchors(lessons_md)

    rows = []
    cited_lessons: set[str] = set()
    for r in rules:
        hits = int(hit_counts.get(r["id"], 0))
        for m in _LESSON_REF.finditer(r["source"]):
            cited_lessons.add(m.group(1).lower())
        rows.append({**r, "hits": hits})
    rows.sort(key=lambda x: (-x["hits"], x["id"]))

    zero_hit = [{"id": r["id"], "severity": r["severity"], "source": r["source"]}
                for r in rows if r["hits"] == 0]

    # A lesson is "covered" if any rule cites an anchor that prefix-matches it
    # (rule anchors are sometimes shorter than the full GitHub anchor).
    def _covered(anchor: str) -> bool:
        return any(anchor.startswith(c) or c.startswith(anchor) for c in cited_lessons if c)
    lessons_without_rule = [a for a in anchors if a and not _covered(a)]

    fired = [r for r in rows if r["hits"] > 0]
    return {
        "summary": {
            "total_rules": len(rules),
            "rules_fired": len(fired),
            "rules_never_fired": len(zero_hit),
            "total_findings": sum(r["hits"] for r in rows),
            "lesson_anchors": len(anchors),
            "lessons_without_guarding_rule": len(lessons_without_rule),
        },
        "top_firing": rows[:10],
        "zero_hit_rules": zero_hit,
        "lessons_without_guarding_rule": lessons_without_rule,
    }
