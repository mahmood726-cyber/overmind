# TruthCert Verification Backbone — Design Spec

**Date:** 2026-04-07
**Status:** APPROVED
**Location:** `C:\overmind\` (extends existing Overmind v3.0.0)
**Depends on:** TruthCert spec at `C:\Projects\Burhan\TruthCert_v3.1.0-FINAL_Public_Frozen.md`

## 1. Purpose

Replace Overmind's single-witness verification (run pytest, check exit code) with a TruthCert-inspired multi-witness engine that produces three-tier verdicts (CERTIFIED / REJECT / FAIL) with scope locks and fail-closed semantics. The nightly verifier becomes a certified portfolio audit, not just a pass/fail report.

## 2. Architecture

```
nightly_verify.py
  └── TruthCertEngine (new)
        ├── Witness 1: TestSuiteWitness (existing — runs pytest/npm test)
        ├── Witness 2: SmokeWitness (new — import check + minimal run)
        ├── Witness 3: NumericalWitness (new — fixture snapshot comparison)
        ├── ScopeLock (new — immutable task definition)
        ├── Arbitrator (new — compares witness verdicts, fail-closed)
        └── CertBundle (new — packages results as TruthCert bundle)
```

### Tiered witness assignment

| Condition | Witnesses | Count |
|-----------|-----------|-------|
| `risk_profile == "high" and advanced_math_score >= 10` | TestSuite + Smoke + Numerical | 3 |
| `risk_profile in ("high", "medium_high")` | TestSuite + Smoke | 2 |
| Everything else | TestSuite only | 1 |

### Files

- Create: `overmind/verification/truthcert_engine.py` — orchestrates witnesses, delegates to arbitrator
- Create: `overmind/verification/witnesses.py` — TestSuiteWitness, SmokeWitness, NumericalWitness
- Create: `overmind/verification/scope_lock.py` — immutable scope definition
- Create: `overmind/verification/cert_bundle.py` — output bundle with hash
- Modify: `overmind/verification/verifier.py` — delegate to TruthCertEngine
- Modify: `scripts/nightly_verify.py` — use new engine, richer reports
- Create: `data/baselines/` directory — numerical snapshots per project

## 3. Scope Lock

Frozen at task creation, immutable during verification:

```python
@dataclass(frozen=True)
class ScopeLock:
    project_id: str
    project_path: str
    risk_profile: str
    witness_count: int          # 1, 2, or 3 based on tier
    test_command: str           # primary test suite command
    smoke_modules: list[str]    # Python modules to import-check (auto-discovered)
    baseline_path: str | None   # path to numerical snapshot, if exists
    expected_outcome: str       # "pass" — what a healthy project should do
    source_hash: str            # SHA-256 of project's test files at verification time
    created_at: str
```

`source_hash` is SHA-256 of all `test_*.py` / `*_test.py` files in the project's test directory. If someone modifies tests to hide a failure, the hash changes and the bundle records it.

### Smoke module auto-discovery

Scan project root + one level deep for `*.py` files. Extract importable module names. For HTML-only projects, scan for `.js` files and validate with `node -c`. Store discovered list in `smoke_modules` field.

## 4. Witnesses

### Witness 1 — TestSuiteWitness

Runs `project.test_commands[0]` via subprocess. Same logic as current `VerificationEngine._run_command`.

Returns: `WitnessResult(witness_type="test_suite", verdict=PASS|FAIL, exit_code, stdout, stderr, elapsed)`

Timeout: inherited from nightly_verify (default 120s).

### Witness 2 — SmokeWitness

For each module in `scope_lock.smoke_modules`, runs:
```
python -c "import {module_name}"
```

For HTML/JS projects, runs:
```
node -c "$(cat {js_file})"
```

Returns PASS if all imports/parses succeed. Returns FAIL if any crash with ImportError, SyntaxError, or ModuleNotFoundError.

Timeout: 10 seconds total per project.

### Witness 3 — NumericalWitness

Looks for `data/baselines/{project_id}.json` containing:
```json
{
  "project_id": "bayesianma-240f4a74",
  "created_at": "2026-04-08T03:00:00Z",
  "command": "python -c \"from engine import run; print(run('fixture.json'))\"",
  "values": {
    "tau2": 0.0412,
    "pooled_effect": -0.234,
    "i_squared": 45.2,
    "prediction_interval_lower": -0.89,
    "prediction_interval_upper": 0.42
  },
  "tolerance": 1e-6
}
```

Runs the `command`, parses output values, compares each against snapshot with tolerance. Returns PASS if all within tolerance, FAIL if any drift, SKIP if no baseline file exists.

Timeout: 30 seconds per project.

### Baseline creation

Run nightly_verify with `--create-baselines` flag. For each high-risk math project:
1. Run the project's baseline command (defined in project CLAUDE.md or auto-detected)
2. Save output values to `data/baselines/{project_id}.json`
3. Never runs automatically — manual only, to prevent locking in bad values

## 5. Arbitrator

Compares witness verdicts using fail-closed logic:

| W1 (TestSuite) | W2 (Smoke) | W3 (Numerical) | Verdict | Reason |
|----------------|------------|----------------|---------|--------|
| PASS | PASS | PASS | CERTIFIED | All witnesses agree |
| PASS | PASS | SKIP | CERTIFIED | No baseline, available witnesses agree |
| PASS | FAIL | any | REJECT | Tests pass but imports fail |
| FAIL | PASS | any | REJECT | Tests fail but imports OK (flaky tests?) |
| FAIL | FAIL | any | FAIL | Clean failure — project broken |
| PASS | PASS | FAIL | REJECT | Numerical drift despite passing tests |
| any | SKIP | SKIP | Single-witness fallback (current behavior) |

**REJECT vs FAIL:**
- FAIL = project is genuinely broken, all witnesses agree
- REJECT = witnesses disagree, investigation needed — this is the most valuable signal

SKIP witnesses don't count as disagreement. A project with only 1 non-SKIP witness falls through to single-witness logic (PASS or FAIL, never CERTIFIED or REJECT).

## 6. Cert Bundle

Output per project verification:

```python
@dataclass
class CertBundle:
    project_id: str
    scope_lock: ScopeLock
    witness_results: list[WitnessResult]
    verdict: str              # CERTIFIED | REJECT | FAIL | PASS (single-witness)
    arbitration_reason: str   # e.g. "3/3 agree" or "W1 PASS vs W3 FAIL: numerical drift"
    timestamp: str
    bundle_hash: str          # SHA-256 of all fields above, serialized deterministically
```

Bundles are saved to `data/nightly_reports/bundles/{date}/{project_id}.json`.

`bundle_hash` is computed from the JSON-serialized bundle with sorted keys, excluding the `bundle_hash` field itself. Deterministic — same inputs always produce same hash.

## 7. Morning Report Upgrade

```markdown
# Nightly Verification Report - 2026-04-08

**32/50 CERTIFIED** | 3 FAIL | 2 REJECT | 13 single-witness (PASS) | 40min total

## REJECT (investigate — witnesses disagree)

### MetaGuard — W1 PASS vs W3 FAIL
- Witness 1 (test suite): PASS in 22.8s
- Witness 3 (numerical): tau2 drifted 0.0412 → 0.0398 (delta=0.0014, tol=1e-6)
- Scope hash: a3f8c2... (unchanged from last night)
- **Action:** Intentional change? Run `--create-baselines`. Bug? Investigate.

### idea12 — W1 PASS vs W2 FAIL
- Witness 1 (test suite): PASS in 4.2s
- Witness 2 (smoke): FAIL — ImportError: scipy.optimize (module removed?)
- **Action:** Check if scipy was uninstalled or version changed.

## FAIL (broken — witnesses agree)

### MetaRepair — 2/2 FAIL
- Witness 1 (test suite): TIMEOUT after 120s
- Witness 2 (smoke): FAIL — ImportError: scipy.stats
- **Action:** Known Python 3.13 WMI deadlock? Check lessons.md.

## CERTIFIED (healthy)

| Project | Witnesses | Time | Bundle Hash |
|---------|-----------|------|-------------|
| BayesianMA | 3/3 PASS | 24.1s | c7e2f1... |
| CardioOracle | 3/3 PASS | 8.2s | 91ab3d... |
| MetaRep | 2/2 PASS | 16.3s | f4d820... |
...
```

## 8. Testing

Tests added to `C:\OvermindTestBed\`:

| File | Tests | Description |
|------|-------|-------------|
| test_scope_lock.py | 3 | Frozen/immutable, source_hash computed, tier logic correct |
| test_witnesses.py | 6 | TestSuiteWitness real pytest, SmokeWitness catches ImportError, NumericalWitness detects drift + handles missing baseline + SKIP |
| test_arbitrator.py | 5 | All 7 verdict combos, REJECT vs FAIL distinction, SKIP passthrough |
| test_cert_bundle.py | 3 | Hash deterministic, all fields populated, JSON serialization |
| test_truthcert_engine.py | 4 | Tiered witness selection (1/2/3), full pipeline with stubs, fail-closed on disagreement |
| **Total** | **21** | Combined with existing 53 = **74 total** |

## 9. Constraints

- Never modify project source files during verification
- Nightly run must stay under 60 minutes for 50 projects (~72s budget per project)
- SmokeWitness timeout: 10 seconds per project
- NumericalWitness timeout: 30 seconds per project
- Baselines in `data/baselines/` — not committed to project repos
- `--create-baselines` is manual only, never automatic
- SKIP witnesses don't count as disagreement (graceful degradation)
- Single-witness projects return PASS/FAIL (not CERTIFIED/REJECT) for backward compatibility

## 10. What This Does NOT Include (Future Work)

- Judge agent for automated failure diagnosis (next sub-project)
- Evolution manager / procedural memory (depends on judge)
- Full provenance hash chains linking nightly reports across days
- Domain-specific validator packs (meta-analysis math checks as a witness)
- Automatic baseline refresh after intentional changes
