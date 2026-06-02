"""Index + recall over the markdown memory files (~/.claude memory).

This is deliberately separate from the SQLite ``MemoryStore``: the markdown files
under ``~/.claude/memory`` and ``~/.claude/projects/<machine>/memory`` are the
*portable source of truth* (they sync across machines via claude-ecosystem-sync).
This module **indexes** them and never rewrites their content. The one mutating
operation is the explicit, opt-in ``consolidate(apply=True)`` decay pass, which
*moves* expired/stale facts into ``<memory>/archive/`` (reversible — never
deletes, never edits, never auto-merges).

Local-first / stdlib only: BM25 ranking over (name + description + body), a
bidirectional ``[[wiki-link]]`` graph, and a consolidation report (near-duplicates,
stale/unreviewed facts, orphan links, files missing from MEMORY.md). No network,
no embeddings dependency — deterministic and offline.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_INDEX_FILES = {"memory.md"}  # MEMORY.md is the index, not a fact


def sanitized_home() -> str:
    """Replicate Claude Code's cwd sanitization for the project-memory dir name."""
    return re.sub(r"[:\\/]", "-", str(Path.home()))


def default_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".claude" / "memory",
        home / ".claude" / "projects" / sanitized_home() / "memory",
    ]


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal stdlib frontmatter parse (no yaml dep). Returns (fields, body)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            # flatten nested "  type: x" under metadata: by last-key-wins on bare keys
            if key and val:
                fields.setdefault(key, val)
    return fields, text[m.end():]


@dataclass
class MemoryDoc:
    path: Path
    name: str
    description: str
    mtype: str
    body: str
    links: list[str]
    fields: dict
    _tokens: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.name or self.path.stem


def load_docs(roots: list[Path] | None = None) -> list[MemoryDoc]:
    roots = roots or default_roots()
    docs: list[MemoryDoc] = []
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.md")):
            if p.name.lower() in _INDEX_FILES:
                continue
            if "templates" in p.parts or p.name.endswith(".template.md"):
                continue  # scaffolding, not real facts
            if "archive" in p.parts:
                continue  # already-decayed facts — out of the live index
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            fields, body = _parse_frontmatter(text)
            name = fields.get("name") or p.stem
            doc = MemoryDoc(
                path=p,
                name=name,
                description=fields.get("description", ""),
                mtype=fields.get("type", "unknown"),
                body=body,
                links=_LINK_RE.findall(text),
                fields=fields,
            )
            doc._tokens = _tokenize(f"{name} {doc.description} {body}")
            docs.append(doc)
    return docs


# --- BM25 -------------------------------------------------------------------

def bm25_recall(docs: list[MemoryDoc], query: str, k: int = 5,
                k1: float = 1.5, b: float = 0.75) -> list[tuple[MemoryDoc, float]]:
    q_terms = _tokenize(query)
    if not docs or not q_terms:
        return []
    N = len(docs)
    df: Counter[str] = Counter()
    for d in docs:
        for t in set(d._tokens):
            df[t] += 1
    avgdl = sum(len(d._tokens) for d in docs) / N
    scored: list[tuple[MemoryDoc, float]] = []
    for d in docs:
        tf = Counter(d._tokens)
        dl = len(d._tokens) or 1
        score = 0.0
        for t in q_terms:
            if t not in tf:
                continue
            idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            denom = tf[t] + k1 * (1 - b + b * dl / avgdl)
            score += idf * (tf[t] * (k1 + 1)) / denom
        if score > 0:
            scored.append((d, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# --- link graph -------------------------------------------------------------

def build_link_graph(docs: list[MemoryDoc]) -> dict[str, dict[str, list[str]]]:
    by_slug = {d.slug: d for d in docs}
    out: dict[str, list[str]] = defaultdict(list)
    inn: dict[str, list[str]] = defaultdict(list)
    orphans: list[tuple[str, str]] = []
    for d in docs:
        for link in d.links:
            target = link.strip()
            if target in by_slug:
                out[d.slug].append(target)
                inn[target].append(d.slug)
            else:
                orphans.append((d.slug, target))
    return {"out": dict(out), "in": dict(inn), "orphans": orphans}


# --- consolidation report (read-only; suggests, never edits) ----------------

def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _age_days(fields: dict) -> int | None:
    for key in ("last_reviewed", "created"):
        raw = fields.get(key)
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                d = datetime.strptime(raw[:19] if "T" in raw else raw[:10], fmt).date()
                return (date.today() - d).days
            except ValueError:
                continue
    return None


def consolidate_report(docs: list[MemoryDoc], roots: list[Path] | None = None,
                       dup_threshold: float = 0.6, stale_days: int = 180) -> dict:
    roots = roots or default_roots()
    graph = build_link_graph(docs)
    # near-duplicate pairs
    dups: list[dict] = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            sim = _jaccard(docs[i]._tokens, docs[j]._tokens)
            if sim >= dup_threshold:
                dups.append({"a": docs[i].slug, "b": docs[j].slug, "similarity": round(sim, 3)})
    # stale / unreviewed
    stale, undated = [], []
    for d in docs:
        age = _age_days(d.fields)
        if age is None:
            undated.append(d.slug)
        elif age > stale_days:
            stale.append({"slug": d.slug, "age_days": age})
    # files missing from MEMORY.md index
    indexed_names: set[str] = set()
    for root in roots:
        idx = root / "MEMORY.md"
        if idx.exists():
            txt = idx.read_text(encoding="utf-8", errors="ignore")
            indexed_names |= {m.lower() for m in re.findall(r"\(([^)]+)\.md\)", txt)}
    missing_from_index = [d.path.stem for d in docs
                          if d.path.stem.lower() not in indexed_names
                          and "templates" not in d.path.parts]
    return {
        "doc_count": len(docs),
        "near_duplicates": dups,
        "stale": stale,
        "undated_no_review_field": undated,
        "orphan_links": [{"from": s, "missing_target": t} for s, t in graph["orphans"]],
        "missing_from_MEMORY_md": missing_from_index,
    }


# --- top-level entry points (called by the CLI) -----------------------------

def cmd_index(roots: list[Path] | None = None) -> dict:
    docs = load_docs(roots)
    graph = build_link_graph(docs)
    return {
        "roots": [str(r) for r in (roots or default_roots())],
        "doc_count": len(docs),
        "by_type": dict(Counter(d.mtype for d in docs)),
        "link_edges": sum(len(v) for v in graph["out"].values()),
        "orphan_link_count": len(graph["orphans"]),
        "docs": [{"slug": d.slug, "type": d.mtype, "links": d.links,
                  "description": d.description} for d in docs],
    }


def cmd_recall(query: str, k: int = 5, roots: list[Path] | None = None) -> dict:
    docs = load_docs(roots)
    graph = build_link_graph(docs)
    hits = bm25_recall(docs, query, k=k)
    return {
        "query": query,
        "results": [
            {
                "slug": d.slug,
                "type": d.mtype,
                "score": round(score, 3),
                "description": d.description,
                "path": str(d.path),
                "linked": graph["out"].get(d.slug, []) + graph["in"].get(d.slug, []),
            }
            for d, score in hits
        ],
    }


def _is_expired(fields: dict) -> bool:
    raw = fields.get("valid_until")
    if not raw:
        return False
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date() < date.today()
    except ValueError:
        return False


def archive_stale(roots: list[Path] | None = None, stale_days: int = 365) -> list[dict]:
    """Move expired (valid_until past) or stale (last_reviewed/created older than
    stale_days) facts into a sibling ``archive/`` dir. Reversible — moves, never
    deletes; never touches un-decayed facts. Returns what was archived."""
    archived: list[dict] = []
    for d in load_docs(roots):
        age = _age_days(d.fields)
        expired = _is_expired(d.fields)
        if not expired and not (age is not None and age > stale_days):
            continue
        arch_dir = d.path.parent / "archive"
        arch_dir.mkdir(exist_ok=True)
        dest = arch_dir / d.path.name
        try:
            d.path.rename(dest)
        except OSError:
            continue
        archived.append({
            "slug": d.slug,
            "from": str(d.path),
            "to": str(dest),
            "reason": "expired (valid_until past)" if expired else f"stale (>{stale_days}d unreviewed)",
        })
    return archived


def cmd_consolidate(roots: list[Path] | None = None, apply: bool = False,
                    stale_days: int = 365) -> dict:
    report = consolidate_report(load_docs(roots), roots)
    if apply:
        report["archived"] = archive_stale(roots, stale_days)
        if report["archived"]:
            report["note"] = ("archived to <memory>/archive/ (reversible). "
                              "Update MEMORY.md to drop the archived index lines.")
        else:
            report["note"] = "apply: nothing expired or stale — no facts archived."
    return report

