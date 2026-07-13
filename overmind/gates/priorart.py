"""Gate F7, made executable — a prior-art SEARCH, not a checkbox.

I claimed novelty three times (Trialstreamer, EligMeta, Dawid-Skene 1979) and
was wrong three times; an external family found the prior art each time. Codex,
round 1: *"it does not bind that pass to an actual search corpus ... build a
PriorArtClaim contract: required search sources, exact queries, date, retrieved
candidates, exclusion reasons, reviewer family, and hard block on any unresolved
similar candidate."*

So a novelty claim now REQUIRES a ``PriorArtSearch`` that:
  - was actually EXECUTED (the ``executed`` flag is set only by a real backend,
    never by the constructor — a hand-built empty search cannot pass),
  - ran ≥1 concrete query against ≥1 named source,
  - was run by a family OTHER than the claimant (decorrelation — F7),
  - dispositioned every retrieved candidate: each is either EXCLUDED with a
    reason or flagged SIMILAR. Any unresolved SIMILAR candidate is a hard block.

``execute_prior_art_search`` shells the search out to a different vendor family
(Codex / openai by default) so the search is genuinely decorrelated from the
Claude claimant. Offline or with no executor, it FAILS CLOSED — no search, no
novelty.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional


class PriorArtError(RuntimeError):
    pass


# --- signing: 'executed' is a mutable bool and therefore forgeable (both external
# families flagged this). The real proof of execution is an HMAC token that only
# execute_prior_art_search can mint, because only it holds the key. A hand-built
# or field-mutated search cannot produce a matching token, so guard_novelty can
# refuse it. Key from env (never from the object itself — the TruthCert lesson);
# absent, a per-process key so forgery is impossible within a run. ---
_PROCESS_KEY = os.urandom(32)


def _key() -> bytes:
    env = os.environ.get("OVERMIND_PRIORART_KEY")
    return env.encode("utf-8") if env else _PROCESS_KEY


def _sign(subject: str, queries, sources, reviewer_family: str, candidates) -> str:
    payload = json.dumps({
        "subject": subject,
        "queries": list(queries),
        "sources": list(sources),
        "family": reviewer_family,
        "candidates": [(c.citation, c.similar, c.reason) for c in candidates],
    }, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hmac.new(_key(), payload, hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class Candidate:
    """A retrieved prior-art hit and its disposition."""
    citation: str
    similar: bool          # True == this looks like the same idea (a novelty killer)
    reason: str = ""       # why excluded, or why judged similar


@dataclass(frozen=True, slots=True)
class PriorArtSearch:
    """The evidence that a real adversarial prior-art search happened.

    ``executed`` is set True ONLY by ``execute_prior_art_search`` after a backend
    returned. A search object you build by hand has executed=False and cannot
    clear the gate — that is what stops F7 from degrading back into a label."""
    subject: str                       # the novelty claim being tested
    queries: tuple[str, ...]           # the exact queries run
    sources: tuple[str, ...]           # corpora searched (pubmed, codex-knowledge, ...)
    reviewer_family: str               # who ran it: openai / google / ...
    candidates: tuple[Candidate, ...] = ()
    executed: bool = False
    date: str = ""                     # caller stamps (Date.now is unavailable here)
    token: str = ""                    # HMAC proof of execution — only the executor mints it
    meta: dict = field(default_factory=dict)

    @property
    def unresolved_similar(self) -> tuple[Candidate, ...]:
        return tuple(c for c in self.candidates if c.similar)

    @property
    def token_valid(self) -> bool:
        if not self.token:
            return False
        expected = _sign(self.subject, self.queries, self.sources,
                         self.reviewer_family, self.candidates)
        return hmac.compare_digest(self.token, expected)


def guard_novelty(claim, search: Optional[PriorArtSearch], *,
                  claimant_family: str = "anthropic") -> PriorArtSearch:
    """Fail closed unless a real, different-family search cleared the novelty claim."""
    if search is None:
        raise PriorArtError(
            f"BLOCKED: novelty claim {getattr(claim, 'text', claim)!r} has no "
            f"PriorArtSearch attached. A novelty claim without an executed search "
            f"is exactly the F7 failure (Trialstreamer/EligMeta/Dawid-Skene)."
        )
    if not search.executed:
        raise PriorArtError(
            f"BLOCKED: prior-art search for {search.subject!r} was never executed "
            f"(executed=False) — a hand-built empty search is a checkbox, not a search."
        )
    # 'executed' alone is forgeable (a public bool). The binding proof is the HMAC
    # token, which only execute_prior_art_search can mint and which changes if ANY
    # field is mutated. No valid token => not a real, unmodified search.
    if not search.token_valid:
        raise PriorArtError(
            f"BLOCKED: prior-art search for {search.subject!r} has no valid signature "
            f"(token_valid=False). 'executed=True' set by hand or a mutated field cannot "
            f"clear the gate — only execute_prior_art_search mints a valid token."
        )
    if not search.queries or not any(q.strip() for q in search.queries):
        raise PriorArtError(
            f"BLOCKED: prior-art search for {search.subject!r} ran no concrete query.")
    if not search.sources:
        raise PriorArtError(
            f"BLOCKED: prior-art search for {search.subject!r} names no source corpus.")
    # REPLAY guard (Codex+agy round-2): a valid, signed search for subject A must
    # not clear a novelty claim about subject B. Bind the search to THIS claim.
    subj = getattr(claim, "text", None)
    if subj is not None and search.subject != subj:
        raise PriorArtError(
            f"BLOCKED: prior-art search is for {search.subject!r} but the claim is "
            f"{subj!r} — a search for a different subject cannot clear this novelty "
            f"claim (replay/misbinding)."
        )
    if not search.reviewer_family or search.reviewer_family == claimant_family:
        raise PriorArtError(
            f"BLOCKED: prior-art search for {search.subject!r} was run by "
            f"{search.reviewer_family!r}, same family as the claimant "
            f"{claimant_family!r}. A self-family 'looks novel to me' is worthless (F7)."
        )
    if search.unresolved_similar:
        hits = "; ".join(c.citation for c in search.unresolved_similar)
        raise PriorArtError(
            f"BLOCKED: novelty claim {search.subject!r} — prior art found by "
            f"{search.reviewer_family}: {hits}. Not novel."
        )
    return search


# ---------------------------------------------------------------------------
# Executors — the thing that makes the search REAL. Each returns a list of
# Candidate and the source label; execute_prior_art_search wraps them and sets
# executed=True. A missing/failed executor raises, so the gate stays fail-closed.
# ---------------------------------------------------------------------------

def _codex_executor(subject: str, queries: tuple[str, ...]) -> tuple[list[Candidate], str, str]:
    """Run the prior-art search through Codex (openai family) — genuinely a
    different family than the Claude claimant. Returns (candidates, source, family)."""
    codex = shutil.which("codex")
    if not codex:
        raise PriorArtError("codex CLI not on PATH — cannot execute prior-art search")
    q = " ; ".join(queries)
    prompt = (
        "You are an adversarial prior-art reviewer. For the claimed-novel method below, "
        "search your knowledge for PRIOR WORK that already does substantially the same thing. "
        "Return STRICT JSON: {\"candidates\":[{\"citation\":\"Author Year, venue\","
        "\"similar\":true|false,\"reason\":\"...\"}]}. 'similar':true means it is the same idea "
        "(a novelty killer). If you find none after a real search, return an empty list — but "
        "only after genuinely looking.\n\n"
        f"CLAIMED-NOVEL METHOD: {subject}\nSEARCH ANGLES: {q}\nReturn ONLY the JSON."
    )
    proc = subprocess.run(
        [codex, "exec", prompt],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=240,
    )
    out = (proc.stdout or "").strip()
    start, end = out.find("{"), out.rfind("}")
    if start < 0 or end <= start:
        raise PriorArtError(f"codex returned no JSON: {out[:200]!r}")
    data = json.loads(out[start:end + 1])
    cands = [
        Candidate(citation=str(c.get("citation", "")).strip(),
                  similar=bool(c.get("similar", False)),
                  reason=str(c.get("reason", "")).strip())
        for c in data.get("candidates", [])
    ]
    return cands, "codex-knowledge", "openai"


def execute_prior_art_search(subject: str, queries, *, sources=None,
                             executor: Callable = _codex_executor,
                             date: str = "") -> PriorArtSearch:
    """Execute a REAL prior-art search via a different family and return a search
    object with ``executed=True``. This is the only sanctioned constructor of an
    executed search — the gate trusts ``executed`` because only this sets it."""
    queries = tuple(queries)
    cands, src, family = executor(subject, queries)
    used_sources = tuple(sources) if sources else (src,)
    cands = tuple(cands)
    token = _sign(subject, queries, used_sources, family, cands)
    return PriorArtSearch(
        subject=subject, queries=queries, sources=used_sources,
        reviewer_family=family, candidates=cands,
        executed=True, date=date, token=token,
        meta={"executor": getattr(executor, "__name__", "custom")},
    )
