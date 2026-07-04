"""Determinism witnesses for the reproduction gate (AN-5, arXiv:2601.15322 DFAH).

Two additive D3 witnesses:
  * ``passk`` — the promotion bar for "verified" is **all-k-succeed** (passk), not
    pass@k (any-of-k). A result is promoted to "verified" only if it passes on EVERY
    one of N replays — the compliance-grade metric.
  * ``signature_determinism`` — identical tool-call + args signature across N replays
    (Signature determinism). Flags a reproduction whose action *sequence* drifts run
    to run even when the final answer matches.

Honest caveat (carried from DFAH): determinism proves **auditability**, not
**correctness** — a deterministically wrong answer is still wrong. These pair WITH
the correctness gate (reproduction_witness), never substitute for it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def passk(replay_successes: list[bool]) -> bool:
    """All-k-succeed. True iff there is >=1 replay and EVERY replay passed."""
    return bool(replay_successes) and all(replay_successes)


def pass_at_k(replay_successes: list[bool]) -> bool:
    """Any-of-k (the weaker metric) — provided for contrast/logging only."""
    return any(replay_successes)


def signature_of(tool_calls) -> str:
    """Stable signature of a run's tool-call + args sequence (order-sensitive).
    ``tool_calls`` is a list of {name, args} dicts (or any JSON-able sequence)."""
    normalized = json.dumps(tool_calls, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class DeterminismResult:
    deterministic: bool
    distinct_signatures: int
    n_replays: int
    signatures: list[str]

    def to_dict(self) -> dict:
        return {"deterministic": self.deterministic, "distinct_signatures": self.distinct_signatures,
                "n_replays": self.n_replays, "signatures": list(self.signatures)}


def signature_determinism(replay_tool_calls: list) -> DeterminismResult:
    """Signature determinism across N replays: identical tool-call+args each time.

    ``replay_tool_calls`` is a list (one per replay) of tool-call sequences. A run
    is signature-deterministic iff all replays share one signature."""
    sigs = [signature_of(tc) for tc in replay_tool_calls]
    distinct = len(set(sigs))
    return DeterminismResult(
        deterministic=(distinct == 1 and len(sigs) > 0),
        distinct_signatures=distinct, n_replays=len(sigs), signatures=sigs,
    )


@dataclass(slots=True)
class VerifiedPromotion:
    """AN-5 promotion decision for 'verified': passk AND (optionally) signature-det."""
    passk_ok: bool
    signature_ok: bool
    promote: bool
    note: str

    def to_dict(self) -> dict:
        return {"passk": self.passk_ok, "signature_deterministic": self.signature_ok,
                "promote": self.promote, "note": self.note}


def verified_promotion(replay_successes: list[bool], replay_tool_calls: list | None = None,
                       *, require_signature: bool = False) -> VerifiedPromotion:
    """Promote a result to "verified" only if passk holds (and, when required, the
    tool-call signature is deterministic across replays)."""
    pk = passk(replay_successes)
    sig_ok = True
    if replay_tool_calls is not None:
        sig_ok = signature_determinism(replay_tool_calls).deterministic
    promote = pk and (sig_ok or not require_signature)
    if not pk:
        note = "not passk (a replay failed) — not verified"
    elif require_signature and not sig_ok:
        note = "passk but tool-call signature drifts across replays — auditability gap, not verified"
    else:
        note = "passk" + (" + signature-deterministic" if replay_tool_calls is not None else "")
    return VerifiedPromotion(pk, sig_ok, promote, note)
