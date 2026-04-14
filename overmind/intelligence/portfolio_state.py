from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from overmind.storage.models import MemoryRecord, ProjectRecord, slugify

SUCCESS_VERDICTS = {"CERTIFIED", "PASS"}
FAILURE_VERDICTS = {"REJECT", "FAIL"}
PROJECT_ID_HASH_SUFFIX = re.compile(r"-[0-9a-f]{8}$", re.IGNORECASE)


def project_identity_key(
    project: ProjectRecord | None = None,
    *,
    name: str | None = None,
    project_id: str | None = None,
    root_path: str | None = None,
) -> str:
    if project is not None:
        name = project.name
        project_id = project.project_id
        root_path = project.root_path

    candidates = [
        _strip_project_hash(project_id),
        slugify(name or "") if name else "",
        slugify(Path(root_path).name) if root_path else "",
        slugify(project_id or "") if project_id else "",
    ]
    for candidate in candidates:
        if candidate and candidate != "project":
            return candidate
    return "project"


def project_identity_aliases(
    project: ProjectRecord | None = None,
    *,
    name: str | None = None,
    project_id: str | None = None,
    root_path: str | None = None,
) -> set[str]:
    if project is not None:
        name = project.name
        project_id = project.project_id
        root_path = project.root_path

    aliases = {
        project_identity_key(name=name, project_id=project_id, root_path=root_path),
    }
    if name:
        aliases.add(slugify(name))
        aliases.add(name.lower())
    if project_id:
        aliases.add(project_id.lower())
        aliases.add(_strip_project_hash(project_id))
    if root_path:
        root_name = Path(root_path).name
        aliases.add(root_name.lower())
        aliases.add(slugify(root_name))
        aliases.add(_normalize_path(root_path))
    return {alias for alias in aliases if alias}


def build_project_identity_groups(projects: list[ProjectRecord]) -> dict[str, list[ProjectRecord]]:
    groups: dict[str, list[ProjectRecord]] = {}
    for project in projects:
        groups.setdefault(project_identity_key(project), []).append(project)
    return groups


def select_representative_project(projects: list[ProjectRecord]) -> ProjectRecord:
    return max(
        projects,
        key=lambda project: (
            project_priority_score(project),
            int(bool(project.test_commands)),
            int(project.has_validation_history),
            int(project.has_oracle_benchmarks),
            -len(project.root_path),
            project.project_id,
        ),
    )


def project_priority_score(project: ProjectRecord) -> int:
    score = 0
    if project.risk_profile == "high":
        score += 10
    elif project.risk_profile == "medium_high":
        score += 5
    score += min(project.advanced_math_score, 10)
    if project.has_oracle_benchmarks:
        score += 3
    if project.has_validation_history:
        score += 2
    return score


def build_verification_state_index(
    projects: list[ProjectRecord],
    memories: list[MemoryRecord],
    artifacts_dir: Path,
) -> dict[str, dict[str, str]]:
    alias_map = _project_identity_alias_map(projects)
    states: dict[str, dict[str, str]] = {}

    for memory in memories:
        status = _status_from_memory(memory)
        if status is None:
            continue
        identity = alias_map.get(memory.scope.lower(), project_identity_key(project_id=memory.scope))
        _store_newer_state(
            states,
            identity,
            {
                "status": status,
                "source": f"memory:{memory.memory_type}",
                "timestamp": memory.updated_at or memory.created_at,
                "detail": memory.title,
            },
        )

    for bundle_state in _latest_bundle_states(projects, artifacts_dir).values():
        _store_newer_state(states, bundle_state["identity"], bundle_state)

    return states


def is_verified_identity(identity: str, state_index: dict[str, dict[str, str]]) -> bool:
    return state_index.get(identity, {}).get("status") == "verified"


def _project_identity_alias_map(projects: list[ProjectRecord]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for project in projects:
        identity = project_identity_key(project)
        for alias in project_identity_aliases(project):
            alias_map[alias] = identity
    return alias_map


def _latest_bundle_states(
    projects: list[ProjectRecord],
    artifacts_dir: Path,
) -> dict[str, dict[str, str]]:
    alias_map = _project_identity_alias_map(projects)
    known_identities = set(alias_map.values())
    states: dict[str, dict[str, str]] = {}

    for report_dir in _nightly_report_dirs(artifacts_dir):
        bundles_root = report_dir / "bundles"
        if not bundles_root.exists():
            continue
        for bundle_dir in sorted(path for path in bundles_root.iterdir() if path.is_dir()):
            for bundle_path in bundle_dir.glob("*.json"):
                try:
                    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                identity = _bundle_identity(payload, alias_map)
                if not identity or identity not in known_identities:
                    continue
                verdict = str(payload.get("verdict", "")).upper()
                status = "verified" if verdict in SUCCESS_VERDICTS else "failed" if verdict in FAILURE_VERDICTS else "unknown"
                timestamp = str(payload.get("timestamp") or bundle_dir.name)
                _store_newer_state(
                    states,
                    identity,
                    {
                        "identity": identity,
                        "status": status,
                        "verdict": verdict,
                        "source": f"bundle:{bundle_path}",
                        "timestamp": timestamp,
                        "detail": str(payload.get("arbitration_reason", "")),
                    },
                )
    return states


def _nightly_report_dirs(artifacts_dir: Path) -> list[Path]:
    sibling_reports = artifacts_dir.parent / "nightly_reports"
    if sibling_reports.exists():
        return [sibling_reports]

    candidates = [
        sibling_reports,
        Path(__file__).resolve().parents[2] / "data" / "nightly_reports",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _normalize_path(str(candidate))
        if key in seen or not candidate.exists():
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _bundle_identity(payload: dict[str, object], alias_map: dict[str, str]) -> str:
    scope_lock = payload.get("scope_lock", {})
    root_path = scope_lock.get("project_path") if isinstance(scope_lock, dict) else ""
    project_id = str(payload.get("project_id", ""))
    candidate_aliases = project_identity_aliases(project_id=project_id, root_path=str(root_path or ""))
    for alias in candidate_aliases:
        resolved = alias_map.get(alias)
        if resolved:
            return resolved
    return project_identity_key(project_id=project_id, root_path=str(root_path or ""))


def _status_from_memory(memory: MemoryRecord) -> str | None:
    if memory.memory_type == "project_learning":
        return "verified"
    if memory.memory_type == "regression":
        return "failed"
    if memory.memory_type != "audit_snapshot":
        return None
    pass_rate = _pass_rate_from_tags(memory.tags)
    if pass_rate is None:
        return None
    return "verified" if pass_rate >= 0.999 else "failed"


def _pass_rate_from_tags(tags: list[str]) -> float | None:
    for tag in tags:
        if not tag.startswith("pass_rate:"):
            continue
        try:
            return float(tag.split(":", 1)[1])
        except ValueError:
            return None
    return None


def _store_newer_state(
    states: dict[str, dict[str, str]],
    identity: str,
    candidate: dict[str, str],
) -> None:
    current = states.get(identity)
    if current is None or _timestamp_key(candidate.get("timestamp", "")) >= _timestamp_key(current.get("timestamp", "")):
        states[identity] = candidate


def _timestamp_key(value: str) -> tuple[int, float, str]:
    if not value:
        return (0, 0.0, "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (2, parsed.timestamp(), value)
    except ValueError:
        return (1, 0.0, value)


def _strip_project_hash(project_id: str | None) -> str:
    if not project_id:
        return ""
    return PROJECT_ID_HASH_SUFFIX.sub("", project_id.lower())


def _normalize_path(value: str) -> str:
    return value.replace("/", "\\").rstrip("\\").lower()
