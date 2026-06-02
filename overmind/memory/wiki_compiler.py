"""Wiki compiler (Phase 3): render the flat SQLite memories into an interlinked
markdown knowledge base — the "Karpathy-style wiki" on Overmind's roadmap.

Read-only over the memory store: produces an ``index.md`` + one page per scope,
each memory a section with its content, tags, confidence, and ``[[wiki links]]``
resolved from its ``linked_memories``. Deterministic, stdlib-only. Duck-typed on
the MemoryRecord attributes so it's trivially testable.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


def _slug(value: str) -> str:
    s = (value or "global").strip().lower()
    s = re.sub(r"[^\w-]+", "-", s).strip("-")  # collapse separators (: / space) to '-'
    return s or "global"


def compile_wiki(memories: list, out_dir) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    id_to_title = {getattr(m, "memory_id", ""): getattr(m, "title", "") for m in memories}
    by_scope: dict[str, list] = defaultdict(list)
    for m in memories:
        by_scope[getattr(m, "scope", None) or "global"].append(m)

    link_count = 0
    scope_pages: list[tuple[str, str, int]] = []
    for scope, mems in sorted(by_scope.items()):
        lines = [f"# {scope}", ""]
        by_type: dict[str, list] = defaultdict(list)
        for m in mems:
            by_type[getattr(m, "memory_type", None) or "unknown"].append(m)
        for mtype, items in sorted(by_type.items()):
            lines += [f"## {mtype}", ""]
            for m in items:
                lines.append(f"### {getattr(m, 'title', '(untitled)')}")
                content = getattr(m, "content", "") or ""
                if content:
                    lines.append(content.strip())
                meta = []
                tags = getattr(m, "tags", None) or []
                if tags:
                    meta.append("tags: " + ", ".join(tags))
                conf = getattr(m, "confidence", None)
                if conf is not None:
                    meta.append(f"confidence: {conf}")
                links = getattr(m, "linked_memories", None) or []
                if links:
                    link_count += len(links)
                    meta.append("links: " + ", ".join(
                        f"[[{id_to_title.get(l, l)}]]" for l in links))
                if meta:
                    lines += ["", "_" + " · ".join(meta) + "_"]
                lines.append("")
        fname = _slug(scope) + ".md"
        (out / fname).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        scope_pages.append((scope, fname, len(mems)))

    idx = [
        "# Overmind Memory Wiki",
        "",
        f"Compiled {len(memories)} memories across {len(scope_pages)} scope(s). "
        "Source of truth stays the memory store; this is a generated, browsable view.",
        "",
        "## Scopes",
    ]
    for scope, fname, n in scope_pages:
        idx.append(f"- [{scope}]({fname}) — {n} memory(ies)")
    (out / "index.md").write_text("\n".join(idx) + "\n", encoding="utf-8")

    return {
        "out_dir": str(out),
        "pages": len(scope_pages) + 1,
        "memories": len(memories),
        "links": link_count,
        "scopes": [s for s, _, _ in scope_pages],
    }
