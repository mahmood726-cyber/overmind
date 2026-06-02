"""JIT rule loading (1B): resolve a task signal to the relevant rule slices.

Reads ``~/.claude/rules/_index.yaml`` (the routing table) and returns only the
rule sections that match a given file/glob or task description — so an agent
loads a few hundred relevant tokens instead of all four rules/*.md files.

The rule CONTENT stays in the markdown files; this only routes to slices and
extracts them. Section refs look like ``rules.md#HTML apps (large single-file)``;
``AGENTS.md#...`` refs resolve against ``~/.claude/AGENTS.md``.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import yaml

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def default_rules_dir() -> Path:
    return Path.home() / ".claude" / "rules"


def _resolve_file(name: str, rules_dir: Path) -> Path:
    # AGENTS.md / CLAUDE.md etc. live one level up (~/.claude); rules live in rules_dir.
    if name.upper() in {"AGENTS.MD", "CLAUDE.MD", "GEMINI.MD", "CODEX.MD"}:
        return rules_dir.parent / name
    return rules_dir / name


def extract_section(text: str, section: str) -> str | None:
    """Return the markdown block under the header whose title == section."""
    lines = text.splitlines()
    start = None
    level = 0
    for i, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if m and m.group(2).strip() == section.strip():
            start, level = i, len(m.group(1))
            break
    if start is None:
        return None
    out = [lines[start]]
    for line in lines[start + 1:]:
        m = _HEADER_RE.match(line)
        if m and len(m.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out).strip()


def resolve_ref(ref: str, rules_dir: Path) -> dict:
    """Resolve 'file.md#Section' (or 'file.md') to {ref, found, text}."""
    fname, _, section = ref.partition("#")
    path = _resolve_file(fname.strip(), rules_dir)
    if not path.exists():
        return {"ref": ref, "found": False, "reason": f"missing file {path}"}
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not section:
        return {"ref": ref, "found": True, "text": text.strip()}
    block = extract_section(text, section)
    if block is None:
        return {"ref": ref, "found": False, "reason": f"section '{section}' not found in {fname}"}
    return {"ref": ref, "found": True, "text": block}


def _matches(query: str, entry: dict) -> bool:
    q = query.strip()
    ql = q.lower()
    base = Path(q).name
    for g in entry.get("when_globs", []):
        if fnmatch.fnmatch(q, g) or fnmatch.fnmatch(base, g) or fnmatch.fnmatch(ql, g.lower()):
            return True
    for kw in entry.get("when_keywords", []):
        if kw.lower() in ql:
            return True
    return False


def load_index(rules_dir: Path | None = None) -> dict:
    rules_dir = rules_dir or default_rules_dir()
    idx_path = rules_dir / "_index.yaml"
    if not idx_path.exists():
        return {}
    return yaml.safe_load(idx_path.read_text(encoding="utf-8")) or {}


def rules_for(query: str, with_text: bool = False, rules_dir: Path | None = None) -> dict:
    rules_dir = rules_dir or default_rules_dir()
    index = load_index(rules_dir)
    if not index:
        return {"query": query, "error": f"no _index.yaml in {rules_dir}"}

    matched_ids: list[str] = []
    refs: list[str] = list(index.get("always", []))
    for entry in index.get("rules", []):
        if _matches(query, entry):
            matched_ids.append(entry.get("id", "?"))
            refs += entry.get("load", [])
    if not matched_ids:
        refs += index.get("fallback", [])

    # de-dupe, preserve order
    seen: set[str] = set()
    ordered = [r for r in refs if not (r in seen or seen.add(r))]

    result: dict = {"query": query, "matched": matched_ids, "slices": ordered}
    if with_text:
        result["loaded"] = [resolve_ref(r, rules_dir) for r in ordered]
        missing = [d["ref"] for d in result["loaded"] if not d["found"]]
        if missing:
            result["unresolved"] = missing
    else:
        # still validate the refs resolve (cheap integrity check)
        bad = [r for r in ordered if not resolve_ref(r, rules_dir)["found"]]
        if bad:
            result["unresolved"] = bad
    return result
