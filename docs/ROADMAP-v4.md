# Overmind v4 Roadmap

**Vision:** Self-improving research operations platform with certified verification, structured knowledge, and automated failure diagnosis.

**Status:** Updated 2026-04-07

---

## Phase 1: TruthCert Verification Backbone [SHIPPED]

Multi-witness verification with scope locks, fail-closed arbitrator, CERTIFIED/REJECT/FAIL verdicts.

- 3 witnesses: TestSuite (all), Smoke (tier 2+), Numerical (tier 3)
- Tiered by risk: high+math≥10 → 3, high/medium_high → 2, else → 1
- Arbitrator: disagreement → REJECT (investigate), consensus → CERTIFIED
- CertBundle with deterministic SHA-256 hash per verification
- Nightly verifier at 3 AM via Task Scheduler
- 74 integration tests (53 Overmind + 21 TruthCert)

**Spec:** `docs/superpowers/specs/2026-04-07-truthcert-verification-backbone-design.md`
**Plan:** `docs/superpowers/plans/2026-04-07-truthcert-backbone.md`

---

## Phase 2: Karpathy Wiki Compiler [NEXT]

Automated knowledge base that compiles nightly verification results into structured, interlinked Markdown articles. Inspired by Karpathy's "LLM Knowledge Base" pattern (April 2026).

### What it does
After the nightly verifier completes, a wiki compiler:
1. Reads all CertBundles from `data/nightly_reports/bundles/{date}/`
2. Reads each project's README, CLAUDE.md, test output
3. Writes/updates structured Markdown articles in `C:\overmind\wiki/{project_id}.md`
4. Cross-links related projects (same tech stack, same failure patterns)
5. Runs "lint" pass: detects contradictions between wiki and lessons.md
6. Generates a changelog diff: what changed since last night

### Article structure per project
```markdown
# {ProjectName}

**Last verified:** 2026-04-08 03:00 UTC
**Verdict:** CERTIFIED (3/3 witnesses)
**Bundle hash:** c7e2f1...

## Health
- Test suite: 30/30 PASS (3.7s)
- Smoke imports: 12/12 OK
- Numerical: tau2=0.0412 (within tolerance)

## Key Facts
- Risk: high, Math score: 20
- Stack: Python, HTML, Bayesian ensemble
- Calibration slope: 0.874 (Platt scaling, fixed 2026-03-25)

## History
- 2026-04-08: CERTIFIED (3/3)
- 2026-04-07: CERTIFIED (2/2)
- 2026-04-06: not verified

## Related
- [[MetaGuard]] — same tau2 estimator
- [[BayesianMA]] — shared Bayesian engine
```

### Why this beats current memory
| Current (SQLite memories) | Wiki compiler |
|---|---|
| Flat key-value records | Structured interlinked articles |
| Machine-readable only | Human-readable Markdown |
| Requires DB queries to access | Claude Code reads natively via auto-memory |
| Dream cycle does primitive merging | LLM writes coherent narratives |
| No cross-project linking | Backlinks between related projects |

### Implementation approach
- New module: `overmind/wiki/compiler.py`
- Runs after dream cycle in nightly_verify.py
- Uses Claude API (haiku) for article generation — cheap, fast
- Or: template-based generation (no LLM needed for structured fields, only for narratives)
- Wiki directory: `C:\overmind\wiki/` with one .md per project
- Index file: `C:\overmind\wiki/INDEX.md` auto-generated

### Open questions
- LLM-generated vs template-based articles? (Template for structured fields, LLM for narratives/connections)
- Should wiki articles be committed to git? (Yes — version history is valuable)
- How to handle 276+ projects without token explosion? (Only update changed projects)

---

## Phase 3: Judge Agent [AFTER WIKI]

Automated failure diagnosis that turns REJECT/FAIL verdicts into actionable tickets.

### What it does
When the nightly verifier produces a REJECT or FAIL:
1. Judge reads the CertBundle (all witness outputs, stderr, exit codes)
2. Classifies the failure type: dependency rot, numerical drift, timeout/hang, test flake, real bug
3. Checks lessons.md for known patterns (e.g., Python 3.13 WMI deadlock)
4. Writes a diagnosis to the project's wiki article
5. Optionally creates a task in Overmind's task queue

### Failure taxonomy
- **DependencyRot:** ImportError, ModuleNotFoundError → "pip install X" or "check version"
- **NumericalDrift:** Witness 3 FAIL with delta > tolerance → "intentional? update baseline : investigate"
- **Timeout:** likely scipy/WMI deadlock or infinite loop → check lessons.md
- **TestFlake:** intermittent failures → increase timeout or mark as flaky
- **RealBug:** consistent failure across witnesses → needs human attention

### Implementation approach
- New module: `overmind/diagnosis/judge.py`
- Pattern matching on stderr + exit code (no LLM needed for most cases)
- Falls back to LLM (haiku) for ambiguous failures
- Output: diagnosis record added to wiki article + optional task creation

---

## Phase 4: Evolution Manager [AFTER JUDGE]

Distills successful strategies into procedural memory — the system that makes Overmind learn *how* to fix things, not just *what* broke.

### What it does
After judge diagnoses failures and fixes are applied:
1. Tracks which diagnosis → fix pairs actually worked
2. Extracts procedural recipes: "when ImportError on scipy.stats → monkey-patch platform._wmi_query"
3. Stores recipes in wiki as "Procedures" articles
4. Next time same failure pattern appears, recommends the proven fix

### This replaces
- Current heuristic memory (low-value "ValueError 178x" records)
- Current dream engine consolidation (primitive word-overlap merging)
- Manual lessons.md curation (recipes auto-discovered from outcomes)

### Implementation approach
- Extends wiki compiler with a "Procedures" article type
- Q-router extended to track strategy outcomes (not just runner outcomes)
- Feedback loop: judge diagnosis → fix applied → verify again → strategy memory updated

---

## Dependency Chain

```
Phase 1 (TruthCert)     ← DONE
    ↓
Phase 2 (Wiki Compiler)  ← NEXT — reads CertBundles, writes structured Markdown
    ↓
Phase 3 (Judge Agent)    ← reads wiki + bundles, writes diagnoses
    ↓
Phase 4 (Evolution Mgr)  ← reads judge outcomes, writes procedural recipes
```

Each phase is independently valuable. Phase 2 alone transforms the nightly report from ephemeral logs into a persistent, growing knowledge base.
