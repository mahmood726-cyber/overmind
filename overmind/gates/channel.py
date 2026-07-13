"""The binding export channel — the #1 fix both families demanded.

agy, round 1: *"Unless the framework ... enforces type-safety at the boundary
(e.g., the output channel *only* accepts validated Claim objects), the gates can
be trivially bypassed by omission."* Codex, round 2: *"the honest top residual
... an unguarded lane defeats every fix."*

This module is that boundary. It is the ONE sanctioned sink through which a
number reaches a document, slide, app page, or a message to Mahmood. Its public
entry point accepts a ``Claim`` and NOTHING ELSE — there is no overload, no
``emit_raw``, no ``trust_me`` flag. A bare ``float``/``int``/``str`` handed to
the channel does not get a second-class path; it is refused before anything is
rendered. That is the difference between a linter (detects after the fact) and a
type sink (the illegal state has no path).

Construction runs every applicable gate, in order:
  1. type       — must be a Claim (rejects the bare number)              [channel]
  2. export     — non-synthetic, no synthetic ancestor, real locator     [Gate 1]
  3. layer      — aggregate claims declared their evidence layers        [Gate 2]
  4. resolve    — the locator is FOLLOWED to ground truth, value matches  [resolver]
  5. panel      — flattering/novelty claims carry a cleared panel verdict [Gate 4]

Any failure raises ``ChannelViolation`` and NOTHING is emitted (fail closed,
all-or-nothing on a batch). The scanner in ``enforcement.py`` proves that no
lane writes a number to output WITHOUT coming through here — that is what turns
this from opt-in into mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .contract import Claim, ClaimType, SourceTier
from .export_gate import guard_export, ExportBlocked
from .layer_gate import guard_layers, LayerCoverageError
from .resolver import LocatorResolver, default_resolver, Resolution
from .priorart import guard_novelty, PriorArtError


class ChannelViolation(RuntimeError):
    """A number tried to leave the harness without being a validated Claim, or a
    validated Claim failed a gate. Nothing is emitted."""


import re as _re

_STOP = {"the", "a", "an", "of", "in", "at", "to", "and", "or", "for", "with",
         "rate", "score", "value", "total", "mean", "median", "number", "count",
         "years", "days", "weeks", "months", "percent", "change", "baseline"}


def _tokens(s: str) -> set[str]:
    return {w for w in _re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in _STOP}


def _overlap(a: str, b: str) -> bool:
    """Meaningful word overlap between two outcome descriptions, ignoring numbers,
    units, and generic stopwords. Used to bind a claim's stated meaning to ground
    truth so a numeric coincidence cannot launder a mislabeled number."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        # if one side has only generic/stopwords (e.g. "median age" -> {age}), fall
        # back to substring so short labels still bind
        return a.strip().lower() in b.strip().lower() or b.strip().lower() in a.strip().lower()
    return bool(ta & tb)


@dataclass(frozen=True, slots=True)
class Rendered:
    """The ONLY thing a caller gets back — proof the number cleared every gate.

    A destination (markdown/slide/app/message) receives ``Rendered`` objects, not
    floats. The rendered ``text`` embeds the value and its locator so a reader can
    trace it; ``resolution`` records what ground truth said."""
    text: str
    value: Any
    locator: str
    source_tier: str
    resolution: Resolution | None
    claim_text: str
    passed_gates: tuple[str, ...] = field(default_factory=tuple)


class ExportChannel:
    """The single sink. Hold one per process; ``CHANNEL`` is the default."""

    def __init__(self, *, resolver: LocatorResolver | None = None,
                 require_resolution: bool = True,
                 require_panel_for_flattering: bool = True):
        self._resolver = resolver or default_resolver()
        # require_resolution=False reopens the gated-laundering hole; it exists
        # ONLY for unit tests that inject a stub resolver. Production leaves it True.
        self._require_resolution = require_resolution
        self._require_panel = require_panel_for_flattering

    def emit(self, claim: Claim, *, dest: str = "briefing") -> Rendered:
        """The gate. Accepts a Claim ONLY. Returns a Rendered on success; raises
        ChannelViolation otherwise. A bare number reaching here is the illegal
        state — it is refused with a message, never rendered."""
        passed: list[str] = []

        # 1. TYPE — the bare-number refusal. This is the type sink: there is no
        # branch that accepts a float/int/str. The illegal value has no path.
        if not isinstance(claim, Claim):
            raise ChannelViolation(
                f"REFUSED: the export channel accepts only validated Claim objects, "
                f"got {type(claim).__name__!r} ({claim!r}). A bare number has no path "
                f"to output — wrap it: Claim(text=..., value={claim!r}, source_tier=..., "
                f"locator='NCT...#anchor'). Construction is the only way in, and it runs "
                f"the gates."
            )
        passed.append("type")

        # 2 + 3. EXPORT and LAYER gates (fail closed, re-raised as ChannelViolation
        # so a caller has exactly one exception type to handle at the boundary).
        try:
            guard_export(claim)
            passed.append("export")
        except ExportBlocked as exc:
            raise ChannelViolation(str(exc)) from exc
        try:
            guard_layers(claim)
            passed.append("layer")
        except LayerCoverageError as exc:
            raise ChannelViolation(str(exc)) from exc

        # 4. RESOLVE — follow the locator to ground truth. DERIVED claims inherit
        # their parents' resolved locators, so they are checked at the leaves, not
        # here. Everything else must dereference or be refused (closes laundering).
        resolution: Resolution | None = None
        if claim.source_tier is not SourceTier.DERIVED and self._require_resolution:
            resolution = self._resolver.resolve(claim.locator, claim.value)
            if not resolution.passes:
                raise ChannelViolation(
                    f"REFUSED: {claim.text!r} locator {claim.locator!r} did not resolve "
                    f"against ground truth [{resolution.backend}]: {resolution.reason}. "
                    f"A locator that cannot be followed is a decoration, not a source."
                )
            # SEMANTIC anchor-hijack guard (both families, round 2): an #om[id] whose
            # NUMBER matches by coincidence (e.g. a fabricated 60% efficacy anchored to
            # a median-age of 60) must still be refused unless the claim declares the
            # outcome it expects and it matches AACT's recorded outcome title.
            self._guard_semantic(claim, resolution)
            passed.append(f"resolve:{resolution.backend}")
        elif claim.source_tier is SourceTier.DERIVED:
            # A derived claim must actually name its parents; a derived claim with
            # no lineage is how taint (and provenance) gets dropped. And each parent
            # must ITSELF be exportable — Codex confirmed a fabricated `999` derived
            # claim passed when only non-empty lineage was required. Recurse to the
            # leaves so a derived number cannot launder through fake parents.
            if not claim.derived_from:
                raise ChannelViolation(
                    f"REFUSED: derived claim {claim.text!r} declares no parents "
                    f"(derived_from=()) — a derived number with no lineage cannot be "
                    f"resolved and cannot be trusted."
                )
            if self._require_resolution:
                for parent in claim.derived_from:
                    try:
                        self._validate_leaf(parent)
                    except ChannelViolation as exc:
                        raise ChannelViolation(
                            f"REFUSED: derived claim {claim.text!r} rests on an "
                            f"un-exportable parent {parent.text!r}: {exc}"
                        ) from exc
            passed.append("resolve:derived-lineage")

        # 5. PANEL + PRIOR-ART — bound into the sink (see _guard_panel).
        if self._guard_panel(claim):
            passed.append("panel")

        return Rendered(
            text=f"{claim.value} [{claim.text}] <{claim.locator}>",
            value=claim.value,
            locator=claim.locator,
            source_tier=claim.source_tier.value,
            resolution=resolution,
            claim_text=claim.text,
            passed_gates=tuple(passed),
        )

    def _guard_panel(self, claim: Claim) -> bool:
        """Gate 4/F7 bound into the sink. Returns True if a panel was required and
        cleared (so the caller can record it). A flattering/self-confirming/novelty
        claim must carry a cleared cross-family verdict; a NOVELTY claim must also
        carry an HMAC-verified prior-art search bound to THIS claim."""
        needs_panel = (claim.flatters_user or claim.confirms_hypothesis
                       or claim.claim_type is ClaimType.NOVELTY)
        if not (needs_panel and self._require_panel):
            return False
        verdict = claim.meta.get("panel_verdict")
        if verdict != "passed":
            raise ChannelViolation(
                f"REFUSED: {claim.text!r} flatters the user/us or claims novelty but "
                f"carries no cleared cross-family panel verdict "
                f"(claim.meta['panel_verdict']={verdict!r}). Run gates.panel.adjudicate "
                f"and attach 'passed' before it can be emitted (F4/F7).")
        if claim.claim_type is ClaimType.NOVELTY:
            try:
                guard_novelty(claim, claim.meta.get("prior_art"),
                              claimant_family=claim.meta.get("claimant_family", "anthropic"))
            except PriorArtError as exc:
                raise ChannelViolation(str(exc)) from exc
        return True

    def _validate_leaf(self, claim: Claim) -> None:
        """Recursively validate a parent of a DERIVED claim. Codex round-3: a parent
        must clear the SAME gates a directly-emitted claim would — export, layer,
        resolve, semantic, panel/prior-art — else a claim that would fail direct
        emission is laundered through a derived child. Recurses to the leaves."""
        if not isinstance(claim, Claim):
            raise ChannelViolation(f"parent is not a Claim: {claim!r}")
        try:
            guard_export(claim)
            guard_layers(claim)
        except (ExportBlocked, LayerCoverageError) as exc:
            raise ChannelViolation(str(exc)) from exc
        self._guard_panel(claim)   # flattering/novelty parents face the panel too
        if claim.source_tier is SourceTier.DERIVED:
            if not claim.derived_from:
                raise ChannelViolation(f"derived parent {claim.text!r} has no lineage")
            for p in claim.derived_from:
                self._validate_leaf(p)
            return
        res = self._resolver.resolve(claim.locator, claim.value)
        if not res.passes:
            raise ChannelViolation(
                f"parent {claim.text!r} locator {claim.locator!r} did not resolve "
                f"[{res.backend}]: {res.reason}")
        self._guard_semantic(claim, res)

    @staticmethod
    def _guard_semantic(claim: Claim, resolution: Resolution) -> None:
        """For a value-bearing #om[id] claim, require the claim to name the outcome
        it expects and match it against AACT's recorded title — defeats a numeric
        coincidence hijack. If the anchor is armcount/existence this is a no-op."""
        loc = (claim.locator or "")
        if "om[" not in loc.lower() or claim.value is None:
            return
        gt = resolution.ground_truth
        title = gt.get("title") if isinstance(gt, dict) else None
        expected = (claim.meta.get("outcome") or "").strip()
        if not expected:
            raise ChannelViolation(
                f"REFUSED: {claim.text!r} pins value to {loc!r} but declares no "
                f"expected outcome (claim.meta['outcome']). Without it, a number that "
                f"matches AACT by coincidence (e.g. median age == a fabricated %) would "
                f"pass — the anchor-hijack hole. Declare the outcome so it can be checked."
            )
        # Codex round-3 break: checking meta['outcome'] vs AACT alone lets a LYING
        # claim.text ("efficacy 60%") ride a matching meta ("Median age"). Bind all
        # three: meta['outcome'] must match AACT's title AND the human claim.text
        # must be consistent with that outcome — the number's stated meaning, its
        # declared meaning, and its true meaning must agree.
        if title and not _overlap(expected, title):
            raise ChannelViolation(
                f"REFUSED: {claim.text!r} expects outcome {expected!r} but AACT records "
                f"the value at {loc!r} under {title!r} — value matched but the OUTCOME "
                f"does not (anchor-hijack).")
        if not _overlap(claim.text, expected) and not _overlap(claim.text, title or ""):
            raise ChannelViolation(
                f"REFUSED: claim text {claim.text!r} does not match the declared/true "
                f"outcome ({expected!r} / {title!r}) — the number's stated meaning "
                f"disagrees with what it actually measures (anchor-hijack via a lying "
                f"claim text)."
            )

    def emit_all(self, claims: Iterable[Claim], *, dest: str = "briefing") -> list[Rendered]:
        """Batch. Fails closed on the FIRST bad claim — no partial deliverable
        ships with some numbers un-gated."""
        return [self.emit(c, dest=dest) for c in claims]


# The default process-wide sink. Lanes import THIS.
CHANNEL = ExportChannel()


def emit(claim: Claim, *, dest: str = "briefing") -> Rendered:
    """Module-level convenience over the default channel. The one obvious sink."""
    return CHANNEL.emit(claim, dest=dest)


def emit_all(claims: Iterable[Claim], *, dest: str = "briefing") -> list[Rendered]:
    return CHANNEL.emit_all(claims, dest=dest)


def write_report(path: str, rendered: Iterable[Rendered], *, header: str = "") -> str:
    """A channel-OWNED physical sink: it accepts ONLY Rendered objects (the output
    of emit), so a lane that writes through here cannot smuggle a raw number to
    disk. This does not force every lane to use it — that is the named top residual
    — but it gives the clean last-mile path agy asked for: the write is Rendered-
    typed, not str-typed."""
    lines = [header] if header else []
    for r in rendered:
        if not isinstance(r, Rendered):
            raise ChannelViolation(
                f"write_report accepts only Rendered (channel output), got "
                f"{type(r).__name__!r} — route the number through emit() first.")
        lines.append(r.text)
    body = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body
