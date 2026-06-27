"""Loop brakes: cross-night circuit breaker + per-item retry cap.

QW-1 from FRONTIER-AGENT-SCAN-2026-06.md (ADDITIVE — new module only;
no judge/quorum/witness paths touched).

NightCircuitBreaker
    CLOSED/OPEN/HALF_OPEN state machine keyed by project_id.
    Trips after ``threshold`` (default 3) consecutive FAIL nights for the
    same failure_class.  State persists to ``state_path``
    (data/circuit_states.json).  is_open() returns False when CLOSED or
    HALF_OPEN (trial allowed), True when OPEN.

ItemRetryCounter
    In-memory, per-run counter.  Caps at ``max_retries`` (default 3)
    fix-attempts per project within one nightly run.  Complementary to
    NightCircuitBreaker which operates across nights.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

STATE_CLOSED = "CLOSED"
STATE_OPEN = "OPEN"
STATE_HALF_OPEN = "HALF_OPEN"

_DEFAULT_THRESHOLD = 3
_DEFAULT_HALF_OPEN_AFTER = 7 * 86400  # 7 days before allowing one trial


@dataclass
class _ProjectState:
    state: str = STATE_CLOSED
    consecutive_fails: int = 0
    failure_class: str = ""
    opened_at: float = 0.0
    last_attempt: float = 0.0


class NightCircuitBreaker:
    """Trips after N consecutive FAIL nights for a project+failure_class.

    Default-safe: is_open() returns False until a failure streak is
    recorded; existing callers see no behaviour change.
    """

    def __init__(
        self,
        state_path: Path,
        threshold: int = _DEFAULT_THRESHOLD,
        half_open_after: float = _DEFAULT_HALF_OPEN_AFTER,
    ) -> None:
        self.state_path = Path(state_path)
        self.threshold = threshold
        self.half_open_after = half_open_after
        self._states: dict[str, _ProjectState] = {}
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def is_open(self, project_id: str) -> bool:
        """Return True iff the circuit is OPEN (project should be skipped)."""
        st = self._get(project_id)
        if st.state == STATE_CLOSED:
            return False
        if st.state == STATE_OPEN:
            if time.time() - st.opened_at >= self.half_open_after:
                st.state = STATE_HALF_OPEN
                self._save()
                return False  # Allow one trial run
            return True
        # HALF_OPEN: allow one trial
        return False

    def record_attempt(self, project_id: str, failure_class: str) -> None:
        """Record a FAIL verdict; trip the circuit if threshold reached."""
        st = self._get(project_id)

        if st.state == STATE_HALF_OPEN:
            # Trial run failed — return to OPEN
            st.state = STATE_OPEN
            st.opened_at = time.time()
            st.consecutive_fails += 1
        elif not st.failure_class or st.failure_class == failure_class:
            st.consecutive_fails += 1
            st.failure_class = failure_class
        else:
            # Different failure class: reset streak
            st.consecutive_fails = 1
            st.failure_class = failure_class

        st.last_attempt = time.time()

        if st.state == STATE_CLOSED and st.consecutive_fails >= self.threshold:
            st.state = STATE_OPEN
            st.opened_at = time.time()

        self._states[project_id] = st
        self._save()

    def record_success(self, project_id: str) -> None:
        """Record a CERTIFIED/PASS verdict; reset the circuit to CLOSED."""
        st = self._get(project_id)
        if st.state != STATE_CLOSED or st.consecutive_fails > 0:
            st.state = STATE_CLOSED
            st.consecutive_fails = 0
            st.failure_class = ""
            st.opened_at = 0.0
            self._states[project_id] = st
            self._save()

    def reset(self, project_id: str) -> None:
        """Manually force a project's circuit back to CLOSED."""
        self._states.pop(project_id, None)
        self._save()

    def circuit_state(self, project_id: str) -> str:
        return self._get(project_id).state

    def consecutive_fails(self, project_id: str) -> int:
        return self._get(project_id).consecutive_fails

    def failure_class(self, project_id: str) -> str:
        return self._get(project_id).failure_class

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get(self, project_id: str) -> _ProjectState:
        if project_id not in self._states:
            self._states[project_id] = _ProjectState()
        return self._states[project_id]

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            for pid, entry in raw.items():
                self._states[pid] = _ProjectState(**entry)
        except Exception:
            pass  # Corrupt state: start fresh; not a critical-path failure

    def _save(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {pid: asdict(st) for pid, st in self._states.items()}
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)
        except Exception:
            pass  # Observability; never crash the nightly run


class ItemRetryCounter:
    """Per-run, per-project fix-attempt counter.

    Caps at ``max_retries`` (default 3) attempts per project within one
    nightly run.  This is an in-memory counter complementary to
    NightCircuitBreaker which operates across nights.
    """

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries
        self._counts: dict[str, int] = {}

    def increment(self, project_id: str) -> int:
        """Increment and return the new attempt count for this project."""
        self._counts[project_id] = self._counts.get(project_id, 0) + 1
        return self._counts[project_id]

    def is_capped(self, project_id: str) -> bool:
        """Return True if this project has reached the per-run retry cap."""
        return self._counts.get(project_id, 0) >= self.max_retries

    def count(self, project_id: str) -> int:
        return self._counts.get(project_id, 0)
