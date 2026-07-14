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
from .sink import SINK, SinkViolation


class ChannelViolation(RuntimeError):
    """A number tried to leave the harness without being a validated Claim, or a
    validated Claim failed a gate. Nothing is emitted."""


import re as _re

_STOP = {"the", "a", "an", "of", "in", "at", "to", "and", "or", "for", "with",
         "rate", "score", "value", "total", "mean", "median", "number", "count",
         "years", "days", "weeks", "months", "percent", "change", "baseline"}


def _tokens(s: str) -> set[str]:
    return {w for w in _re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in _STOP}


_NUM_TOK = _re.compile(r"\d+(?:\.\d+)?")
# a claim-shaped number a header must not carry (%, decimal proportion, RR/OR/HR, N=)
_HEADER_NUMBER = _re.compile(
    r"\d+(?:\.\d+)?\s?%|(?<![\w.])0?\.\d{2,}|\b(?:RR|OR|HR|SMD|MD)\s*[=:]?\s*\d|\bN\s*=\s*\d{2,}",
    _re.IGNORECASE)


def _dim_num_tokens(s: str) -> set[str]:
    """Numeric tokens (doses, weeks) — the DISCRIMINATOR _tokens erased. Codex round-4:
    'IGIV-C 0.2 g/kg' and 'IGIV-C 0.4 g/kg' both reduced to {igiv, infusion}, so a
    wrong-dose arm passed. Keep the numbers."""
    return set(_NUM_TOK.findall(s or ""))


# Trial-boilerplate words that are NOT the discriminator of an arm. Codex round-5:
# 'Double-Blind Tocilizumab' vs 'Double-Blind Placebo' shared {double, blind} (2 tokens,
# Jaccard exactly 0.5) and false-accepted — the drug name is the identity, the
# 'Double-Blind' is scaffolding. Strip the scaffolding so the drug/comparator decides.
_DIM_STOP = _STOP | {
    "double", "blind", "single", "open", "label", "group", "arm", "cohort", "period",
    "treatment", "control", "active", "phase", "randomized", "randomised", "part",
    "stage", "study", "subjects", "patients", "participants", "comparator", "reference",
    "experimental", "standard", "care", "usual", "sham", "vehicle", "matching",
}


_NEG = {"without", "no", "not", "non", "never", "absence", "neither", "nor",
        "negative", "excluding", "except"}


def _neg_tokens(s: str) -> frozenset[str]:
    """Negation words in a label — their mismatch flips clinical meaning (with vs
    without, positive vs negative, included vs excluding)."""
    return frozenset(w for w in _re.findall(r"[a-z]+", (s or "").lower()) if w in _NEG)


def _dim_word_tokens(s: str, *, arm: bool = False) -> set[str]:
    """Word tokens for dimension binding — length>=2 (so unit words 'mg'/'kg'/'ml'/'bw'
    survive, unlike _tokens' >=3), minus generic stopwords. For ARMS, also strip
    trial-boilerplate ('double blind', 'group', 'placebo'-context words) so the drug /
    comparator name is what actually gets compared, not the shared scaffolding."""
    stop = _DIM_STOP if arm else _STOP
    return {w for w in _re.findall(r"[a-z]{2,}", (s or "").lower()) if w not in stop}


def _dimension_match(declared: str, truth: str, *, strict_numeric: bool = False) -> bool:
    """Stricter than _overlap, for arm/timepoint/unit binding. Two layers:

    NUMERIC (the dose/week discriminator, Codex round-4): a number the CLAIM states
    that ground truth does NOT have is a conflict (wrong dose 0.4 vs 0.2, wrong week
    12 vs 52) -> reject. For ARMS additionally require every ground-truth number to be
    declared (strict_numeric) so a vague 'Duloxetine' cannot match both 'Duloxetine
    60 mg' and '120 mg'. Timepoint/unit are lenient (a short label may omit truth's
    incidental numbers) but still reject an outright numeric conflict.

    WORD: token-set containment with an evidence floor (>=2 shared tokens, or covering
    >=half the truth's words), else Jaccard >= 0.5. 'GnRH Agonist' vs 'GnRH Antagonist'
    share only 'gnrh' -> Jaccard 0.2 -> blocked, even though both are number-free."""
    dn, tn = _dim_num_tokens(declared), _dim_num_tokens(truth)
    if dn - tn:                        # claim states a number ground truth lacks
        return False
    if strict_numeric and (tn - dn):   # arm: ground truth's dose must be declared
        return False
    # Codex round-6: 'With Chronic Pain' vs 'Without Chronic Pain' — the declared title
    # was a strict SUBSET of truth (it just omits 'without'), so containment accepted a
    # negated arm. A negation-word mismatch flips meaning: require the negation sets to
    # agree. (This is a heuristic patch; the definitive fix is exact group_code binding.)
    if _neg_tokens(declared) != _neg_tokens(truth):
        return False
    td, tt = _dim_word_tokens(declared, arm=strict_numeric), _dim_word_tokens(truth, arm=strict_numeric)
    if not td or not tt:
        # tokenless words (e.g. numeric-only or single-letter units) -> if we got here
        # the numeric check already passed; fall back to normalized substring
        d, t = (declared or "").strip().lower(), (truth or "").strip().lower()
        if not d or not t:
            return False
        return d in t or t in d
    inter = td & tt
    if not inter:
        return False
    if (td <= tt or tt <= td) and (len(inter) >= 2 or len(inter) >= len(tt) / 2):
        return True
    return len(inter) / len(td | tt) >= 0.5


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


import hashlib as _hashlib
import hmac as _hmac
import os as _os

# Round-4 (Codex): a hand-built Rendered defeated write_report, which only did an
# isinstance() check. Rendered is now SEALED — emit() mints an HMAC over its payload
# with a key write_report also holds; a Rendered that did not come from emit() has no
# valid seal and is refused at the physical write. Key from env (never committed);
# absent, a per-process key so a forged Rendered cannot be minted within a run without
# reaching into channel internals (the in-process ceiling, named in the report —
# process separation is the only hard boundary, per agy).
_RENDER_PROCESS_KEY = _os.urandom(32)


def _render_key() -> bytes:
    env = _os.environ.get("OVERMIND_RENDER_KEY")
    return env.encode("utf-8") if env else _RENDER_PROCESS_KEY


def _seal_payload(text: str, value, locator: str, claim_text: str, source_tier: str) -> str:
    # Codex round-5: the seal MUST cover `text` — that is the string write_report
    # actually writes to disk. Sealing only value/locator/claim_text let a valid seal
    # be reused with a swapped `text` (the real payload). Bind the seal to the emitted
    # bytes so a mutated text invalidates it.
    msg = f"{text}\x1f{value!r}\x1f{locator}\x1f{claim_text}\x1f{source_tier}".encode("utf-8")
    return _hmac.new(_render_key(), msg, _hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class Rendered:
    """The ONLY thing a caller gets back — proof the number cleared every gate.

    A destination (markdown/slide/app/message) receives ``Rendered`` objects, not
    floats. The rendered ``text`` embeds the value and its locator so a reader can
    trace it; ``resolution`` records what ground truth said. ``seal`` is an HMAC over
    the payload minted by emit(); write_report refuses a Rendered whose seal does not
    verify, so a hand-constructed Rendered cannot ride the sanctioned writer."""
    text: str
    value: Any
    locator: str
    source_tier: str
    resolution: Resolution | None
    claim_text: str
    passed_gates: tuple[str, ...] = field(default_factory=tuple)
    seal: str = ""

    @property
    def seal_valid(self) -> bool:
        if not self.seal:
            return False
        expected = _seal_payload(self.text, self.value, self.locator,
                                 self.claim_text, self.source_tier)
        return _hmac.compare_digest(self.seal, expected)


class ExportChannel:
    """The single sink. Hold one per process; ``CHANNEL`` is the default."""

    def __init__(self, *, resolver: LocatorResolver | None = None,
                 require_resolution: bool = True,
                 require_panel_for_flattering: bool = True,
                 require_sanctioned_novelty: bool = True,
                 require_group_code: bool = True):
        self._resolver = resolver or default_resolver()
        # require_resolution=False reopens the gated-laundering hole; it exists
        # ONLY for unit tests that inject a stub resolver. Production leaves it True.
        self._require_resolution = require_resolution
        self._require_panel = require_panel_for_flattering
        # Codex round-5: the channel called guard_novelty WITHOUT require_sanctioned,
        # so a NOVELTY claim backed by an in-process STUB search emitted. Default ON so
        # production novelty needs the real cross-process codex executor; tests that
        # inject a stub construct the channel with this False.
        self._require_sanctioned_novelty = require_sanctioned_novelty
        # Part V Fix #2 — CLOSE the 13.1% wrong-arm title tail. The title-string arm
        # heuristic measured specificity 0.869 (a 13.1% false-accept tail Codex mined
        # three ways: dose, boilerplate, negation). The definitive check is the exact
        # ctgov_group_code the #om[id] already pins (1.0/1.0 by construction). With this
        # ON, a value claim on an #om row whose AACT arm carries a group_code MUST declare
        # a matching meta['group_code'] — a title-only declaration is arm-UNVERIFIED and
        # fails closed, NOT accepted on a fuzzy title match. This removes the title path
        # (and its tail) for the case that has a definitive check available.
        self._require_group_code = require_group_code

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

        text = f"{claim.value} [{claim.text}] <{claim.locator}>"
        return Rendered(
            text=text,
            value=claim.value,
            locator=claim.locator,
            source_tier=claim.source_tier.value,
            resolution=resolution,
            claim_text=claim.text,
            passed_gates=tuple(passed),
            seal=_seal_payload(text, claim.value, claim.locator, claim.text,
                               claim.source_tier.value),
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
                              claimant_family=claim.meta.get("claimant_family", "anthropic"),
                              require_sanctioned=self._require_sanctioned_novelty)
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

    def _guard_semantic(self, claim: Claim, resolution: Resolution) -> None:
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
        # Round-4, ranked HIGHEST: arm / timepoint / unit binding — the SELECTION
        # error. Outcome-title match alone lets a real number attach to the WRONG
        # arm (control vs treatment), WRONG timepoint (wk12 vs wk52), or WRONG unit
        # (mg/dL vs mmol/L). The om id pins one AACT row, so its arm/timepoint/unit
        # ARE ground truth. When AACT holds them, the claim MUST declare and match —
        # an unbound arm is precisely how a right-looking number lands on the wrong
        # thing (F3's blind spot; arithmetic recall on selection was 0.000).
        # DEFINITIVE arm identity (Codex round-6): the om id already pins one AACT row,
        # whose ctgov_group_code IS the arm's true identity. If the claim declares
        # meta['group_code'], match it EXACTLY against ground truth — no string
        # heuristic, no with/without tail. This is the real fix; the title match below
        # is the best-effort fallback for human-readable declarations.
        gt_group = gt.get("group") if isinstance(gt, dict) else None
        gt_arm = gt.get("arm") if isinstance(gt, dict) else None
        declared_group = (claim.meta.get("group_code") or "").strip()
        arm_bound_by_group = False
        if self._require_group_code and (gt_group or gt_arm):
            # Part V Fix #2 — CLOSE the 13.1% wrong-arm title tail. The definitive arm
            # identity is the ctgov_group_code the #om[id] ALREADY pins (1.0/1.0 by
            # construction). It is now REQUIRED, not optional: a title-only arm
            # declaration is arm-UNVERIFIED and fails closed, never accepted on a fuzzy
            # title match (the path Codex mined three ways: dose, boilerplate, negation).
            if not declared_group:
                raise ChannelViolation(
                    f"REFUSED (arm-UNVERIFIED): {claim.text!r} pins a value to {loc!r} whose "
                    f"AACT arm is group_code={gt_group!r} / arm={gt_arm!r}, but the claim "
                    f"declares no meta['group_code']. A title-only arm declaration has a "
                    f"measured 13.1% wrong-arm false-accept tail and is NOT accepted — declare "
                    f"the exact group_code so the arm is bound definitively.")
            if gt_group:
                if declared_group.upper() != str(gt_group).upper():
                    raise ChannelViolation(
                        f"REFUSED: {claim.text!r} declares arm group_code={declared_group!r} "
                        f"but AACT records group {gt_group!r} for {loc!r} — wrong arm "
                        f"(definitive exact group-code mismatch).")
                arm_bound_by_group = True   # definitive match — skip the title heuristic
            else:
                # AACT surfaces an arm TITLE but no ctgov_group_code for this row: the
                # definitive check is unavailable, so the arm is UNVERIFIED. Fail closed
                # rather than accept an ungrounded group_code or fall to a fuzzy title
                # match (per the mandate: "where group_code genuinely does not exist, the
                # claim is arm-UNVERIFIED — not silently accepted on a fuzzy title match").
                raise ChannelViolation(
                    f"REFUSED (arm-UNVERIFIED): {loc!r} carries an arm title but AACT holds no "
                    f"ctgov_group_code for this row, so declared group_code={declared_group!r} "
                    f"cannot be checked against ground truth — the arm cannot be definitively "
                    f"bound (no silent fuzzy-title accept).")
        elif gt_group and declared_group and declared_group.upper() != str(gt_group).upper():
            # require_group_code disabled (test/legacy): still honour an EXACT check when
            # both sides are present; otherwise the title heuristic below runs.
            raise ChannelViolation(
                f"REFUSED: {claim.text!r} declares arm group_code={declared_group!r} but "
                f"AACT records group {gt_group!r} for {loc!r} — wrong arm (exact group-code "
                f"mismatch; this is the definitive arm-identity check).")
        if not arm_bound_by_group:
            # title heuristic — the best-effort fallback, reached only when group_code
            # enforcement is disabled or ground truth pins neither group nor arm.
            ExportChannel._guard_dimension(claim, gt, "arm",
                "the number belongs to a specific study arm; declare claim.meta['arm'] "
                "(e.g. the treatment/control group title) so it cannot be read off the "
                "wrong arm")
        ExportChannel._guard_dimension(claim, gt, "timepoint",
            "the number is measured at a specific timepoint; declare "
            "claim.meta['timepoint'] (the time_frame) so a wk12 value is not shipped "
            "as wk52")
        ExportChannel._guard_dimension(claim, gt, "unit",
            "the number carries a unit; declare claim.meta['unit'] so a value is not "
            "reinterpreted in the wrong unit")

    @staticmethod
    def _guard_dimension(claim: Claim, gt: dict, key: str, why: str) -> None:
        """Bind one semantic dimension (arm/timepoint/unit) of a value claim to
        ground truth. REQUIRED when AACT holds a non-null value for it — an
        attacker controls the claim, not the ground truth, so 'require when GT has
        it' cannot be dodged. Absent from GT (or a stub resolver) -> no-op, so this
        is backward compatible with resolvers that do not surface the dimension."""
        truth = gt.get(key) if isinstance(gt, dict) else None
        if truth is None or str(truth).strip() == "":
            return  # ground truth does not pin this dimension -> nothing to bind
        declared = (claim.meta.get(key) or "").strip()
        if not declared:
            raise ChannelViolation(
                f"REFUSED: {claim.text!r} pins a value to {claim.locator!r} but does "
                f"not declare its {key} (claim.meta[{key!r}]). AACT records {key}="
                f"{truth!r} for this datum — {why}. Without it, the number could be "
                f"read off the wrong {key} (the selection error).")
        # arm identity hinges on the DOSE; require ground-truth's numbers to be declared
        if not _dimension_match(declared, str(truth), strict_numeric=(key == "arm")):
            raise ChannelViolation(
                f"REFUSED: {claim.text!r} declares {key}={declared!r} but AACT records "
                f"{key}={truth!r} for {claim.locator!r} — the number is attached to the "
                f"wrong {key} (selection error / wrong-{key} hijack).")

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
    """A channel-OWNED physical sink. Two properties, together, make this the only
    way a world-claim number reaches a protected deliverable file:

      1. TYPE: it accepts ONLY ``Rendered`` objects (the output of emit), so a lane
         that writes through here cannot smuggle a raw number to disk.
      2. PHYSICAL OWNERSHIP: the actual ``open(...,'w')`` runs inside
         ``SINK.authorized_write()``. Any OTHER code that tries to ``open`` a
         protected deliverable path for writing is refused by the audit hook —
         because it is NOT inside this context. This is the round-4 top residual,
         now closed at the OS-call layer: the channel does not merely offer a clean
         path, it owns the physical write to registered roots."""
    # Codex round-6: the `header` was written UNSEALED — arbitrary bytes riding beside
    # valid Rendered lines. A header is a human banner, not a data path: refuse one that
    # contains a claim-shaped number so a fabricated figure cannot be smuggled in it.
    if header and _HEADER_NUMBER.search(header):
        raise ChannelViolation(
            f"write_report refused a header containing a claim-shaped number "
            f"({header!r}). The header is a banner, not a number path — put every number "
            f"through emit() so it is sealed and gated.")
    lines = [header] if header else []
    for r in rendered:
        if not isinstance(r, Rendered):
            raise ChannelViolation(
                f"write_report accepts only Rendered (channel output), got "
                f"{type(r).__name__!r} — route the number through emit() first.")
        # Codex round-4: an isinstance check is not enough — Rendered is a public
        # dataclass, so a hand-built one with a fabricated value would ride the
        # sanctioned writer. Require the emit()-minted SEAL: a Rendered that did not
        # come through the gates has no valid seal and is refused here.
        if not r.seal_valid:
            raise ChannelViolation(
                f"write_report refused a Rendered with an invalid seal "
                f"(value={r.value!r}, locator={r.locator!r}). A Rendered must be minted "
                f"by channel.emit() — a hand-constructed one cannot ride the physical "
                f"sink. (If this is a legitimate cross-process write, set a shared "
                f"OVERMIND_RENDER_KEY so the seal verifies.)")
        lines.append(r.text)
    body = "\n".join(lines)
    with SINK.authorized_write():
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    return body


def seal_deliverables(*roots: str) -> tuple[str, ...]:
    """Arm the physical sink over one or more deliverable roots. After this, any
    write to a file under a root that does NOT go through the channel's
    ``authorized_write`` context (i.e. through ``write_report``) is refused at the
    ``open`` call. Call once at an export entrypoint (nightly/slide/app generation)
    with the specific output directory — NOT process-wide, so unrelated writes
    (logs, caches) are unaffected. Returns the roots now protected."""
    for r in roots:
        SINK.protect(r)
    return SINK.protected_roots
