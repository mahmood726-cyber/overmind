# TruthCert Verification Backbone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Overmind's single-witness verification with a TruthCert-inspired multi-witness engine producing CERTIFIED/REJECT/FAIL verdicts with scope locks and fail-closed semantics.

**Architecture:** New `truthcert_engine.py` orchestrates 1-3 witnesses per project based on risk tier. `witnesses.py` contains TestSuiteWitness (existing logic), SmokeWitness (import checks), and NumericalWitness (snapshot regression). `scope_lock.py` freezes verification parameters. `cert_bundle.py` packages results with deterministic hashing. Existing `verifier.py` delegates to the new engine. Tests go in OvermindTestBed.

**Tech Stack:** Python 3.13, existing Overmind modules, subprocess for witness execution, hashlib for bundle hashing, json for baselines.

---

### Task 1: ScopeLock + WitnessResult data models

**Files:**
- Create: `C:\overmind\overmind\verification\scope_lock.py`
- Test: `C:\OvermindTestBed\tests\test_scope_lock.py`

- [ ] **Step 1: Write 3 failing tests**

```python
# C:\OvermindTestBed\tests\test_scope_lock.py
"""Test ScopeLock immutability, source_hash, and tier logic."""
from __future__ import annotations

import hashlib
from pathlib import Path

from overmind.verification.scope_lock import ScopeLock, WitnessResult, compute_tier


def test_scope_lock_is_frozen():
    """ScopeLock fields cannot be changed after creation."""
    lock = ScopeLock(
        project_id="test_proj",
        project_path="C:\\test",
        risk_profile="high",
        witness_count=3,
        test_command="python -m pytest tests/ -q",
        smoke_modules=["engine", "utils"],
        baseline_path=None,
        expected_outcome="pass",
        source_hash="abc123",
        created_at="2026-04-07T00:00:00Z",
    )
    try:
        lock.project_id = "changed"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass  # Expected — frozen dataclass


def test_compute_tier_high_math_gets_3():
    """High risk + advanced_math_score >= 10 -> 3 witnesses."""
    assert compute_tier("high", 20) == 3
    assert compute_tier("high", 10) == 3
    assert compute_tier("high", 9) == 2  # below threshold
    assert compute_tier("medium_high", 20) == 2  # not high risk
    assert compute_tier("medium", 5) == 1


def test_witness_result_fields():
    """WitnessResult stores all required fields."""
    result = WitnessResult(
        witness_type="test_suite",
        verdict="PASS",
        exit_code=0,
        stdout="5 passed",
        stderr="",
        elapsed=3.2,
    )
    assert result.verdict == "PASS"
    assert result.elapsed == 3.2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_scope_lock.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'overmind.verification.scope_lock'`

- [ ] **Step 3: Implement scope_lock.py**

```python
# C:\overmind\overmind\verification\scope_lock.py
"""Immutable scope lock and witness result models for TruthCert verification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScopeLock:
    project_id: str
    project_path: str
    risk_profile: str
    witness_count: int
    test_command: str
    smoke_modules: tuple[str, ...]
    baseline_path: str | None
    expected_outcome: str
    source_hash: str
    created_at: str


@dataclass(frozen=True, slots=True)
class WitnessResult:
    witness_type: str       # "test_suite" | "smoke" | "numerical"
    verdict: str            # "PASS" | "FAIL" | "SKIP"
    exit_code: int | None
    stdout: str
    stderr: str
    elapsed: float


def compute_tier(risk_profile: str, advanced_math_score: int) -> int:
    """Determine witness count from project risk and math score."""
    if risk_profile == "high" and advanced_math_score >= 10:
        return 3
    if risk_profile in ("high", "medium_high"):
        return 2
    return 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_scope_lock.py -v`
Expected: 3 passed

Note: The test uses `smoke_modules=["engine", "utils"]` as a list but the dataclass expects a tuple. The test should use `smoke_modules=("engine", "utils")` or the implementation should accept both. Since frozen dataclasses need hashable fields, tuple is correct. **Fix the test to use tuples.**

- [ ] **Step 5: Commit**

```bash
cd C:\overmind && git add overmind/verification/scope_lock.py && git commit -m "feat: ScopeLock + WitnessResult data models"
cd C:\OvermindTestBed && git add tests/test_scope_lock.py && git commit -m "test: scope lock — frozen, tier logic, witness result fields"
```

---

### Task 2: Three witness classes

**Files:**
- Create: `C:\overmind\overmind\verification\witnesses.py`
- Test: `C:\OvermindTestBed\tests\test_witnesses.py`

- [ ] **Step 1: Write 6 failing tests**

```python
# C:\OvermindTestBed\tests\test_witnesses.py
"""Test the three witness types: TestSuite, Smoke, Numerical."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from overmind.verification.witnesses import (
    TestSuiteWitness,
    SmokeWitness,
    NumericalWitness,
)


CARDIOORACLE_ROOT = Path("C:/Models/CardioOracle")


def test_test_suite_witness_passes_real_pytest(tmp_path):
    """TestSuiteWitness runs real CardioOracle curation tests."""
    witness = TestSuiteWitness(timeout=120)
    result = witness.run(
        command="python -m pytest tests/test_curation.py -q",
        cwd=str(CARDIOORACLE_ROOT),
    )
    assert result.witness_type == "test_suite"
    assert result.verdict == "PASS"
    assert result.exit_code == 0


def test_test_suite_witness_detects_failure(tmp_path):
    """TestSuiteWitness returns FAIL for a failing command."""
    witness = TestSuiteWitness(timeout=30)
    result = witness.run(
        command='python -c "raise SystemExit(1)"',
        cwd=str(tmp_path),
    )
    assert result.verdict == "FAIL"
    assert result.exit_code == 1


def test_smoke_witness_passes_clean_modules(tmp_path):
    """SmokeWitness PASS when all modules import successfully."""
    # Create a simple importable module
    (tmp_path / "good_module.py").write_text("X = 42\n", encoding="utf-8")
    witness = SmokeWitness(timeout=10)
    result = witness.run(
        modules=["good_module"],
        cwd=str(tmp_path),
    )
    assert result.verdict == "PASS"


def test_smoke_witness_catches_import_error(tmp_path):
    """SmokeWitness FAIL when a module has an ImportError."""
    (tmp_path / "bad_module.py").write_text("import nonexistent_package_xyz\n", encoding="utf-8")
    witness = SmokeWitness(timeout=10)
    result = witness.run(
        modules=["bad_module"],
        cwd=str(tmp_path),
    )
    assert result.verdict == "FAIL"
    assert "nonexistent_package_xyz" in result.stderr or "nonexistent_package_xyz" in result.stdout


def test_numerical_witness_passes_matching_snapshot(tmp_path):
    """NumericalWitness PASS when output matches baseline."""
    baseline = {
        "command": f'python -c "import json; print(json.dumps(dict(tau2=0.04, effect=-0.23)))"',
        "values": {"tau2": 0.04, "effect": -0.23},
        "tolerance": 1e-4,
    }
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    witness = NumericalWitness(timeout=30)
    result = witness.run(
        baseline_path=str(baseline_path),
        cwd=str(tmp_path),
    )
    assert result.verdict == "PASS"


def test_numerical_witness_detects_drift(tmp_path):
    """NumericalWitness FAIL when output drifts from baseline."""
    baseline = {
        "command": f'python -c "import json; print(json.dumps(dict(tau2=0.99, effect=-0.23)))"',
        "values": {"tau2": 0.04, "effect": -0.23},
        "tolerance": 1e-6,
    }
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    witness = NumericalWitness(timeout=30)
    result = witness.run(
        baseline_path=str(baseline_path),
        cwd=str(tmp_path),
    )
    assert result.verdict == "FAIL"
    assert "tau2" in result.stderr or "tau2" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_witnesses.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement witnesses.py**

```python
# C:\overmind\overmind\verification\witnesses.py
"""Three witness types for TruthCert multi-witness verification."""
from __future__ import annotations

import json
import subprocess
import sys
import time

from overmind.verification.scope_lock import WitnessResult

PYTHON_EXE = sys.executable


class TestSuiteWitness:
    """Witness 1: runs the project's test suite command."""

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout

    def run(self, command: str, cwd: str) -> WitnessResult:
        start = time.time()
        try:
            proc = subprocess.run(
                command, cwd=cwd, shell=True,
                capture_output=True, text=True, timeout=self.timeout,
            )
            elapsed = time.time() - start
            verdict = "PASS" if proc.returncode == 0 else "FAIL"
            return WitnessResult(
                witness_type="test_suite", verdict=verdict,
                exit_code=proc.returncode,
                stdout=proc.stdout[-2000:], stderr=proc.stderr[-2000:],
                elapsed=round(elapsed, 2),
            )
        except subprocess.TimeoutExpired:
            return WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Timed out after {self.timeout}s",
                elapsed=round(time.time() - start, 2),
            )
        except OSError as exc:
            return WitnessResult(
                witness_type="test_suite", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Failed to start: {exc}",
                elapsed=round(time.time() - start, 2),
            )


class SmokeWitness:
    """Witness 2: import-checks all discovered Python modules."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def run(self, modules: list[str], cwd: str) -> WitnessResult:
        if not modules:
            return WitnessResult(
                witness_type="smoke", verdict="SKIP", exit_code=None,
                stdout="", stderr="No modules to check",
                elapsed=0.0,
            )
        start = time.time()
        failures: list[str] = []
        for module in modules:
            try:
                proc = subprocess.run(
                    [PYTHON_EXE, "-c", f"import {module}"],
                    cwd=cwd, capture_output=True, text=True,
                    timeout=self.timeout,
                )
                if proc.returncode != 0:
                    failures.append(f"{module}: {proc.stderr.strip()[-200:]}")
            except subprocess.TimeoutExpired:
                failures.append(f"{module}: import timed out")
            except OSError as exc:
                failures.append(f"{module}: {exc}")

        elapsed = round(time.time() - start, 2)
        if failures:
            return WitnessResult(
                witness_type="smoke", verdict="FAIL", exit_code=1,
                stdout="", stderr="\n".join(failures),
                elapsed=elapsed,
            )
        return WitnessResult(
            witness_type="smoke", verdict="PASS", exit_code=0,
            stdout=f"{len(modules)} modules imported OK",
            stderr="", elapsed=elapsed,
        )


class NumericalWitness:
    """Witness 3: compares output values against a saved baseline snapshot."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def run(self, baseline_path: str, cwd: str) -> WitnessResult:
        from pathlib import Path

        path = Path(baseline_path)
        if not path.exists():
            return WitnessResult(
                witness_type="numerical", verdict="SKIP", exit_code=None,
                stdout="", stderr=f"No baseline at {baseline_path}",
                elapsed=0.0,
            )

        start = time.time()
        baseline = json.loads(path.read_text(encoding="utf-8"))
        command = baseline["command"]
        expected = baseline["values"]
        tolerance = baseline.get("tolerance", 1e-6)

        try:
            proc = subprocess.run(
                command, cwd=cwd, shell=True,
                capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Baseline command timed out after {self.timeout}s",
                elapsed=round(time.time() - start, 2),
            )
        except OSError as exc:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=-1,
                stdout="", stderr=f"Failed to start: {exc}",
                elapsed=round(time.time() - start, 2),
            )

        if proc.returncode != 0:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL",
                exit_code=proc.returncode,
                stdout=proc.stdout[-500:],
                stderr=f"Command failed: {proc.stderr.strip()[-500:]}",
                elapsed=round(time.time() - start, 2),
            )

        # Parse output as JSON
        try:
            actual = json.loads(proc.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=0,
                stdout=proc.stdout[-500:],
                stderr="Could not parse output as JSON",
                elapsed=round(time.time() - start, 2),
            )

        # Compare values
        drifts: list[str] = []
        for key, expected_val in expected.items():
            actual_val = actual.get(key)
            if actual_val is None:
                drifts.append(f"{key}: missing in output")
            elif isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                if abs(actual_val - expected_val) > tolerance:
                    drifts.append(f"{key}: {expected_val} -> {actual_val} (delta={abs(actual_val - expected_val):.2e}, tol={tolerance:.0e})")
            elif actual_val != expected_val:
                drifts.append(f"{key}: {expected_val!r} -> {actual_val!r}")

        elapsed = round(time.time() - start, 2)
        if drifts:
            return WitnessResult(
                witness_type="numerical", verdict="FAIL", exit_code=0,
                stdout=proc.stdout[-500:],
                stderr="Numerical drift: " + "; ".join(drifts),
                elapsed=elapsed,
            )
        return WitnessResult(
            witness_type="numerical", verdict="PASS", exit_code=0,
            stdout=f"{len(expected)} values within tolerance",
            stderr="", elapsed=elapsed,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_witnesses.py -v --timeout=180`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd C:\overmind && git add overmind/verification/witnesses.py && git commit -m "feat: TestSuiteWitness, SmokeWitness, NumericalWitness"
cd C:\OvermindTestBed && git add tests/test_witnesses.py && git commit -m "test: 3 witness types — test suite, smoke import, numerical drift"
```

---

### Task 3: Arbitrator

**Files:**
- Create: `C:\overmind\overmind\verification\cert_bundle.py` (contains Arbitrator + CertBundle)
- Test: `C:\OvermindTestBed\tests\test_arbitrator.py`

- [ ] **Step 1: Write 5 failing tests**

```python
# C:\OvermindTestBed\tests\test_arbitrator.py
"""Test arbitrator fail-closed logic and cert bundle hashing."""
from __future__ import annotations

from overmind.verification.scope_lock import ScopeLock, WitnessResult
from overmind.verification.cert_bundle import Arbitrator, CertBundle


def _witness(wtype, verdict):
    return WitnessResult(
        witness_type=wtype, verdict=verdict,
        exit_code=0 if verdict == "PASS" else 1,
        stdout="", stderr="", elapsed=1.0,
    )


def _lock(witness_count):
    return ScopeLock(
        project_id="test", project_path="C:\\test",
        risk_profile="high", witness_count=witness_count,
        test_command="pytest", smoke_modules=(),
        baseline_path=None, expected_outcome="pass",
        source_hash="abc", created_at="2026-04-07T00:00:00Z",
    )


def test_all_pass_is_certified():
    """3 PASS witnesses -> CERTIFIED."""
    arb = Arbitrator()
    results = [_witness("test_suite", "PASS"), _witness("smoke", "PASS"), _witness("numerical", "PASS")]
    verdict, reason = arb.arbitrate(results)
    assert verdict == "CERTIFIED"


def test_all_fail_is_fail():
    """All witnesses FAIL -> FAIL (clean failure)."""
    arb = Arbitrator()
    results = [_witness("test_suite", "FAIL"), _witness("smoke", "FAIL")]
    verdict, reason = arb.arbitrate(results)
    assert verdict == "FAIL"


def test_disagreement_is_reject():
    """W1 PASS + W2 FAIL -> REJECT (witnesses disagree)."""
    arb = Arbitrator()
    results = [_witness("test_suite", "PASS"), _witness("smoke", "FAIL")]
    verdict, reason = arb.arbitrate(results)
    assert verdict == "REJECT"


def test_numerical_drift_is_reject():
    """W1 PASS + W2 PASS + W3 FAIL -> REJECT (numerical drift)."""
    arb = Arbitrator()
    results = [_witness("test_suite", "PASS"), _witness("smoke", "PASS"), _witness("numerical", "FAIL")]
    verdict, reason = arb.arbitrate(results)
    assert verdict == "REJECT"
    assert "numerical" in reason.lower() or "drift" in reason.lower() or "disagree" in reason.lower()


def test_skip_witnesses_not_counted():
    """PASS + SKIP -> falls through to single-witness PASS."""
    arb = Arbitrator()
    results = [_witness("test_suite", "PASS"), _witness("smoke", "SKIP")]
    verdict, reason = arb.arbitrate(results)
    # With only 1 non-SKIP, can't be CERTIFIED or REJECT — falls to PASS
    assert verdict == "PASS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_arbitrator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement cert_bundle.py**

```python
# C:\overmind\overmind\verification\cert_bundle.py
"""Arbitrator (fail-closed verdict logic) and CertBundle (output with hash)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from overmind.verification.scope_lock import ScopeLock, WitnessResult


class Arbitrator:
    """Compares witness verdicts using fail-closed logic."""

    def arbitrate(self, results: list[WitnessResult]) -> tuple[str, str]:
        """Returns (verdict, reason). Verdict is CERTIFIED|REJECT|FAIL|PASS."""
        non_skip = [r for r in results if r.verdict != "SKIP"]

        if len(non_skip) == 0:
            return "SKIP", "All witnesses skipped"

        if len(non_skip) == 1:
            v = non_skip[0].verdict
            return v, f"Single witness: {non_skip[0].witness_type} {v}"

        verdicts = {r.verdict for r in non_skip}

        if verdicts == {"PASS"}:
            return "CERTIFIED", f"{len(non_skip)}/{len(non_skip)} witnesses agree PASS"

        if verdicts == {"FAIL"}:
            types = ", ".join(r.witness_type for r in non_skip)
            return "FAIL", f"All witnesses FAIL: {types}"

        # Disagreement — fail closed
        pass_witnesses = [r.witness_type for r in non_skip if r.verdict == "PASS"]
        fail_witnesses = [r.witness_type for r in non_skip if r.verdict == "FAIL"]
        return "REJECT", (
            f"Witnesses disagree: {', '.join(pass_witnesses)} PASS "
            f"vs {', '.join(fail_witnesses)} FAIL"
        )


@dataclass
class CertBundle:
    """Packages verification results with a deterministic hash."""

    project_id: str
    scope_lock: ScopeLock
    witness_results: list[WitnessResult]
    verdict: str
    arbitration_reason: str
    timestamp: str
    bundle_hash: str = ""

    def __post_init__(self) -> None:
        if not self.bundle_hash:
            self.bundle_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = {
            "project_id": self.project_id,
            "scope_lock": _frozen_to_dict(self.scope_lock),
            "witness_results": [_frozen_to_dict(w) for w in self.witness_results],
            "verdict": self.verdict,
            "arbitration_reason": self.arbitration_reason,
            "timestamp": self.timestamp,
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(encoded.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "scope_lock": _frozen_to_dict(self.scope_lock),
            "witness_results": [_frozen_to_dict(w) for w in self.witness_results],
            "verdict": self.verdict,
            "arbitration_reason": self.arbitration_reason,
            "timestamp": self.timestamp,
            "bundle_hash": self.bundle_hash,
        }


def _frozen_to_dict(obj) -> dict:
    """Convert a frozen dataclass to dict (asdict fails on slots+frozen in some versions)."""
    if hasattr(obj, "__dataclass_fields__"):
        return {name: getattr(obj, name) for name in obj.__dataclass_fields__}
    return dict(obj)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_arbitrator.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd C:\overmind && git add overmind/verification/cert_bundle.py && git commit -m "feat: Arbitrator (fail-closed) + CertBundle (hashed output)"
cd C:\OvermindTestBed && git add tests/test_arbitrator.py && git commit -m "test: arbitrator — certified, fail, reject, drift, skip passthrough"
```

---

### Task 4: CertBundle tests

**Files:**
- Test: `C:\OvermindTestBed\tests\test_cert_bundle.py`

- [ ] **Step 1: Write 3 failing tests**

```python
# C:\OvermindTestBed\tests\test_cert_bundle.py
"""Test CertBundle hashing and serialization."""
from __future__ import annotations

import json

from overmind.verification.scope_lock import ScopeLock, WitnessResult
from overmind.verification.cert_bundle import CertBundle


def _lock():
    return ScopeLock(
        project_id="test", project_path="C:\\test",
        risk_profile="high", witness_count=2,
        test_command="pytest", smoke_modules=("engine",),
        baseline_path=None, expected_outcome="pass",
        source_hash="abc123", created_at="2026-04-07T00:00:00Z",
    )


def _witness(verdict="PASS"):
    return WitnessResult(
        witness_type="test_suite", verdict=verdict,
        exit_code=0, stdout="ok", stderr="", elapsed=1.0,
    )


def test_bundle_hash_is_deterministic():
    """Same inputs produce same hash."""
    b1 = CertBundle(
        project_id="test", scope_lock=_lock(),
        witness_results=[_witness()], verdict="CERTIFIED",
        arbitration_reason="1/1 PASS", timestamp="2026-04-07T03:00:00Z",
    )
    b2 = CertBundle(
        project_id="test", scope_lock=_lock(),
        witness_results=[_witness()], verdict="CERTIFIED",
        arbitration_reason="1/1 PASS", timestamp="2026-04-07T03:00:00Z",
    )
    assert b1.bundle_hash == b2.bundle_hash
    assert len(b1.bundle_hash) == 16


def test_bundle_hash_changes_on_different_verdict():
    """Different verdict produces different hash."""
    b1 = CertBundle(
        project_id="test", scope_lock=_lock(),
        witness_results=[_witness()], verdict="CERTIFIED",
        arbitration_reason="ok", timestamp="2026-04-07T03:00:00Z",
    )
    b2 = CertBundle(
        project_id="test", scope_lock=_lock(),
        witness_results=[_witness("FAIL")], verdict="FAIL",
        arbitration_reason="broken", timestamp="2026-04-07T03:00:00Z",
    )
    assert b1.bundle_hash != b2.bundle_hash


def test_bundle_serializes_to_json():
    """to_dict produces valid JSON with all fields."""
    bundle = CertBundle(
        project_id="test", scope_lock=_lock(),
        witness_results=[_witness()], verdict="CERTIFIED",
        arbitration_reason="all pass", timestamp="2026-04-07T03:00:00Z",
    )
    d = bundle.to_dict()
    json_str = json.dumps(d)  # should not raise
    parsed = json.loads(json_str)
    assert parsed["verdict"] == "CERTIFIED"
    assert parsed["bundle_hash"] == bundle.bundle_hash
    assert parsed["scope_lock"]["project_id"] == "test"
```

- [ ] **Step 2: Run tests**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_cert_bundle.py -v`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
cd C:\OvermindTestBed && git add tests/test_cert_bundle.py && git commit -m "test: cert bundle — deterministic hash, change detection, JSON serialization"
```

---

### Task 5: TruthCertEngine orchestrator

**Files:**
- Create: `C:\overmind\overmind\verification\truthcert_engine.py`
- Test: `C:\OvermindTestBed\tests\test_truthcert_engine.py`

- [ ] **Step 1: Write 4 failing tests**

```python
# C:\OvermindTestBed\tests\test_truthcert_engine.py
"""Test TruthCertEngine orchestration: tier selection, full pipeline, fail-closed."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from overmind.storage.models import ProjectRecord
from overmind.verification.truthcert_engine import TruthCertEngine
from overmind.verification.scope_lock import WitnessResult


def _project(risk="high", math_score=20, test_cmds=None):
    return ProjectRecord(
        project_id="test_proj", name="TestProject",
        root_path="C:\\test", risk_profile=risk,
        has_advanced_math=math_score > 0,
        advanced_math_score=math_score,
        test_commands=test_cmds or ["python -m pytest tests/ -q"],
    )


def test_tier_3_runs_three_witnesses():
    """High-risk math project runs all 3 witness types."""
    engine = TruthCertEngine(baselines_dir=Path("C:/overmind/data/baselines"))
    project = _project(risk="high", math_score=20)
    lock = engine.build_scope_lock(project)
    assert lock.witness_count == 3


def test_tier_1_runs_one_witness():
    """Medium-risk project runs only test suite witness."""
    engine = TruthCertEngine(baselines_dir=Path("C:/overmind/data/baselines"))
    project = _project(risk="medium", math_score=2)
    lock = engine.build_scope_lock(project)
    assert lock.witness_count == 1


def test_full_pipeline_with_mocked_witnesses(tmp_path):
    """Full verify() returns a CertBundle with correct verdict."""
    engine = TruthCertEngine(baselines_dir=tmp_path)
    project = _project(risk="medium", math_score=2)

    def mock_test_suite_run(command, cwd):
        return WitnessResult("test_suite", "PASS", 0, "ok", "", 1.0)

    with patch.object(engine.test_suite_witness, "run", side_effect=mock_test_suite_run):
        bundle = engine.verify(project)

    assert bundle.verdict == "PASS"  # single witness, not CERTIFIED
    assert len(bundle.witness_results) == 1
    assert bundle.bundle_hash


def test_disagreement_produces_reject(tmp_path):
    """When witnesses disagree, verdict is REJECT."""
    engine = TruthCertEngine(baselines_dir=tmp_path)
    project = _project(risk="high", math_score=5)  # tier 2: test_suite + smoke

    def mock_test_run(command, cwd):
        return WitnessResult("test_suite", "PASS", 0, "ok", "", 1.0)

    def mock_smoke_run(modules, cwd):
        return WitnessResult("smoke", "FAIL", 1, "", "ImportError", 0.5)

    with patch.object(engine.test_suite_witness, "run", side_effect=mock_test_run), \
         patch.object(engine.smoke_witness, "run", side_effect=mock_smoke_run):
        bundle = engine.verify(project)

    assert bundle.verdict == "REJECT"
    assert "disagree" in bundle.arbitration_reason.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_truthcert_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement truthcert_engine.py**

```python
# C:\overmind\overmind\verification\truthcert_engine.py
"""TruthCertEngine: multi-witness verification orchestrator."""
from __future__ import annotations

import glob
import hashlib
import os
from pathlib import Path

from overmind.storage.models import ProjectRecord, utc_now
from overmind.verification.cert_bundle import Arbitrator, CertBundle
from overmind.verification.scope_lock import ScopeLock, WitnessResult, compute_tier
from overmind.verification.witnesses import (
    NumericalWitness,
    SmokeWitness,
    TestSuiteWitness,
)


class TruthCertEngine:
    """Orchestrates tiered multi-witness verification with fail-closed semantics."""

    def __init__(
        self,
        baselines_dir: Path,
        test_timeout: int = 120,
        smoke_timeout: int = 10,
        numerical_timeout: int = 30,
    ) -> None:
        self.baselines_dir = baselines_dir
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        self.test_suite_witness = TestSuiteWitness(timeout=test_timeout)
        self.smoke_witness = SmokeWitness(timeout=smoke_timeout)
        self.numerical_witness = NumericalWitness(timeout=numerical_timeout)
        self.arbitrator = Arbitrator()

    def build_scope_lock(self, project: ProjectRecord) -> ScopeLock:
        """Build an immutable scope lock from project attributes."""
        tier = compute_tier(project.risk_profile, project.advanced_math_score)
        test_command = project.test_commands[0] if project.test_commands else ""
        smoke_modules = self._discover_modules(project.root_path) if tier >= 2 else ()
        baseline_path = self._find_baseline(project.project_id) if tier >= 3 else None
        source_hash = self._hash_test_files(project.root_path)

        return ScopeLock(
            project_id=project.project_id,
            project_path=project.root_path,
            risk_profile=project.risk_profile,
            witness_count=tier,
            test_command=test_command,
            smoke_modules=tuple(smoke_modules),
            baseline_path=baseline_path,
            expected_outcome="pass",
            source_hash=source_hash,
            created_at=utc_now(),
        )

    def verify(self, project: ProjectRecord) -> CertBundle:
        """Run tiered verification and return a certified bundle."""
        lock = self.build_scope_lock(project)
        results: list[WitnessResult] = []

        # Witness 1: always run test suite
        if lock.test_command:
            results.append(self.test_suite_witness.run(lock.test_command, lock.project_path))
        else:
            results.append(WitnessResult(
                witness_type="test_suite", verdict="SKIP", exit_code=None,
                stdout="", stderr="No test command", elapsed=0.0,
            ))

        # Witness 2: smoke check (tier 2+)
        if lock.witness_count >= 2:
            if lock.smoke_modules:
                results.append(self.smoke_witness.run(
                    list(lock.smoke_modules), lock.project_path,
                ))
            else:
                results.append(WitnessResult(
                    witness_type="smoke", verdict="SKIP", exit_code=None,
                    stdout="", stderr="No modules discovered", elapsed=0.0,
                ))

        # Witness 3: numerical regression (tier 3)
        if lock.witness_count >= 3:
            if lock.baseline_path:
                results.append(self.numerical_witness.run(
                    lock.baseline_path, lock.project_path,
                ))
            else:
                results.append(WitnessResult(
                    witness_type="numerical", verdict="SKIP", exit_code=None,
                    stdout="", stderr="No baseline file", elapsed=0.0,
                ))

        verdict, reason = self.arbitrator.arbitrate(results)

        return CertBundle(
            project_id=project.project_id,
            scope_lock=lock,
            witness_results=results,
            verdict=verdict,
            arbitration_reason=reason,
            timestamp=utc_now(),
        )

    def _discover_modules(self, root_path: str) -> list[str]:
        """Find importable Python modules in project root + one level deep."""
        modules: list[str] = []
        root = Path(root_path)
        for py_file in sorted(root.glob("*.py")):
            name = py_file.stem
            if name.startswith("_") or name == "setup":
                continue
            modules.append(name)
        for py_file in sorted(root.glob("*/*.py")):
            if py_file.parent.name.startswith((".", "_", "test", "node_modules")):
                continue
            name = py_file.stem
            if name.startswith("_"):
                continue
            modules.append(f"{py_file.parent.name}.{name}")
        return modules[:20]  # cap to avoid huge import lists

    def _find_baseline(self, project_id: str) -> str | None:
        """Look for a numerical baseline file."""
        path = self.baselines_dir / f"{project_id}.json"
        return str(path) if path.exists() else None

    def _hash_test_files(self, root_path: str) -> str:
        """SHA-256 of all test files in the project."""
        hasher = hashlib.sha256()
        root = Path(root_path)
        test_files = sorted(
            list(root.glob("**/test_*.py")) + list(root.glob("**/*_test.py"))
        )
        for tf in test_files[:50]:  # cap for performance
            try:
                hasher.update(tf.read_bytes())
            except OSError:
                continue
        return hasher.hexdigest()[:16]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/OvermindTestBed && python -m pytest tests/test_truthcert_engine.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd C:\overmind && git add overmind/verification/truthcert_engine.py && git commit -m "feat: TruthCertEngine — tiered multi-witness orchestration"
cd C:\OvermindTestBed && git add tests/test_truthcert_engine.py && git commit -m "test: TruthCertEngine — tier selection, pipeline, fail-closed reject"
```

---

### Task 6: Wire into nightly_verify.py

**Files:**
- Modify: `C:\overmind\scripts\nightly_verify.py`

- [ ] **Step 1: Update nightly_verify.py to use TruthCertEngine**

Replace the `verify_project` function and report generation in `nightly_verify.py`. Key changes:

1. Import `TruthCertEngine` instead of `VerificationEngine`
2. Replace `verify_project()` to call `engine.verify(project)` returning a `CertBundle`
3. Update report to show CERTIFIED/REJECT/FAIL/PASS verdicts
4. Save bundle JSON files to `data/nightly_reports/bundles/{date}/`
5. Add `--create-baselines` flag

The full replacement for the `main()` function's verification section:

```python
# In nightly_verify.py, replace the VerificationEngine import and usage:

# OLD:
# from overmind.verification.verifier import VerificationEngine
# verifier = VerificationEngine(DATA_DIR / "artifacts", verification_timeout=args.timeout)

# NEW:
from overmind.verification.truthcert_engine import TruthCertEngine

# In main(), replace verifier creation:
engine = TruthCertEngine(
    baselines_dir=DATA_DIR / "baselines",
    test_timeout=args.timeout,
    smoke_timeout=10,
    numerical_timeout=30,
)

# Replace the verification loop body:
# OLD: task, result, elapsed = verify_project(verifier, proj, args.timeout)
# NEW:
import time as _time
start = _time.time()
bundle = engine.verify(proj)
elapsed = _time.time() - start

# Update status tracking to use bundle.verdict:
# CERTIFIED, REJECT, FAIL, PASS, SKIP
```

The full modified `nightly_verify.py` should:
- Add `--create-baselines` argument to argparse
- Use `TruthCertEngine` instead of `VerificationEngine`
- Track 4 verdict categories: certified, rejected, failed, single_pass
- Save per-project bundle JSON to `data/nightly_reports/bundles/{date}/`
- Generate upgraded markdown report with REJECT section
- Keep Q-router and memory extraction logic unchanged

- [ ] **Step 2: Test manually**

Run: `python C:\overmind\scripts\nightly_verify.py --dry-run --limit 5`
Expected: Shows 5 projects with tier info.

Run: `python C:\overmind\scripts\nightly_verify.py --limit 3 --timeout 60 --min-risk high`
Expected: Runs with CERTIFIED/REJECT/FAIL/PASS verdicts.

- [ ] **Step 3: Commit**

```bash
cd C:\overmind && git add scripts/nightly_verify.py && git commit -m "feat: nightly verifier uses TruthCertEngine with multi-witness verdicts"
```

---

### Task 7: Run full test suite + fix failures

**Files:**
- Possibly modify any test or source file that fails

- [ ] **Step 1: Run all OvermindTestBed tests**

Run: `cd /c/OvermindTestBed && python -m pytest tests/ -v --timeout=180`
Expected: 74 passed (53 existing + 21 new)

- [ ] **Step 2: Fix any failures**

Common issues:
- `smoke_modules` type mismatch: tests may pass list, ScopeLock expects tuple
- `_frozen_to_dict` may fail on tuple fields — ensure JSON serialization handles tuples
- Import paths: verify `C:\overmind` on sys.path via root conftest.py
- Real pytest witness test: CardioOracle tests must still pass (~6s)

- [ ] **Step 3: Run nightly verifier live**

Run: `python C:\overmind\scripts\nightly_verify.py --limit 5 --timeout 60 --min-risk high`
Expected: Projects show CERTIFIED (if all witnesses agree), PASS (single witness), or REJECT/FAIL.

- [ ] **Step 4: Commit**

```bash
cd C:\overmind && git add -A && git commit -m "fix: resolve test failures from full suite run"
cd C:\OvermindTestBed && git add -A && git commit -m "fix: resolve test failures from full suite run"
```

---

### Task 8: Final validation + push

- [ ] **Step 1: Run full OvermindTestBed suite**

Run: `cd /c/OvermindTestBed && python -m pytest tests/ -v --timeout=180`
Expected: 74 passed, 0 failed.

- [ ] **Step 2: Run nightly verifier with full output**

Run: `python C:\overmind\scripts\nightly_verify.py --limit 10 --timeout 120 --min-risk high`
Verify: Report at `C:\overmind\data\nightly_reports\` shows CERTIFIED/REJECT/FAIL breakdown.

- [ ] **Step 3: Commit and push both repos**

```bash
cd C:\overmind && git add -A && git commit -m "ship: TruthCert verification backbone — multi-witness, scope locks, fail-closed"
cd C:\OvermindTestBed && git add -A && git commit -m "ship: 74 tests — 21 new TruthCert witness/arbitrator/bundle tests"
```

Push both:
```bash
cd C:\overmind && git push
cd C:\OvermindTestBed && git push
```
