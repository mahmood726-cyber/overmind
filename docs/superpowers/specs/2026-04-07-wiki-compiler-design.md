# Wiki Compiler Design Spec

**Date:** 2026-04-07
**Status:** APPROVED
**Location:** `C:\overmind\` (extends nightly verifier)
**Inspired by:** Karpathy's LLM Knowledge Base pattern (April 2026)

## 1. Purpose

After the nightly verifier produces CertBundles, the wiki compiler transforms them into structured, interlinked Markdown articles — one per project. This creates a persistent, human-readable, git-versioned knowledge base that Claude Code can read natively via auto-memory, replacing the low-value SQLite memory records.

## 2. Architecture

```
nightly_verify.py (existing)
  └── After dream cycle, call:
      WikiCompiler.compile(bundles, projects)
        ├── For each bundle: generate/update wiki/{project_id}.md
        ├── Generate wiki/INDEX.md (auto-generated table of all projects)
        ├── Generate wiki/CHANGELOG.md (what changed tonight)
        └── Git commit the wiki directory
```

### Files

- Create: `overmind/wiki/compiler.py` — main compiler logic
- Create: `overmind/wiki/templates.py` — Markdown templates for articles
- Modify: `scripts/nightly_verify.py` — call compiler after dream cycle
- Create: `C:\overmind\wiki/` directory — output articles
- Test: `C:\OvermindTestBed\tests\test_wiki_compiler.py`

## 3. Article Template

Each project gets `wiki/{project_id}.md`:

```markdown
# {project_name}

**Last verified:** {date} UTC | **Verdict:** {verdict} ({witness_summary})
**Bundle hash:** {hash} | **Risk:** {risk_profile} | **Math:** {math_score}

## Health

| Witness | Verdict | Time | Detail |
|---------|---------|------|--------|
| Test Suite | {w1_verdict} | {w1_time}s | {w1_detail} |
| Smoke | {w2_verdict} | {w2_time}s | {w2_detail} |
| Numerical | {w3_verdict} | {w3_time}s | {w3_detail} |

## Project

- **Path:** {root_path}
- **Type:** {project_type}
- **Stack:** {stack}
- **Test command:** `{test_command}`

## Verification History

| Date | Verdict | Witnesses | Time | Hash |
|------|---------|-----------|------|------|
| {date} | {verdict} | {n}/{n} | {time}s | {hash} |
| ... (last 10 entries) |

## Notes

{any_failure_details_or_empty}
```

### Design decisions

- **Template-based, no LLM calls** — structured fields from CertBundle + ProjectRecord. Fast, free, deterministic.
- **History appended** — each run appends a row to the Verification History table. Cap at 10 rows (oldest dropped).
- **Notes section** — populated only for REJECT/FAIL with witness stderr excerpts. Empty for CERTIFIED/PASS.
- **No cross-project backlinks in v1** — would require analyzing project dependencies, deferred to Phase 4.

## 4. INDEX.md

Auto-generated summary of all projects in wiki:

```markdown
# Overmind Wiki Index

**Last compiled:** {date} | **Projects:** {total} | **Certified:** {n} | **Rejected:** {n} | **Failed:** {n}

| Project | Verdict | Risk | Math | Last Verified |
|---------|---------|------|------|---------------|
| [{name}](project_id.md) | CERTIFIED | high | 20 | 2026-04-08 |
| ... |
```

Sorted by: REJECT first (needs attention), then FAIL, then CERTIFIED, then PASS.

## 5. CHANGELOG.md

What changed in tonight's run, appended per night:

```markdown
## 2026-04-08

**Verified:** 50 projects | **Certified:** 32 | **Rejected:** 2 | **Failed:** 3

### Changes from last night
- MetaGuard: CERTIFIED → REJECT (numerical drift in tau2)
- idea12: PASS → FAIL (ImportError: scipy)
- BayesianMA: REJECT → CERTIFIED (baseline updated)

### New projects verified
- OvermindTestBed (first verification)
```

Changelog is append-only, newest at top. Cap at 30 entries.

## 6. Integration with nightly_verify.py

After the dream cycle completes:

```python
from overmind.wiki.compiler import WikiCompiler

wiki_dir = Path("C:/overmind/wiki")
compiler = WikiCompiler(wiki_dir)
compiler.compile(
    bundles=[r["bundle"] for r in results],
    projects=[r["project"] for r in results],
)
```

The compiler:
1. Reads existing articles (to preserve history rows)
2. Generates updated articles from bundles
3. Writes INDEX.md and appends to CHANGELOG.md
4. Git commits the wiki directory: `git add wiki/ && git commit -m "wiki: nightly {date} — {n} certified, {n} reject, {n} fail"`

## 7. Testing

| File | Tests | Description |
|------|-------|-------------|
| test_wiki_compiler.py | 6 | Article generation from CertBundle, history append, INDEX generation, CHANGELOG append, REJECT notes populated, git commit |

Combined with existing 74 = **80 total**.

## 8. Constraints

- No LLM calls — pure template rendering
- No network access — reads local CertBundles only
- Git commit is optional (skip if `--no-commit` flag or not a git repo)
- Articles for projects not verified tonight are untouched (stale but preserved)
- History table capped at 10 rows per article
- CHANGELOG capped at 30 entries
- Total wiki size: ~50-100 KB for 50 projects (small)
