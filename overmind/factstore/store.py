"""Append-only, provenance-carrying shared fact store.

Storage is SQLite in WAL mode so many lanes can read/write concurrently and every
write is durably on disk the instant it returns (resumable-from-disk by
construction — a PC restart loses nothing, and a partial run's facts are all
present but stay unverified, so `consume_verified` refuses to emit them as
complete).

Two append-only tables:
  * ``facts``       — immutable rows: value, provenance, source, derivation,
                      parents, and (for headlines) the pre-registered refutation
                      criterion. A fact's VALUE and PROVENANCE are never mutated.
  * ``fact_events`` — append-only verification / contradiction / adjudication
                      events. A fact's live status is a fold of its events, so the
                      history is never rewritten.

Provenance is a two-point lattice: REAL ⊔ SYNTHETIC = SYNTHETIC. It is computed
ONCE at assert/derive time from the fact's own flag ⊔ every parent's provenance,
then frozen — that is what makes the synthetic flag unlosable and transitive.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

from overmind.factstore.plausibility import check_plausibility


class Provenance(str, Enum):
    REAL = "real"
    SYNTHETIC = "synthetic"

    @staticmethod
    def join(*provs: "Provenance") -> "Provenance":
        """Lattice join: SYNTHETIC dominates. Empty -> REAL."""
        return (Provenance.SYNTHETIC
                if any(p == Provenance.SYNTHETIC for p in provs) else Provenance.REAL)


class Status(str, Enum):
    UNVERIFIED = "unverified"   # asserted, no verification event
    VERIFIED = "verified"       # a verification event stands (not later refuted/contradicted)
    REFUTED = "refuted"
    CONTRADICTED = "contradicted"  # conflicts with another fact, not yet adjudicated


class FactStoreError(RuntimeError):
    """Base for all fact-store consumption failures."""


class NoSuchFactError(FactStoreError):
    pass


class SyntheticFactError(FactStoreError):
    """Raised when a SYNTHETIC number is consumed as if it were real."""


class UnverifiedFactError(FactStoreError):
    """Raised when an unverified/refuted number is consumed as if verified."""


class ContradictedFactError(FactStoreError):
    """Raised when a contradicted-but-unadjudicated number is consumed."""


class SycophancyGateError(FactStoreError):
    """Raised when a hypothesis-confirming headline is verified without the
    required cross-family adversarial review + pre-registered refutation."""


class ImplausibleFactError(FactStoreError):
    """Raised when a numeric fact fails the deterministic plausibility gate
    (external consistency) — e.g. the DTA70 impossible-dispersion signature."""


@dataclass(slots=True)
class Fact:
    id: int
    key: str
    value: Any
    provenance: Provenance
    source_locator: str
    derivation: str
    parents: list[int]
    lane: str
    confirms_hypothesis: bool
    hypothesis: str
    refutation_criterion: str
    created: float
    status: Status = Status.UNVERIFIED
    events: list[dict] = field(default_factory=list)

    @property
    def is_synthetic(self) -> bool:
        return self.provenance == Provenance.SYNTHETIC

    @property
    def consumable(self) -> bool:
        """Safe to consume as a real, verified number."""
        return (self.provenance == Provenance.REAL
                and self.status == Status.VERIFIED)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "key": self.key, "value": self.value,
            "provenance": self.provenance.value, "status": self.status.value,
            "source_locator": self.source_locator, "derivation": self.derivation,
            "parents": list(self.parents), "lane": self.lane,
            "confirms_hypothesis": self.confirms_hypothesis,
            "hypothesis": self.hypothesis,
            "refutation_criterion": self.refutation_criterion,
            "created": self.created,
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    key                  TEXT NOT NULL,
    value                TEXT NOT NULL,            -- JSON
    provenance           TEXT NOT NULL,            -- real | synthetic  (FROZEN, transitive)
    source_locator       TEXT NOT NULL,
    derivation           TEXT NOT NULL DEFAULT '',
    parents              TEXT NOT NULL DEFAULT '[]',
    lane                 TEXT NOT NULL,
    confirms_hypothesis  INTEGER NOT NULL DEFAULT 0,
    hypothesis           TEXT NOT NULL DEFAULT '',
    refutation_criterion TEXT NOT NULL DEFAULT '',
    created              REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);
CREATE TABLE IF NOT EXISTS fact_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id   INTEGER NOT NULL,
    kind      TEXT NOT NULL,     -- verified|refuted|contradicted|adjudicated_winner|adjudicated_loser|reslice_flag
    families  TEXT NOT NULL DEFAULT '[]',
    reviewer  TEXT NOT NULL DEFAULT '',
    detail    TEXT NOT NULL DEFAULT '',
    created   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_fact ON fact_events(fact_id);
-- Rehydrate-on-read taint (DCPG / NeuroTaint 2604.23374): a lane that READS a
-- synthetic fact is recorded here; every fact it subsequently writes inherits
-- synthetic regardless of declared lineage. Persisted so the taint survives a
-- process restart (cross-session persistence). This closes context-window
-- laundering — re-stating a synthetic value as a fresh root fact with no edge.
CREATE TABLE IF NOT EXISTS tainted_lanes (
    lane            TEXT PRIMARY KEY,
    tainted_by_fact INTEGER NOT NULL,
    detail          TEXT NOT NULL DEFAULT '',
    created         REAL NOT NULL
);
-- Value-taint set (agy's cheap patch): normalised numeric forms emitted by any
-- synthetic fact. A new fact whose numeric leaves match a tainted value is forced
-- synthetic — catches copy/rounding laundering of a specific number.
CREATE TABLE IF NOT EXISTS value_taints (
    norm     TEXT PRIMARY KEY,
    fact_id  INTEGER NOT NULL,
    created  REAL NOT NULL
);
"""

# Numeric agreement tolerance for contradiction detection (matches the repo's
# R/metafor parity band). Two numeric values "agree" within atol + rtol*scale.
_DEFAULT_RTOL = 1e-6
_DEFAULT_ATOL = 1e-9
# A hypothesis-confirming headline needs corroboration from at least this many
# DISTINCT vendor families before it can be verified (anti-sycophancy). Two
# families DETECT; the third RESOLVES — but two distinct families is the floor
# below which a same-family panel would just agree with itself.
_MIN_ADVERSARIAL_FAMILIES = 2


def _values_agree(a: Any, b: Any, *, rtol: float, atol: float) -> bool:
    """True if a and b are the same fact-value. Numbers compare within tolerance;
    everything else compares by canonical JSON equality."""
    an = _as_number(a)
    bn = _as_number(b)
    if an is not None and bn is not None:
        if not (math.isfinite(an) and math.isfinite(bn)):
            return an == bn  # NaN/inf: only equal if identical
        return abs(an - bn) <= atol + rtol * max(abs(an), abs(bn))
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _as_number(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _numeric_leaves(value: Any) -> list[float]:
    """Every numeric value inside ``value`` (scalars, list items, dict values,
    recursively). Booleans excluded."""
    out: list[float] = []
    n = _as_number(value)
    if n is not None:
        out.append(n)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_numeric_leaves(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(_numeric_leaves(v))
    return out


def _taint_forms(value: Any) -> set[str]:
    """Normalised string forms of the *specific* numeric leaves worth taint-tracking
    (the effect-size / Se / Sp / large-N laundering targets). Registers exact plus
    rounded forms so copy AND rounding laundering (0.858 -> 0.86) both match.

    Deliberately SKIPS small integers (< 1000) and 0/1: study counts, arm counts and
    trivial values are too common to taint without absurd false positives. The
    rehydrate-on-read lane taint is the primary defence; this value set is the
    secondary catch for a specific laundered number."""
    forms: set[str] = set()
    for x in _numeric_leaves(value):
        if not math.isfinite(x):
            continue
        is_int = float(x).is_integer()
        if is_int and abs(x) < 1000:
            continue  # skip trivial/common small integers (counts, k, arms)
        forms.add(repr(float(x)))
        # rounded forms catch copy-with-rounding of a specific float
        if not is_int:
            for nd in (2, 3, 4):
                forms.add(repr(round(float(x), nd)))
    return forms


def open_shared(path: str | Path | None = None, *, lane: str | None = None) -> "FactStore":
    """Open THE shared fact store — the one every lane must read/write so findings
    stop living in twenty private notebooks.

    Path resolution (first hit wins): explicit ``path`` arg -> ``OVERMIND_FACTSTORE``
    env var -> ``~/.overmind/factstore.db``. The parent dir is created. Because it is
    one conventional location, a lane needs a single line to join the shared store::

        from overmind.factstore import open_shared
        fs = open_shared(lane="my-lane")
        fs.record_real("key", value, source="PMID:1", lane="my-lane")

    Pass ``lane`` so rehydrate-on-read taint works: if this handle reads a synthetic
    fact, the lane is tainted and its subsequent writes are forced synthetic.
    """
    import os
    resolved = (str(path) if path is not None
                else os.environ.get("OVERMIND_FACTSTORE")
                or str(Path.home() / ".overmind" / "factstore.db"))
    if resolved != ":memory:":
        Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    return FactStore(resolved, session_lane=lane)


class FactStore:
    """A shared, append-only, provenance-carrying fact store.

    Cheap to use — the common paths are one call each::

        fs = FactStore(path)
        fid = fs.record_real("TB.DTA.sens", 0.72, source="PMID:123", lane="dta")
        fs.verify(fid, families=["openai", "google"], reviewer="panel")
        value = fs.consume_verified("TB.DTA.sens")   # raises unless real+verified

        syn = fs.record_synthetic("TB.DTA.sens", 0.858, source="DTA70", lane="x")
        head = fs.derive("TB.headline", 0.858, from_ids=[syn], source="calc", lane="y")
        fs.consume_verified("TB.headline")   # SyntheticFactError — transitively synthetic
    """

    def __init__(self, path: str | Path = ":memory:", *,
                 session_lane: str | None = None,
                 rtol: float = _DEFAULT_RTOL, atol: float = _DEFAULT_ATOL) -> None:
        self.path = str(path)
        # The lane operating THIS handle. When set, reading a synthetic fact through
        # this handle taints the lane (rehydrate-on-read), so anything it writes next
        # is forced synthetic. Each lane should open the store with its own identity.
        self.session_lane = session_lane
        self.rtol = rtol
        self.atol = atol
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "FactStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- assert / derive --------------------------------------------------

    def assert_fact(
        self,
        key: str,
        value: Any,
        *,
        provenance: Provenance | str,
        source_locator: str,
        lane: str,
        derivation: str = "",
        parents: Sequence[int] = (),
        confirms_hypothesis: bool = False,
        hypothesis: str = "",
        refutation_criterion: str = "",
    ) -> int:
        """Append a fact. Returns its id.

        Provenance is FROZEN here as (declared provenance) ⊔ (every parent's
        provenance) — synthetic is transitive and unlosable. On a value conflict
        with an existing live fact for ``key``, BOTH are marked contradicted.
        """
        if not key or not isinstance(key, str):
            raise ValueError("key must be a non-empty string")
        if not source_locator:
            raise ValueError("source_locator is required — a fact with no origin is naked")
        if not lane:
            raise ValueError("lane is required — every fact records who asserted it")
        prov = Provenance(provenance) if not isinstance(provenance, Provenance) else provenance
        parent_ids = [int(p) for p in parents]
        # TRANSITIVE synthetic (edge layer): join with every parent's frozen provenance.
        parent_provs = [self._provenance_of(pid) for pid in parent_ids]
        effective = Provenance.join(prov, *parent_provs)
        taint_reasons: list[str] = []
        # REHYDRATE-ON-READ (the laundering fix): if the WRITER lane has read a
        # synthetic fact, everything it writes is forced synthetic regardless of the
        # declared lineage — this catches a lane re-stating a synthetic value as a
        # fresh root fact with no parents (the DTA70 escape path).
        if effective != Provenance.SYNTHETIC and self._is_lane_tainted(lane):
            effective = Provenance.SYNTHETIC
            taint_reasons.append(f"writer lane {lane!r} is taint-carrying (read synthetic data)")
        # VALUE-TAINT (copy/rounding launder): if any numeric leaf of the value matches
        # a value emitted by a synthetic fact, force synthetic.
        if effective != Provenance.SYNTHETIC:
            hit = self._value_taint_hit(value)
            if hit is not None:
                effective = Provenance.SYNTHETIC
                taint_reasons.append(f"value matches synthetic-tainted number ({hit})")
        if taint_reasons and derivation:
            derivation = f"{derivation} | TAINTED: {'; '.join(taint_reasons)}"
        elif taint_reasons:
            derivation = "TAINTED: " + "; ".join(taint_reasons)
        # A confirming headline MUST pre-register its refutation criterion at assert
        # time (immutable). Enforced here so it cannot be added post-hoc to rescue a
        # verify() call later.
        if confirms_hypothesis and not refutation_criterion.strip():
            raise SycophancyGateError(
                f"fact {key!r} confirms a hypothesis but has no pre-registered "
                "refutation_criterion — a confirming headline must state, before "
                "the analysis, what result would refute it")
        now = time.time()
        cur = self._conn.execute(
            "INSERT INTO facts (key, value, provenance, source_locator, derivation, "
            "parents, lane, confirms_hypothesis, hypothesis, refutation_criterion, created) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (key, json.dumps(value), effective.value, source_locator, derivation,
             json.dumps(parent_ids), lane, 1 if confirms_hypothesis else 0,
             hypothesis, refutation_criterion, now),
        )
        fact_id = int(cur.lastrowid)
        self._conn.commit()
        # A synthetic fact registers its numeric leaves in the value-taint set so a
        # later copy/rounding re-statement is caught even without a lineage edge.
        if effective == Provenance.SYNTHETIC:
            self._register_value_taint(fact_id, value)
        self._detect_contradiction(fact_id, key, value)
        return fact_id

    def record_real(self, key: str, value: Any, *, source: str, lane: str,
                    **kw) -> int:
        """Cheap path: assert a REAL fact."""
        return self.assert_fact(key, value, provenance=Provenance.REAL,
                                source_locator=source, lane=lane, **kw)

    def record_synthetic(self, key: str, value: Any, *, source: str, lane: str,
                         **kw) -> int:
        """Cheap path: assert a SYNTHETIC fact (e.g. a figure from DTA70)."""
        return self.assert_fact(key, value, provenance=Provenance.SYNTHETIC,
                                source_locator=source, lane=lane, **kw)

    def derive(self, key: str, value: Any, *, from_ids: Sequence[int],
               source: str, lane: str, derivation: str = "", **kw) -> int:
        """Derive a new fact from parents. Provenance is inherited transitively:
        synthetic if ANY parent is synthetic. This is the boundary the fake TB
        number crossed 'naked' — here it stays synthetic forever."""
        return self.assert_fact(
            key, value, provenance=Provenance.REAL,  # own flag REAL; parents may force SYNTHETIC
            source_locator=source, lane=lane, derivation=derivation,
            parents=from_ids, **kw)

    # -- verification / contradiction / adjudication ----------------------

    def verify(self, fact_id: int, *, families: Sequence[str], reviewer: str = "",
               detail: str = "") -> None:
        """Record a verification. GATES (all fail-closed):

        * a SYNTHETIC fact can never be verified real (SyntheticFactError);
        * a CONTRADICTED-unadjudicated fact cannot be verified until adjudicated;
        * a hypothesis-confirming fact needs >= 2 DISTINCT vendor families in
          ``families`` (cross-family adversarial review) — a same-family panel that
          just agrees with the author is not review (SycophancyGateError).
        """
        fact = self._get(fact_id)   # verifying is not consuming — do not taint the verifier
        if fact is None:
            raise NoSuchFactError(f"no fact id={fact_id}")
        if fact.is_synthetic:
            raise SyntheticFactError(
                f"fact {fact.key!r} (id={fact_id}) is SYNTHETIC (source "
                f"{fact.source_locator!r}) — a synthetic number is never verified real")
        if fact.status == Status.CONTRADICTED:
            raise ContradictedFactError(
                f"fact {fact.key!r} (id={fact_id}) is contradicted — adjudicate first")
        # PLAUSIBILITY (external consistency): an implausible number can never be
        # verified. Flagged (recorded), never silently dropped — the DTA70
        # impossible-dispersion / out-of-range / counts-vs-effect class is caught
        # here BEFORE it can be consumed as a real result.
        plaus = check_plausibility(fact.value, kind=fact.key)
        if not plaus.ok:
            self._event(fact_id, "implausible", detail="; ".join(plaus.violations))
            raise ImplausibleFactError(
                f"fact {fact.key!r} (id={fact_id}) fails plausibility and cannot be "
                f"verified: {'; '.join(plaus.violations)}")
        if plaus.warnings:
            # soft flag: surfaced (recorded) but does not block — an extreme-but-
            # possible number gets eyeballed, not auto-rejected.
            self._event(fact_id, "plausibility_warning", detail="; ".join(plaus.warnings))
        fams = sorted({f for f in families if f})
        if fact.confirms_hypothesis and len(fams) < _MIN_ADVERSARIAL_FAMILIES:
            raise SycophancyGateError(
                f"fact {fact.key!r} confirms a hypothesis ({fact.hypothesis!r}); it "
                f"needs adversarial review by >= {_MIN_ADVERSARIAL_FAMILIES} DISTINCT "
                f"vendor families before it can be verified, got {fams or 'none'}. "
                "Confirmation is exactly when the pull to soften is strongest.")
        self._event(fact_id, "verified", families=fams, reviewer=reviewer, detail=detail)

    def refute(self, fact_id: int, *, families: Sequence[str] = (), reviewer: str = "",
               detail: str = "") -> None:
        self._event(fact_id, "refuted", families=list(families), reviewer=reviewer, detail=detail)

    def flag_reslice(self, fact_id: int, *, reviewer: str = "", detail: str = "") -> None:
        """Flag that this fact was produced by a post-hoc re-slice that rescued a
        claim — recorded on the fact so the rescue is never invisible."""
        self._event(fact_id, "reslice_flag", reviewer=reviewer, detail=detail)

    def adjudicate(self, *, winner_id: int, loser_ids: Sequence[int],
                   reviewer: str = "", detail: str = "") -> None:
        """Resolve a contradiction: the winner becomes consumable-again (pending its
        own verification), losers are recorded as refuted."""
        self._event(winner_id, "adjudicated_winner", reviewer=reviewer, detail=detail)
        for lid in loser_ids:
            self._event(lid, "adjudicated_loser", reviewer=reviewer, detail=detail)

    # -- consumption gate -------------------------------------------------

    def consume_verified(self, key: str, *, lane: str = "") -> Any:
        """Return the value for ``key`` ONLY if a single authoritative fact for it is
        REAL and VERIFIED and not contradicted. Otherwise FAIL LOUD — this is the
        gate that would have stopped the fake TB number from reaching the slide.

        Raises: NoSuchFactError / SyntheticFactError / ContradictedFactError /
        UnverifiedFactError.
        """
        # Internal read: consume returns only REAL+VERIFIED values and raises on a
        # synthetic one without leaking it, so it does not itself taint the caller —
        # the taint happens when a lane deliberately reads a synthetic fact via the
        # public get()/facts_for().
        facts = self._facts_for(key)
        if not facts:
            raise NoSuchFactError(f"no fact recorded for key {key!r}")
        # A live contradiction on any candidate blocks the whole key until adjudicated.
        contradicted = [f for f in facts if f.status == Status.CONTRADICTED]
        if contradicted:
            raise ContradictedFactError(
                f"key {key!r} has {len(contradicted)} contradicted value(s) "
                "unadjudicated — no value is usable until adjudicated "
                "(silence is not agreement)")
        verified_real = [f for f in facts if f.consumable]
        if verified_real:
            # Newest verified-real fact wins (adjudication/re-verification supersedes).
            return sorted(verified_real, key=lambda f: f.id)[-1].value
        # Nothing consumable — say precisely why, using the most relevant candidate.
        latest = sorted(facts, key=lambda f: f.id)[-1]
        if latest.is_synthetic:
            raise SyntheticFactError(
                f"key {key!r} latest value is SYNTHETIC (source "
                f"{latest.source_locator!r}, derivation {latest.derivation or 'n/a'!r}) "
                "— refusing to emit a synthetic number as a real result")
        raise UnverifiedFactError(
            f"key {key!r} has no verified value (status={latest.status.value}) — "
            "a partial/unverified number must never be emitted as complete")

    def plausibility(self, fact_id: int):
        """Run the deterministic plausibility gate on a fact's value (standalone —
        does not mutate). Returns a PlausibilityResult."""
        fact = self._get(fact_id)
        if fact is None:
            raise NoSuchFactError(f"no fact id={fact_id}")
        return check_plausibility(fact.value, kind=fact.key)

    def try_consume(self, key: str) -> tuple[bool, Any]:
        """Non-raising variant: (ok, value_or_reason)."""
        try:
            return True, self.consume_verified(key)
        except FactStoreError as exc:
            return False, str(exc)

    # -- reads (public reads TAINT the session lane; internal reads do not) ------

    def get(self, fact_id: int) -> Fact | None:
        """Public read — rehydrate-on-read: if this returns a synthetic fact, the
        session lane is tainted (its future writes inherit synthetic)."""
        fact = self._get(fact_id)
        self._rehydrate_taint([fact] if fact is not None else [])
        return fact

    def facts_for(self, key: str) -> list[Fact]:
        facts = self._facts_for(key)
        self._rehydrate_taint(facts)
        return facts

    def all_facts(self) -> list[Fact]:
        facts = self._all_facts()
        self._rehydrate_taint(facts)
        return facts

    def contradictions(self) -> list[Fact]:
        return [f for f in self._all_facts() if f.status == Status.CONTRADICTED]

    # -- internal (non-tainting) reads ------------------------------------

    def _get(self, fact_id: int) -> Fact | None:
        row = self._conn.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
        return self._hydrate(row) if row is not None else None

    def _facts_for(self, key: str) -> list[Fact]:
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE key=? ORDER BY id", (key,)).fetchall()
        return [self._hydrate(r) for r in rows]

    def _all_facts(self) -> list[Fact]:
        rows = self._conn.execute("SELECT * FROM facts ORDER BY id").fetchall()
        return [self._hydrate(r) for r in rows]

    # -- internals --------------------------------------------------------

    def _provenance_of(self, fact_id: int) -> Provenance:
        row = self._conn.execute(
            "SELECT provenance FROM facts WHERE id=?", (fact_id,)).fetchone()
        if row is None:
            raise NoSuchFactError(f"parent fact id={fact_id} does not exist")
        return Provenance(row["provenance"])

    # -- taint (rehydrate-on-read + value-taint) --------------------------

    def _rehydrate_taint(self, facts: list["Fact"]) -> None:
        """If the session lane read any synthetic fact, taint the lane so anything
        it writes next inherits synthetic — closes context-window laundering."""
        if not self.session_lane:
            return
        for f in facts:
            if f is not None and f.provenance == Provenance.SYNTHETIC:
                self._taint_lane(self.session_lane, f.id,
                                 detail=f"read synthetic fact {f.id} ({f.key!r})")
                return

    def _taint_lane(self, lane: str, by_fact: int, detail: str = "") -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO tainted_lanes (lane, tainted_by_fact, detail, created) "
            "VALUES (?,?,?,?)", (lane, int(by_fact), detail, time.time()))
        self._conn.commit()

    def _is_lane_tainted(self, lane: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM tainted_lanes WHERE lane=?", (lane,)).fetchone()
        return row is not None

    def tainted_lanes(self) -> list[str]:
        """Lanes currently carrying taint (read a synthetic fact)."""
        return [r["lane"] for r in self._conn.execute(
            "SELECT lane FROM tainted_lanes ORDER BY lane").fetchall()]

    def _register_value_taint(self, fact_id: int, value: Any) -> None:
        for norm in _taint_forms(value):
            self._conn.execute(
                "INSERT OR IGNORE INTO value_taints (norm, fact_id, created) VALUES (?,?,?)",
                (norm, int(fact_id), time.time()))
        self._conn.commit()

    def _value_taint_hit(self, value: Any) -> str | None:
        for norm in _taint_forms(value):
            row = self._conn.execute(
                "SELECT norm FROM value_taints WHERE norm=?", (norm,)).fetchone()
            if row is not None:
                return norm
        return None

    def _event(self, fact_id: int, kind: str, *, families: Iterable[str] = (),
               reviewer: str = "", detail: str = "") -> None:
        if self._get(fact_id) is None:
            raise NoSuchFactError(f"no fact id={fact_id}")
        self._conn.execute(
            "INSERT INTO fact_events (fact_id, kind, families, reviewer, detail, created) "
            "VALUES (?,?,?,?,?,?)",
            (fact_id, kind, json.dumps(sorted({f for f in families if f})),
             reviewer, detail, time.time()))
        self._conn.commit()

    def _detect_contradiction(self, new_id: int, key: str, value: Any) -> None:
        """If another LIVE fact for this key holds a different value, contradict BOTH."""
        rows = self._conn.execute(
            "SELECT id, value FROM facts WHERE key=? AND id!=?", (key, new_id)).fetchall()
        conflicting = []
        for r in rows:
            other_val = json.loads(r["value"])
            if not _values_agree(value, other_val, rtol=self.rtol, atol=self.atol):
                # Only a still-live (not already-adjudicated) fact conflicts.
                other = self._get(int(r["id"]))
                if other is not None and other.status != Status.REFUTED:
                    conflicting.append(int(r["id"]))
        if conflicting:
            self._event(new_id, "contradicted",
                        detail=f"conflicts with fact(s) {conflicting} for key {key!r}")
            for cid in conflicting:
                self._event(cid, "contradicted",
                            detail=f"conflicts with fact {new_id} for key {key!r}")

    def _hydrate(self, row: sqlite3.Row) -> Fact:
        events = self._conn.execute(
            "SELECT kind, families, reviewer, detail, created FROM fact_events "
            "WHERE fact_id=? ORDER BY id", (row["id"],)).fetchall()
        ev = [dict(e) for e in events]
        fact = Fact(
            id=int(row["id"]), key=row["key"], value=json.loads(row["value"]),
            provenance=Provenance(row["provenance"]),
            source_locator=row["source_locator"], derivation=row["derivation"],
            parents=json.loads(row["parents"]), lane=row["lane"],
            confirms_hypothesis=bool(row["confirms_hypothesis"]),
            hypothesis=row["hypothesis"], refutation_criterion=row["refutation_criterion"],
            created=float(row["created"]), events=ev,
        )
        fact.status = self._fold_status(ev)
        return fact

    @staticmethod
    def _fold_status(events: list[dict]) -> Status:
        """Live status = fold of the append-only event log.

        Precedence, most recent wins within a category:
          * an unresolved 'contradicted' (no later adjudication) -> CONTRADICTED
          * else a 'refuted'/'adjudicated_loser' after any 'verified' -> REFUTED
          * else a 'verified' -> VERIFIED
          * else UNVERIFIED
        """
        contradicted = False
        adjudicated = False
        verified = False
        refuted = False
        for e in events:
            k = e["kind"]
            if k == "contradicted":
                contradicted, adjudicated = True, False
            elif k in ("adjudicated_winner",):
                adjudicated = True
            elif k == "adjudicated_loser":
                adjudicated, refuted = True, True
            elif k == "verified":
                verified = True
            elif k == "refuted":
                refuted = True
        if contradicted and not adjudicated:
            return Status.CONTRADICTED
        if refuted:
            return Status.REFUTED
        if verified:
            return Status.VERIFIED
        return Status.UNVERIFIED
