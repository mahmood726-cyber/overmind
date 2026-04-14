"""Verification readiness preflight.

Closes the largest observed nightly failure class by catching missing
ingredients BEFORE the verifier runs: if `root_path` doesn't exist, if
`test_commands[0]` can't resolve, if smoke modules won't import, or if a
tier-3 baseline is missing, emit a fail-closed verdict with a typed
`failure_class` instead of running the witnesses and reporting a generic
timeout or WinError.

Design notes:
- Cheap checks only. Path existence + `shutil.which` + file-exists for
  baselines. We explicitly do NOT import smoke modules here because that
  is the smoke witness's job; we just check each module-path resolves to
  a file so a missing-file variant is caught up front.
- Errors are typed via `failure_class` strings consumed by the failure
  taxonomy (`overmind.verification.failure_taxonomy`). Keep class names
  stable — they're aggregated across nights.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from overmind.subprocess_utils import split_command


@dataclass(slots=True)
class PreflightResult:
    ready: bool
    failure_class: str | None = None
    details: list[str] = field(default_factory=list)
    checked: dict[str, bool] = field(default_factory=dict)

    def to_witness_stderr(self) -> str:
        """Render for embedding in a PreflightWitness FAIL stderr."""
        lines = [f"preflight: {self.failure_class or 'unknown'}"]
        lines.extend(f"  - {d}" for d in self.details)
        return "\n".join(lines)


class PreflightChecker:
    """Fail-closed gate: verify ingredients before running any witness."""

    def check(
        self,
        root_path: str,
        test_command: str,
        smoke_modules: tuple[str, ...] | list[str] = (),
        baseline_path: str | None = None,
        tier: int = 1,
    ) -> PreflightResult:
        result = PreflightResult(ready=True)

        # 1. Root path must exist and be a directory.
        root = Path(root_path)
        result.checked["root_path"] = False
        if not root.exists():
            result.ready = False
            result.failure_class = "missing_path"
            result.details.append(f"root_path does not exist: {root_path}")
            return result
        if not root.is_dir():
            result.ready = False
            result.failure_class = "missing_path"
            result.details.append(f"root_path is not a directory: {root_path}")
            return result
        result.checked["root_path"] = True

        # 2. Test command must be non-empty and its executable resolvable.
        result.checked["test_command"] = False
        if not test_command:
            result.ready = False
            result.failure_class = "missing_test_command"
            result.details.append("no test_command configured for project")
            return result
        try:
            parts = split_command(test_command)
        except (ValueError, OSError) as exc:
            result.ready = False
            result.failure_class = "missing_test_command"
            result.details.append(f"test_command unparseable: {exc}")
            return result
        if not parts:
            result.ready = False
            result.failure_class = "missing_test_command"
            result.details.append("test_command parsed to empty argv")
            return result
        executable = parts[0]
        # Absolute paths are verified by existence; other names by shutil.which.
        exec_path = Path(executable)
        if exec_path.is_absolute():
            if not exec_path.exists():
                result.ready = False
                result.failure_class = "missing_executable"
                result.details.append(f"test_command executable not found: {executable}")
                return result
        else:
            resolved = shutil.which(executable)
            if resolved is None:
                result.ready = False
                result.failure_class = "missing_executable"
                result.details.append(f"test_command executable not on PATH: {executable}")
                return result
        result.checked["test_command"] = True

        # 3. Tier 2+: smoke modules must resolve to files (don't import here).
        if tier >= 2 and smoke_modules:
            result.checked["smoke_modules"] = False
            missing = []
            for module in smoke_modules:
                if module.startswith("js:"):
                    rel = module.split(":", 1)[1]
                    if not (root / rel).exists():
                        missing.append(rel)
                elif module.startswith("py:"):
                    dotted = module.split(":", 1)[1]
                    parts_path = dotted.split(".")
                    candidates = [
                        root.joinpath(*parts_path).with_suffix(".py"),
                        root.joinpath(*parts_path) / "__init__.py",
                        root / "src" / Path(*parts_path).with_suffix(".py"),
                        root / "src" / Path(*parts_path) / "__init__.py",
                    ]
                    if not any(c.exists() for c in candidates):
                        missing.append(module)
            if missing:
                result.ready = False
                result.failure_class = "missing_module"
                result.details.append(
                    f"{len(missing)} smoke module(s) do not resolve to a file: {missing[:5]}"
                )
                return result
            result.checked["smoke_modules"] = True

        # 4. Tier 3: baseline file must exist and parse as JSON with required keys.
        if tier >= 3:
            result.checked["baseline"] = False
            if baseline_path is None:
                result.ready = False
                result.failure_class = "missing_baseline"
                result.details.append("tier-3 project has no baseline path configured")
                return result
            baseline_file = Path(baseline_path)
            if not baseline_file.exists():
                result.ready = False
                result.failure_class = "missing_baseline"
                result.details.append(f"baseline file missing: {baseline_path}")
                return result
            try:
                payload = json.loads(baseline_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                result.ready = False
                result.failure_class = "corrupt_baseline"
                result.details.append(f"baseline unreadable: {exc}")
                return result
            if "command" not in payload or "values" not in payload:
                result.ready = False
                result.failure_class = "corrupt_baseline"
                result.details.append("baseline missing required 'command' or 'values' fields")
                return result
            result.checked["baseline"] = True

        return result
