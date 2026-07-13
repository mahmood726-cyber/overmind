"""Locator ground-truth resolution — closes the 'gated laundering' residual.

Both external families named this in round 1: a locator that merely *looks*
real ("PMID:31234567#abstract") passes the syntax check in ``export_gate`` but
is never dereferenced. Codex, round 2: *"gated laundering ... a claim can enter
a guarded path with plausible locator syntax and incomplete semantic metadata,
then pass despite not being evidence-validated."* A pointer that is never
followed is a decoration.

This module FOLLOWS the pointer. For an NCT locator it checks the id against a
local AACT snapshot (579,828 real trials) and, when the anchor names a specific
datum, compares the claimed value to the value AACT actually holds. For a PMID
it requires a configured PubMed backend and FAILS CLOSED when none is reachable
— offline, we would rather refuse than pretend to have dereferenced.

Design contract (the anti-decoration rule):
  - A resolver that cannot reach its backend returns ``resolved=False`` with a
    reason. The channel treats that as a BLOCK, never a pass.
  - "Resolved" means the id EXISTS in ground truth. If the anchor pins a value,
    "value_ok" means ground truth EQUALS the claim (within tolerance).
  - There is no ``assume_ok`` / ``skip`` path. The only way to pass is a real hit.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Callable, Optional

# Anchor forms we can pin to a specific ground-truth value.
#   NCT01439880#designGroups        -> arm count (design_groups)
#   NCT01439880#om[123]             -> outcome_measurements.param_value_num for id 123
#   NCT01439880#armcount=2          -> claimed arm count encoded in the locator
_NCT_RE = re.compile(r"(NCT\d{8})", re.IGNORECASE)
_PMID_RE = re.compile(r"PMID:\s?(\d+)", re.IGNORECASE)
_OM_ANCHOR = re.compile(r"om\[(\d+)\]", re.IGNORECASE)
_ARMCOUNT_ANCHOR = re.compile(r"(?:designgroups|armcount)\s*(?:=\s*(\d+))?", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Resolution:
    """The result of following a locator to ground truth.

    ``resolved`` is the load-bearing field: False means we could not confirm the
    pointer against a real source, and the channel MUST block. ``value_ok`` is
    tri-state: True/False when the anchor pins a value, None when the anchor only
    identifies a document (existence-only)."""
    resolved: bool
    value_ok: Optional[bool]
    backend: str
    ground_truth: object = None
    reason: str = ""

    @property
    def passes(self) -> bool:
        """Fail closed: must have resolved, and if a value was pinned it must match."""
        return self.resolved and (self.value_ok is not False)


class ResolverError(RuntimeError):
    pass


def _default_aact_path() -> Optional[str]:
    """The local AACT snapshot. Env override wins; otherwise the known mirror."""
    env = os.environ.get("OVERMIND_AACT_DUCKDB")
    if env and os.path.exists(env):
        return env
    for cand in (
        r"C:\Projects\cochrane-vs-registry\aact.duckdb",
        "/c/Projects/cochrane-vs-registry/aact.duckdb",
    ):
        if os.path.exists(cand):
            return cand
    return None


class LocatorResolver:
    """Dereferences locators against ground truth. Pluggable backends so PubMed
    can be wired later; the NCT backend is live now against local AACT."""

    def __init__(self, *, aact_path: Optional[str] = None,
                 pmid_backend: Optional[Callable[[str, str, object], Resolution]] = None):
        self._aact_path = aact_path if aact_path is not None else _default_aact_path()
        self._pmid_backend = pmid_backend
        self._con = None  # lazy duckdb connection

    # -- NCT against AACT ----------------------------------------------------
    def _aact(self):
        if self._con is not None:
            return self._con
        if not self._aact_path:
            return None
        try:
            import duckdb
            self._con = duckdb.connect(self._aact_path, read_only=True)
        except Exception:
            self._con = None
        return self._con

    def _resolve_nct(self, nct: str, locator: str, claimed_value: object) -> Resolution:
        con = self._aact()
        nct = nct.upper()
        if con is None:
            # Cannot reach ground truth -> fail closed. This is the honest path
            # offline: refuse, do not wave through.
            return Resolution(False, None, "aact",
                              reason="AACT snapshot unreachable — cannot dereference NCT "
                                     "(fail closed; a pointer we cannot follow is not a source)")
        try:
            hit = con.execute("SELECT nct_id FROM studies WHERE nct_id = ?", [nct]).fetchone()
        except Exception as exc:
            return Resolution(False, None, "aact", reason=f"AACT query failed: {exc}")
        if not hit:
            return Resolution(False, None, "aact",
                              reason=f"{nct} does not exist in AACT — fabricated/typo NCT")

        # Anchor pins a specific value? Then EQUALITY against ground truth is required.
        m_om = _OM_ANCHOR.search(locator)
        if m_om:
            om_id = int(m_om.group(1))
            # Round-4 residual (ranked highest by the prompt): bind not just the
            # outcome TITLE but the ARM, TIMEPOINT, and UNIT of the specific om row.
            # A number can match an outcome yet be attached to the wrong arm (control
            # vs treatment), the wrong timepoint (wk12 vs wk52), or the wrong unit
            # (mg/dL vs mmol/L) — that is the SELECTION error F3 was blind to. The om
            # id pins ONE row, so its arm/timepoint/unit are ground truth; the channel
            # requires the claim to declare and match them (when AACT has them).
            row = con.execute(
                "SELECT om.param_value_num, om.title, om.ctgov_group_code, om.units, "
                "       rg.title AS arm_title, o.time_frame "
                "FROM outcome_measurements om "
                "LEFT JOIN result_groups rg ON rg.id = om.result_group_id "
                "LEFT JOIN outcomes o ON o.id = om.outcome_id "
                "WHERE om.id = ? AND om.nct_id = ?", [om_id, nct]).fetchone()
            if not row:
                return Resolution(False, None, "aact",
                                  reason=f"{nct} has no outcome_measurement id={om_id}")
            gt, title, group, units, arm_title, time_frame = row
            ok = _num_eq(claimed_value, gt)
            return Resolution(True, ok, "aact",
                              ground_truth={"value": gt, "title": title, "group": group,
                                            "arm": arm_title, "timepoint": time_frame,
                                            "unit": units},
                              reason="" if ok else
                                     f"value {claimed_value!r} != AACT ground truth {gt!r} "
                                     f"at om[{om_id}] ({title!r})")
        m_arm = _ARMCOUNT_ANCHOR.search(locator)
        if m_arm:
            n_arms = con.execute(
                "SELECT COUNT(*) FROM design_groups WHERE nct_id = ?", [nct]).fetchone()[0]
            claimed = m_arm.group(1)
            if claimed is None and claimed_value is None:
                # existence + arm-count available but nothing pinned to check against
                return Resolution(True, None, "aact", ground_truth=n_arms,
                                  reason=f"{nct} exists; {n_arms} arms (no value pinned)")
            want = int(claimed) if claimed is not None else claimed_value
            ok = _num_eq(want, n_arms)
            return Resolution(True, ok, "aact", ground_truth=n_arms,
                              reason="" if ok else
                                     f"claimed arm count {want!r} != AACT {n_arms} for {nct}")
        # Existence-only anchor (e.g. '#outcome[2]' as a human pointer): id confirmed
        # but NO value pinned. Both external families ranked this the #1 laundering
        # hole: a fabricated value rides in on a real-but-unanchored NCT. So a
        # VALUE-BEARING claim fails closed here — a real trial id is not evidence
        # for a number the id does not actually pin.
        if claimed_value is not None:
            return Resolution(True, False, "aact", ground_truth=nct,
                              reason=f"{nct} exists but the anchor {locator!r} does not pin "
                                     f"the claimed value {claimed_value!r} to a checkable "
                                     f"field — use #om[id] or #armcount so the number can be "
                                     f"dereferenced (existence-only is not value evidence)")
        return Resolution(True, None, "aact", ground_truth=nct,
                          reason=f"{nct} exists in AACT (existence-only, no value claimed)")

    # -- PMID (requires a configured backend; fail closed otherwise) ---------
    def _resolve_pmid(self, pmid: str, locator: str, claimed_value: object) -> Resolution:
        if self._pmid_backend is None:
            return Resolution(False, None, "pubmed",
                              reason="no PubMed backend configured — cannot dereference "
                                     "PMID offline (fail closed by design)")
        try:
            return self._pmid_backend(pmid, locator, claimed_value)
        except Exception as exc:
            return Resolution(False, None, "pubmed", reason=f"PubMed backend error: {exc}")

    # -- public --------------------------------------------------------------
    def resolve(self, locator: str, claimed_value: object = None) -> Resolution:
        loc = (locator or "").strip()
        if not loc:
            return Resolution(False, None, "none", reason="empty locator")
        m = _NCT_RE.search(loc)
        if m:
            return self._resolve_nct(m.group(1), loc, claimed_value)
        m = _PMID_RE.search(loc)
        if m:
            return self._resolve_pmid(m.group(1), loc, claimed_value)
        return Resolution(False, None, "none",
                          reason="locator names no dereferenceable id (NCT/PMID) — "
                                 "cannot follow it to ground truth")


def _num_eq(a: object, b: object, *, rel: float = 1e-6, atol: float = 1e-9) -> bool:
    """Numeric equality with tolerance; exact for non-numerics."""
    try:
        fa, fb = float(a), float(b)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return a == b
    return abs(fa - fb) <= max(atol, rel * max(abs(fa), abs(fb)))


# A module-level default so callers get live NCT resolution with zero wiring.
_DEFAULT: Optional[LocatorResolver] = None


def default_resolver() -> LocatorResolver:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = LocatorResolver()
    return _DEFAULT
