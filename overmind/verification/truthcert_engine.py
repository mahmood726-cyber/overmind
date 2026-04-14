"""TruthCertEngine: multi-witness verification orchestrator."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from overmind.storage.models import ProjectRecord, utc_now
from overmind.verification.cert_bundle import Arbitrator, CertBundle
from overmind.verification.failure_taxonomy import classify_bundle
from overmind.verification.preflight import PreflightChecker
from overmind.verification.scope_lock import ScopeLock, WitnessResult, compute_tier
from overmind.verification.witnesses import (
    NumericalWitness,
    SmokeWitness,
    SuiteWitness,
)


class TruthCertEngine:
    def __init__(
        self,
        baselines_dir: Path,
        test_timeout: int = 120,
        smoke_timeout: int = 10,
        numerical_timeout: int = 30,
    ) -> None:
        self.baselines_dir = baselines_dir
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
        self.test_suite_witness = SuiteWitness(timeout=test_timeout)
        self.smoke_witness = SmokeWitness(timeout=smoke_timeout)
        self.numerical_witness = NumericalWitness(timeout=numerical_timeout)
        self.arbitrator = Arbitrator()
        self.preflight = PreflightChecker()

    def build_scope_lock(self, project: ProjectRecord) -> ScopeLock:
        tier = compute_tier(project.risk_profile, project.advanced_math_score)
        test_command = project.test_commands[0] if project.test_commands else ""
        smoke_modules = self._discover_modules(project.root_path) if tier >= 2 else ()
        baseline_path = self._find_baseline(project.project_id) if tier >= 3 else None
        source_hash = self._hash_source_files(project.root_path)

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
        lock = self.build_scope_lock(project)

        # Preflight: catch missing ingredients before we spend witness time.
        # Converts the largest observed nightly failure class (missing baseline,
        # missing module, missing path) from a generic FAIL into a typed verdict
        # the dream engine can aggregate and surface.
        preflight = self.preflight.check(
            root_path=lock.project_path,
            test_command=lock.test_command,
            smoke_modules=lock.smoke_modules,
            baseline_path=lock.baseline_path,
            tier=lock.witness_count,
        )
        if not preflight.ready:
            synthetic = WitnessResult(
                witness_type="preflight",
                verdict="FAIL",
                exit_code=-1,
                stdout="",
                stderr=preflight.to_witness_stderr(),
                elapsed=0.0,
            )
            return CertBundle(
                project_id=project.project_id,
                scope_lock=lock,
                witness_results=[synthetic],
                verdict="FAIL",
                arbitration_reason=f"Preflight failed: {preflight.failure_class}",
                timestamp=utc_now(),
                failure_class=preflight.failure_class,
            )

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
        # Always call smoke_witness.run so mocks can intercept; it handles empty list internally.
        if lock.witness_count >= 2:
            results.append(self.smoke_witness.run(
                list(lock.smoke_modules), lock.project_path,
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

        # Single retry for REJECT: re-run failing witness once to filter transient flakes
        if verdict == "REJECT":
            failed_indices = [i for i, r in enumerate(results) if r.verdict == "FAIL"]
            for idx in failed_indices:
                orig = results[idx]
                if orig.witness_type == "test_suite" and lock.test_command:
                    retry = self.test_suite_witness.run(lock.test_command, lock.project_path)
                elif orig.witness_type == "smoke":
                    retry = self.smoke_witness.run(list(lock.smoke_modules), lock.project_path)
                elif orig.witness_type == "numerical" and lock.baseline_path:
                    retry = self.numerical_witness.run(lock.baseline_path, lock.project_path)
                else:
                    continue
                if retry.verdict == "PASS":
                    results[idx] = retry  # Transient flake; use retry result.
            verdict, reason = self.arbitrator.arbitrate(results)
            if verdict != "REJECT":
                reason = f"{reason} (upgraded after retry)"

        failure_class = classify_bundle(results) if verdict in {"FAIL", "REJECT"} else None
        return CertBundle(
            project_id=project.project_id,
            scope_lock=lock,
            witness_results=results,
            verdict=verdict,
            arbitration_reason=reason,
            timestamp=utc_now(),
            failure_class=failure_class,
        )

    # Directories containing scripts/examples/dev tools; not importable modules.
    _SKIP_DIR_NAMES = {
        "test",
        "tests",
        "node_modules",
        "scripts",
        "examples",
        "dev",
        "docs",
        "data",
        "fixtures",
        "migrations",
        "backup",
        "archive",
    }
    # Root-level files that are scripts, not importable modules.
    _SKIP_FILES = {"setup", "conftest", "manage", "run", "main", "cli", "app",
                   "noxfile", "fabfile", "tasks"}
    _JS_SUFFIXES = {".js", ".mjs", ".cjs"}
    _VALID_MODULE_RE = re.compile(r"^[A-Za-z_]\w*$")
    _HASHABLE_SUFFIXES = {".py", ".html", ".js", ".mjs", ".cjs"}

    def _discover_modules(self, root_path: str) -> list[str]:
        root = Path(root_path)
        if not root.exists() or not root.is_dir():
            return []

        targets: list[str] = []
        seen: set[str] = set()

        def add_target(target: str) -> None:
            if target and target not in seen:
                seen.add(target)
                targets.append(target)

        def valid_module_name(name: str) -> bool:
            return bool(self._VALID_MODULE_RE.fullmatch(name))

        def skipped_dir(name: str) -> bool:
            lowered = name.lower()
            return lowered.startswith(".") or lowered.startswith("_") or lowered in self._SKIP_DIR_NAMES

        # Import package roots and nested modules from repo root and src/ when present.
        for base in [root, root / "src"]:
            if not base.exists() or not base.is_dir():
                continue
            for py_file in sorted(base.rglob("*.py")):
                try:
                    relative = py_file.relative_to(base)
                except ValueError:
                    continue
                parent_parts = relative.parts[:-1]
                if any(skipped_dir(part) or not valid_module_name(part) for part in parent_parts):
                    continue
                name = py_file.stem
                if name == "__init__":
                    if parent_parts:
                        add_target(f"py:{'.'.join(parent_parts)}")
                    continue
                if name.startswith("_") or name in self._SKIP_FILES or not valid_module_name(name):
                    continue
                add_target(f"py:{'.'.join([*parent_parts, name])}")

        # For browser/JS projects, smoke-check syntax for nested JS files outside ignored dirs.
        for suffix in sorted(self._JS_SUFFIXES):
            for js_file in sorted(root.rglob(f"*{suffix}")):
                try:
                    relative = js_file.relative_to(root)
                except ValueError:
                    continue
                if any(skipped_dir(part) for part in relative.parts[:-1]):
                    continue
                add_target(f"js:{relative.as_posix()}")

        return targets[:40]

    def _find_baseline(self, project_id: str) -> str | None:
        path = self.baselines_dir / f"{project_id}.json"
        return str(path) if path.exists() else None

    @staticmethod
    def _safe_rglob(root: Path):
        """Walk `root` yielding file paths while swallowing OSError from reparse
        points, broken symlinks, and OneDrive "Files On-Demand" placeholders.

        `Path.rglob` on Windows may raise mid-iteration when scandir hits an
        inaccessible directory; that aborts the hash pass. os.walk with an
        onerror callback lets us log-and-continue instead.
        """
        import os as _os

        def _on_error(_exc: OSError) -> None:
            return None  # skip unreadable subtrees

        for dirpath, _dirnames, filenames in _os.walk(
            str(root), onerror=_on_error, followlinks=False
        ):
            for name in filenames:
                yield Path(dirpath) / name

    def _hash_source_files(self, root_path: str) -> str:
        """Hash source, test, and JS/HTML files to detect any code change."""
        hasher = hashlib.sha256()
        root = Path(root_path)
        files: list[Path] = []
        for path in self._safe_rglob(root):
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if any(
                part.startswith(".") or part in {"node_modules", "__pycache__", ".git"}
                for part in relative.parts[:-1]
            ):
                continue
            try:
                if not path.is_file():
                    continue
            except OSError:
                # Broken symlinks, restricted files, OneDrive placeholders (WinError 1920),
                # etc. — skip rather than abort the entire hash pass.
                continue
            if path.suffix.lower() in self._HASHABLE_SUFFIXES or re.match(r"^(test_.*|.*_test)\.py$", path.name):
                files.append(path)
        for file_path in sorted(files, key=lambda p: str(p))[:500]:
            try:
                hasher.update(file_path.read_bytes())
            except OSError:
                continue
        return hasher.hexdigest()[:16]
