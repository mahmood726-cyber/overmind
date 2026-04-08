# Judge Agent Design Spec

**Date:** 2026-04-07
**Status:** APPROVED
**Phase:** 3 of Overmind v4

## 1. Purpose

Automated failure diagnosis that turns REJECT/FAIL verdicts into classified, actionable diagnoses. Pattern-matches stderr/exit codes against known failure types, writes diagnoses to wiki articles, and optionally queues fix tasks.

## 2. Architecture

```
nightly_verify.py
  └── After wiki compile, call:
      Judge.diagnose(bundle, project) → Diagnosis
        ├── PatternMatcher: classify failure from stderr + exit code + lessons.md patterns
        ├── Write diagnosis to wiki article's Notes section
        └── Optionally create task in Overmind's task queue
```

### Files
- Create: `overmind/diagnosis/__init__.py`
- Create: `overmind/diagnosis/judge.py` — Judge class + PatternMatcher
- Create: `overmind/diagnosis/taxonomy.py` — failure type definitions
- Modify: `scripts/nightly_verify.py` — call judge after wiki compile
- Test: `C:\OvermindTestBed\tests\test_judge.py`

## 3. Failure Taxonomy

| Type | Pattern | Example | Recommended Action |
|------|---------|---------|-------------------|
| `DEPENDENCY_ROT` | ImportError, ModuleNotFoundError | `ImportError: scipy.stats` | `pip install {module}` or check version |
| `NUMERICAL_DRIFT` | Witness 3 FAIL + "drift" in stderr | `tau2: 0.04 -> 0.039` | Update baseline if intentional, investigate if not |
| `TIMEOUT` | exit_code == -1 + "timed out" | `Timed out after 120s` | Check for WMI deadlock (Python 3.13), infinite loop |
| `SYNTAX_ERROR` | SyntaxError in stderr | `SyntaxError: invalid syntax` | Fix the syntax error |
| `TEST_FAILURE` | exit_code != 0 + "FAILED" in stdout | `3 failed, 27 passed` | Read test output, fix failing tests |
| `MISSING_FIXTURE` | FileNotFoundError, "No such file" | `FileNotFoundError: data/fixture.json` | Restore missing fixture file |
| `FLAKY` | Same project alternates PASS/FAIL in history | PASS, FAIL, PASS in last 3 runs | Mark as flaky, increase timeout |
| `UNKNOWN` | No pattern matches | — | Manual investigation needed |

## 4. Diagnosis Model

```python
@dataclass
class Diagnosis:
    project_id: str
    failure_type: str          # From taxonomy
    confidence: float          # 0.0-1.0
    summary: str               # One-line human-readable
    evidence: list[str]        # stderr excerpts that matched
    recommended_action: str    # What to do
    witness_type: str          # Which witness failed
    created_at: str
```

## 5. Pattern Matching

PatternMatcher scans witness results in priority order:
1. Check stderr for ImportError/ModuleNotFoundError → `DEPENDENCY_ROT`
2. Check stderr for "drift" or "delta=" → `NUMERICAL_DRIFT`
3. Check stderr for "timed out" or exit_code == -1 → `TIMEOUT`
4. Check stderr for SyntaxError → `SYNTAX_ERROR`
5. Check stderr for "No such file" or FileNotFoundError → `MISSING_FIXTURE`
6. Check stdout for "failed" + exit_code != 0 → `TEST_FAILURE`
7. Check wiki history for alternating PASS/FAIL → `FLAKY`
8. Fallback → `UNKNOWN`

Confidence: exact pattern match = 0.9, partial match = 0.7, fallback = 0.3.

## 6. Integration

After wiki compile in nightly_verify.py, for each REJECT/FAIL bundle:
```python
judge = Judge()
diagnosis = judge.diagnose(bundle, project, history)
# Diagnosis written to wiki article Notes section
# Optionally: queue task
```

## 7. Testing

| Test | What it proves |
|------|----------------|
| test_dependency_rot_detected | ImportError in stderr → DEPENDENCY_ROT |
| test_numerical_drift_detected | "drift" in stderr → NUMERICAL_DRIFT |
| test_timeout_detected | exit_code -1 + "timed out" → TIMEOUT |
| test_test_failure_detected | "failed" in stdout → TEST_FAILURE |
| test_flaky_detected | Alternating history → FLAKY |
| test_unknown_fallback | No pattern → UNKNOWN |
| test_certified_returns_none | CERTIFIED bundle → no diagnosis |

7 tests. Combined with 80 = **87 total**.

## 8. Constraints
- No LLM calls — pure pattern matching
- Only diagnoses REJECT and FAIL bundles (CERTIFIED/PASS skip)
- Confidence always reported (never claim certainty)
- Evidence excerpts capped at 200 chars
