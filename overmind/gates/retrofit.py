"""The retrofit ACTION — locate first, THEN mark. (HARNESS-SELF-REVIEW Part V, Fix #1)

Part IV §7.4 named this the concrete, do-able gap: `mark_unverified()` exists and
would annotate the 115,253 unverified world-claims on the 1,040 app pages, but it had
not been RUN, and — the sharper danger Mahmood named — a naive run would *stamp
UNVERIFIED on a number we could have located*. That is F1 wearing a badge of honesty:
the single-layer error (mark everything) is as wrong as the no-layer error (mark
nothing). Both refuse to look.

So the retrofit is a three-layer CASCADE, run per claim, BEFORE any mark:

  1. registry   — an NCT co-located with the number (or bound to the number's trial
                  row in the page's structured `outcomeKeys` data) that RESOLVES in the
                  local AACT snapshot. This is a real dereference, live and offline.
  2. oa_table   — the number recovered from an Open-Access JATS results table. Requires
                  an OA backend; FAILS CLOSED (recovers nothing) when none is wired — we
                  do not pretend to have fetched a table we did not.
  3. abstract   — the number found in the trial's PubMed abstract. Requires a PubMed
                  backend; FAILS CLOSED offline for the same reason.

Whatever survives all three with no locator is marked **UNVERIFIED on screen** — visible,
never silently kept, never silently deleted. And EVERY number carries its source tier on
screen (registry / OA table / abstract / unverified). That tag IS the grade: a Kampala
researcher can tell a located number from an unlocated one at a glance — which is exactly
what was missing when the fabricated Xpert figure shipped.

Honest scope of THIS staged run (dogfooding F1 — no capability claimed that was not run):
  * The registry layer is LIVE against the 579,828-trial local AACT snapshot.
  * The oa_table and abstract layers are WIRED but fail closed offline; this staged run
    records how many numbers they were *asked* to recover and recovered (0 when no
    backend), so the report never implies a fetch that did not happen.
  * Nothing is written over a live app page. `stage_corpus()` writes annotated copies to
    a staging tree and emits the exact in-place command for Mahmood to run after review.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .resolver import LocatorResolver, default_resolver
from .sweep import (
    _claim_numbers,
    _ID_IN_CONTEXT,
    _NCT,
    _NOISE_LINE,
    classify_number,
    classify_with_second_family,
)

# Tiers, strongest to weakest. The tag shown on screen IS the grade.
TIER_REGISTRY = "registry"        # VALUE-verified: an #om[id] anchor resolved AND matched
TIER_REGISTERED = "registered"    # the cited trial is REAL, but THIS number is not
                                  # value-verified against it (existence != verification —
                                  # Codex Part-V break: '99% in NCT..' must NOT read as verified)
TIER_OA = "oa_table"
TIER_ABSTRACT = "abstract"
TIER_UNVERIFIED = "unverified"

_OM_ANCHOR = re.compile(r"om\[(\d+)\]", re.IGNORECASE)

_ANY_ID = re.compile(r"NCT\d{8}|PMID:?\s?\d+|PMC\d+|10\.\d{4,9}/\S+", re.IGNORECASE)

# HTML app pages embed their trial data in <script> blobs. Appending a text marker to a
# line inside a script/style block would CORRUPT the JavaScript/JSON (lessons.md: never
# write a literal marker into a <script> template). So the text annotator SKIPS lines
# inside script/style; the structured `source_tier` retrofit below handles app-page data.
_SCRIPT_OPEN = re.compile(r"<script\b", re.IGNORECASE)
_SCRIPT_CLOSE = re.compile(r"</script>", re.IGNORECASE)
_STYLE_OPEN = re.compile(r"<style\b", re.IGNORECASE)
_STYLE_CLOSE = re.compile(r"</style>", re.IGNORECASE)

# A single embedded trial record: {"nct": "NCT........", ... "source_tier": "..."} — the
# safe unit for the app-page retrofit (JSON value replacement, never a corrupting append).
_TIER_RECORD = re.compile(
    r'("nct":\s*"(NCT\d{8})"[^{}]*?"source_tier":\s*")([^"]*)(")', re.IGNORECASE)

# on-screen markers — the tier tag a reader sees next to the number
_TAG_MD = {
    TIER_REGISTRY: " [registry: value verified]",
    TIER_REGISTERED: " [registered: trial exists, value not verified]",
    TIER_OA: " [OA table]",
    TIER_ABSTRACT: " [abstract]",
    TIER_UNVERIFIED: " [UNVERIFIED: no resolvable trial id]",
}
_TAG_HTML = {
    TIER_REGISTRY: ' <span class="om-tier om-registry" title="value verified: an #om[id] anchor resolved and the value matched AACT">✓ registry</span>',
    TIER_REGISTERED: ' <span class="om-tier om-registered" title="the cited trial resolves in AACT, but THIS number is not value-verified against it">◐ registered</span>',
    TIER_OA: ' <span class="om-tier om-oa" title="located: recovered from Open-Access JATS results table">✓ OA table</span>',
    TIER_ABSTRACT: ' <span class="om-tier om-abstract" title="located: found in PubMed abstract">~ abstract</span>',
    TIER_UNVERIFIED: ' <span class="om-tier om-unverified" title="no resolvable locator — not gate-verified">⚠ UNVERIFIED</span>',
}
# a page already carrying any tier tag is idempotent-skipped
_ALREADY = re.compile(r'om-tier|UNVERIFIED|\[registry|\[registered|\[OA table\]|\[abstract\]')


@dataclass
class CascadeCounts:
    """Per-document tally, by the tier that located each world-claim number."""
    path: str
    world: int = 0                 # definite world-claim numbers
    ambiguous: int = 0             # neither vocabulary — also marked, own class
    located_registry: int = 0      # VALUE-verified (om[id] anchor resolved + matched)
    registered: int = 0            # cited trial resolves, but value NOT verified (honest)
    located_oa: int = 0
    located_abstract: int = 0
    unverified: int = 0            # survived the whole cascade with no locator
    oa_attempts: int = 0           # numbers the OA layer was asked to recover
    abstract_attempts: int = 0     # numbers the abstract layer was asked to recover
    page_ncts: int = 0
    page_ncts_resolved: int = 0
    unresolved_ncts: list = field(default_factory=list)  # the cited-but-not-in-AACT ids

    @property
    def located(self) -> int:
        """VALUE-located only. 'registered' is NOT located — the trial is real but the
        number is not verified against it (Codex Part-V break: existence != verification)."""
        return self.located_registry + self.located_oa + self.located_abstract


class OAResolverStub:
    """Placeholder for an Open-Access JATS-table backend. Present so the cascade layer
    is wired and *counted*, but it recovers nothing without a real backend — fail closed,
    never fabricate a recovery. A real backend would return a value for (nct, outcome)."""

    def recover(self, nct: str, outcome: Optional[str], claimed_value) -> bool:
        return False


class AbstractResolverStub:
    """Placeholder for a PubMed-abstract backend. Fail closed offline, same contract."""

    def recover(self, nct: str, outcome: Optional[str], claimed_value) -> bool:
        return False


class Retrofit:
    """Runs the locate-then-mark cascade over a document's world-claim numbers."""

    def __init__(self, *, resolver: Optional[LocatorResolver] = None,
                 oa: Optional[OAResolverStub] = None,
                 abstract: Optional[AbstractResolverStub] = None):
        self.resolver = resolver or default_resolver()
        self.oa = oa or OAResolverStub()
        self.abstract = abstract or AbstractResolverStub()
        self._resolve_cache: dict[str, bool] = {}

    # -- layer 1: registry ---------------------------------------------------
    def _nct_resolves(self, nct: str) -> bool:
        nct = nct.upper()
        if nct not in self._resolve_cache:
            self._resolve_cache[nct] = self.resolver.resolve(nct).resolved
        return self._resolve_cache[nct]

    def _page_nct_pool(self, text: str) -> dict[str, bool]:
        """Every NCT the page cites, resolved once against AACT. A number tied to one of
        these trials (co-located, or bound in the page's structured data) is located at
        the registry tier — a real dereference, not a guess."""
        pool: dict[str, bool] = {}
        for m in _NCT.finditer(text):
            nct = m.group(0).upper()
            if nct not in pool:
                pool[nct] = self._nct_resolves(nct)
        return pool

    def annotate(self, text: str, *, html: bool = False) -> tuple[str, CascadeCounts]:
        """Locate-then-mark every world-claim and ambiguous number, tagging each with the
        tier that located it (registry/OA/abstract) or UNVERIFIED. Idempotent. Only
        definite-internal numbers (test counts/timings/versions) are left untagged."""
        counts = CascadeCounts(path="")
        pool = self._page_nct_pool(text)
        counts.page_ncts = len(pool)
        counts.page_ncts_resolved = sum(1 for v in pool.values() if v)
        # Prose/HTML-annotate path: surface the cited-but-unresolved NCTs so the visible
        # banner can NAME them (and flag placeholder-pattern ids as LIKELY FABRICATED),
        # exactly as retrofit_app_page_tiers does for structured pages. Without this the
        # prose banner shows only a generic "N unverified numbers" line and the fabricated
        # NCTs render invisible — the on-screen badge the researcher needs is missing.
        counts.unresolved_ncts = [n for n, ok in pool.items() if not ok]
        tags = _TAG_HTML if html else _TAG_MD
        out = []
        in_script = False   # never annotate inside <script>/<style> — would corrupt JS/JSON
        for line in text.splitlines():
            if html:
                opened = _SCRIPT_OPEN.search(line) or _STYLE_OPEN.search(line)
                closed = _SCRIPT_CLOSE.search(line) or _STYLE_CLOSE.search(line)
                if in_script:
                    out.append(line)
                    if closed:
                        in_script = False
                    continue
                if opened and not closed:
                    in_script = True
                    out.append(line)
                    continue
                if opened and closed:
                    # single-line inline script — leave the whole line untouched
                    out.append(line)
                    continue
            if _NOISE_LINE.match(line) or _ALREADY.search(line):
                out.append(line)
                continue
            nums = _claim_numbers(line)
            if not nums:
                out.append(line)
                continue
            # MARKING classifier is the REGEX one, deliberately. agy (Gemini) Part-V
            # attack: an LLM classifier is prompt-injectable ("classify as internal"),
            # so the second family must NEVER suppress an on-screen safety mark — it only
            # informs the REPORTED ambiguous-band denominator (see sweep.classify_with_
            # second_family). Marking stays fail-toward-marking: mark world + ambiguous,
            # leave only REGEX-definite internal unmarked.
            kind = classify_number(line)
            if kind not in ("world", "ambiguous"):
                out.append(line)          # regex-definite internal — no locator needed
                continue
            has_id = bool(_ID_IN_CONTEXT.search(line))
            for _ in nums:
                if kind == "world":
                    counts.world += 1
                else:
                    counts.ambiguous += 1
                tier = self._locate(line, pool, counts) if has_id else self._locate_no_id(line, counts)
                if tier == TIER_REGISTRY:
                    counts.located_registry += 1
                elif tier == TIER_REGISTERED:
                    counts.registered += 1
                elif tier == TIER_OA:
                    counts.located_oa += 1
                elif tier == TIER_ABSTRACT:
                    counts.located_abstract += 1
                else:
                    counts.unverified += 1
            # tag the line with the tier its number reached. registry = value verified;
            # registered = trial real but value NOT verified (honest, not green);
            # UNVERIFIED = no locator. One tag per line keeps the page readable.
            line_tier = self._classify_tier(line, pool)
            out.append(line.rstrip() + tags[line_tier])
        return "\n".join(out), counts

    def _classify_tier(self, sentence: str, pool: dict[str, bool]) -> str:
        """Pure tier classification for ONE sentence (no counting). Shared by the
        per-number count loop's _locate and the per-line tag."""
        m = _NCT.search(sentence)
        if m and pool.get(m.group(0).upper(), False):
            nct = m.group(0).upper()
            om = _OM_ANCHOR.search(sentence)
            if om:
                res = self.resolver.resolve(f"{nct}#om[{om.group(1)}]")
                return TIER_REGISTRY if (res.passes and res.value_ok) else TIER_UNVERIFIED
            return TIER_REGISTERED   # trial real, this number not value-verified
        return TIER_UNVERIFIED

    def _locate(self, sentence: str, pool: dict[str, bool],
                counts: CascadeCounts) -> str:
        tier = self._classify_tier(sentence, pool)
        if tier in (TIER_REGISTRY, TIER_REGISTERED):
            return tier
        # not registry/registered -> the OA then abstract layers get their counted attempt
        counts.oa_attempts += 1
        m = _NCT.search(sentence)
        nct = m.group(0).upper() if m else None
        if nct and self.oa.recover(nct, None, None):
            return TIER_OA
        counts.abstract_attempts += 1
        if nct and self.abstract.recover(nct, None, None):
            return TIER_ABSTRACT
        return TIER_UNVERIFIED

    def _locate_no_id(self, sentence: str, counts: CascadeCounts) -> str:
        """No id co-located at all. OA/abstract still get their (failing, counted)
        attempt so the report is honest about what was tried; then unverified."""
        counts.oa_attempts += 1
        counts.abstract_attempts += 1
        return TIER_UNVERIFIED


    # -- app-page structured retrofit (the SAFE app-page path) ---------------
    def retrofit_app_page_tiers(self, text: str) -> tuple[str, CascadeCounts]:
        """The app-page-safe retrofit: rewrite each embedded trial record's
        `source_tier` by running the cascade on its NCT, instead of appending markers to
        script blobs. `extracted` (the app's default, = unverified) is UPGRADED to
        `registered` when the NCT resolves in AACT, DOWNGRADED to `unverified` when the NCT
        is fabricated/unreachable. The page already renders `source_tier` as an on-screen
        badge, so this makes the grade visible where the researcher already looks — no
        markup surgery, no corruption risk. Idempotent (re-running yields the same tiers).

        HONEST TIER (Codex + agy Part-V break): these records carry an NCT but NO per-value
        #om[id] anchor, so a resolving NCT proves the trial is REAL — NOT that this record's
        numbers are verified against AACT. So the resolved tier is `registered` (existence),
        NOT the value-verified `registry`. Per-value verification is a further layer, named.

        Returns (new_text, counts) where counts.registered / counts.unverified are
        per-RECORD (one trial outcome), which is the granularity this layer dereferences."""
        counts = CascadeCounts(path="")
        pool: dict[str, bool] = {}

        def _sub(m: re.Match) -> str:
            prefix, nct, _old_tier, close = m.group(1), m.group(2).upper(), m.group(3), m.group(4)
            if nct not in pool:
                pool[nct] = self._nct_resolves(nct)
            if pool[nct]:
                counts.registered += 1
                tier = TIER_REGISTERED   # trial resolves; value NOT verified (honest)
            else:
                # cascade layers 2/3 (OA/abstract) fail closed offline — counted, then unverified
                counts.oa_attempts += 1
                counts.abstract_attempts += 1
                counts.unverified += 1
                if nct not in counts.unresolved_ncts:
                    counts.unresolved_ncts.append(nct)
                tier = TIER_UNVERIFIED
            counts.world += 1
            return f"{prefix}{tier}{close}"

        new = _TIER_RECORD.sub(_sub, text)
        counts.page_ncts = len(pool)
        counts.page_ncts_resolved = sum(1 for v in pool.values() if v)
        return new, counts


# --------------------------------------------------------------------------
# The VISIBLE banner — because a badge in the DOM that never renders is not a badge.
# --------------------------------------------------------------------------
# CRITICAL (found on apply-day): the app pages store `source_tier` in a JS data object
# (window.RapidMeta.outcomeKeys) that NO rendering code reads (`.source_tier` accessor
# count == 0). Rewriting that field alone changes NOTHING a researcher sees — the exact F1
# trap ("report what is easy to measure as if it were the truth"). So the retrofit ALSO
# injects a self-contained, JS-free, high-contrast FIXED banner that renders regardless of
# the app's own scripts. It is inserted right after the <body> tag as position:fixed so it
# cannot be clipped by the page's overflow-hidden flex layout.

_BANNER_ID = "overmind-provenance-banner"
_BODY_OPEN = re.compile(r"(<body\b[^>]*>)", re.IGNORECASE)
# a non-resolving NCT with a suspiciously round/placeholder tail — likely FABRICATED, not
# merely 'newer than the snapshot'. Heuristic, stated as such on screen.
_PLACEHOLDER_NCT = re.compile(r"^NCT0500\d{4}$|^NCT\d{5}0{3}$", re.IGNORECASE)
_NCT8 = re.compile(r"^NCT(\d{8})$", re.IGNORECASE)


def _fabricated_partition(ncts: list) -> tuple[list, list]:
    """Split cited-but-non-resolving NCTs into (fabricated, unverified), preserving order.

    A non-resolving id is called FABRICATED when EITHER
      (a) it matches the round placeholder digit-pattern (_PLACEHOLDER_NCT), OR
      (b) it belongs to a SEQUENTIAL BLOCK — a run of >=3 non-resolving ids on the same
          page whose numeric parts are (near-)consecutive (gap <=2). Real trials do not
          register in tidy consecutive ranges on a single review; a non-resolving
          consecutive run is a placeholder block, not 'newer than the snapshot'.
    Everything else stays UNVERIFIED (honestly hedged: may be fabricated OR post-snapshot).
    This is the undercount fix — digit-shape alone missed sequential fake ranges like
    NCT04550914..916 / NCT06000801..803 that carry no round tail."""
    nums = {}
    for n in ncts:
        m = _NCT8.match(n)
        if m:
            nums[n] = int(m.group(1))
    ordered = sorted(nums, key=lambda x: nums[x])
    block: set = set()
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and nums[ordered[j + 1]] - nums[ordered[j]] <= 2:
            j += 1
        if j - i + 1 >= 3:
            block.update(ordered[i:j + 1])
        i = j + 1
    fabricated, unverified = [], []
    for n in ncts:
        if _PLACEHOLDER_NCT.match(n) or n in block:
            fabricated.append(n)
        else:
            unverified.append(n)
    return fabricated, unverified


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_provenance_banner(counts: "CascadeCounts", *, recovered=None,
                             cascade_checked: bool = False) -> str:
    """A self-contained, script-free, fixed-position banner a researcher cannot miss. Green
    for registry-linked records, red for UNVERIFIED with the offending NCTs NAMED, and a
    stronger ⛔ flag for placeholder-pattern ids that are likely fabricated (not merely
    unverified). No external CSS/JS; survives the page's own overflow-hidden layout.

    THREE-LAYER CASCADE (registry -> PubMed -> Europe PMC OA):
      * ``recovered`` — NCTs that FAILED the AACT registry lookup but WERE found in PubMed
        or Europe PMC. These are NOT fabricated (a fabricated trial has no abstract either);
        they are real trials the local registry snapshot missed. Shown in green, and removed
        from the fabricated/unverified lists so we never accuse a trial with a real abstract.
      * ``cascade_checked`` — the fabricated/unverified verdicts were confirmed against
        PubMed + Europe PMC (not registry alone), so the on-screen wording says so."""
    recovered = set(recovered or ())
    registered = counts.registered + counts.located_registry
    unverified = counts.unverified
    unresolved = [n for n in counts.unresolved_ncts if n not in recovered]
    rec_here = [n for n in counts.unresolved_ncts if n in recovered]
    marked_prose = 0
    # for prose pages, world+ambiguous unlocated numbers were marked inline; surface a count
    if not unresolved and unverified and not registered and not rec_here:
        marked_prose = unverified
    three = (" (checked against ClinicalTrials.gov + PubMed + Europe PMC)"
             if cascade_checked else "")
    parts = [
        f'<div id="{_BANNER_ID}" style="position:fixed;bottom:0;left:0;right:0;'
        f'z-index:2147483647;font-family:system-ui,Segoe UI,Arial,sans-serif;font-size:13px;'
        f'line-height:1.45;background:#0d1117;color:#e6edf3;border-top:3px solid #f0b429;'
        f'padding:8px 14px;box-shadow:0 -2px 10px rgba(0,0,0,.5);max-height:34vh;overflow:auto">',
        '<b style="color:#f0b429">&#128269; Provenance check (Overmind)</b> &nbsp;',
    ]
    if registered:
        parts.append(f'<span style="color:#3fb950">&#10003; {registered} trial record(s) '
                     f'registry-linked (cited trial resolves in ClinicalTrials.gov/AACT)</span>')
    if rec_here:
        parts.append(f' <span style="color:#3fb950">&#10003; {len(rec_here)} recovered</span> '
                     f'<span style="opacity:.9">&mdash; not in the registry snapshot but a real '
                     f'trial found in PubMed / Europe PMC (abstract available): '
                     f'{_esc(", ".join(rec_here))}</span>')
    if marked_prose:
        parts.append(f'<span style="color:#d29922">&#9888; {marked_prose} number(s) on this '
                     f'page marked UNVERIFIED &mdash; no resolvable trial id</span>')
    if unresolved:
        fabricated, real_unv = _fabricated_partition(unresolved)
        parts.append(' &nbsp;&middot;&nbsp; ')
        if real_unv:
            tail = (f'not found in ClinicalTrials.gov, PubMed, or Europe PMC{three} '
                    f'&mdash; unverified (may be fabricated or newer than all three sources)'
                    if cascade_checked else
                    'cited trial NOT found in the registry (unverified; may be fabricated '
                    'or newer than snapshot)')
            parts.append(f'<span style="color:#f85149;font-weight:bold">&#9888; '
                         f'{len(real_unv)} UNVERIFIED</span> <span style="opacity:.9">&mdash; '
                         f'{tail}: {_esc(", ".join(real_unv))}</span>')
        if fabricated:
            absent = ("absent from ClinicalTrials.gov, PubMed AND Europe PMC (all three "
                      "layers checked)" if cascade_checked else
                      "non-resolving placeholder / sequential-block id, absent from "
                      "ClinicalTrials.gov/AACT")
            parts.append(f' <span style="color:#ff6a69;font-weight:bold">&#9940; '
                         f'{len(fabricated)} LIKELY FABRICATED</span> <span style="opacity:.9">'
                         f'&mdash; {absent} &mdash; must NOT be treated as evidence: '
                         f'{_esc(", ".join(fabricated))}</span>')
    if not registered and not unresolved and not marked_prose and not rec_here:
        parts.append('<span style="color:#3fb950">&#10003; no unlocated world-claim numbers '
                     'detected on this page</span>')
    parts.append('</div>')
    return "".join(parts)


def inject_banner(text: str, counts: "CascadeCounts") -> str:
    """Insert the visible banner right after <body>. Idempotent (skips if already present)."""
    if _BANNER_ID in text:
        return text
    banner = render_provenance_banner(counts)
    m = _BODY_OPEN.search(text)
    if m:
        return text[:m.end()] + banner + text[m.end():]
    return banner + text   # no <body> (fragment) — prepend so it is still visible


# --------------------------------------------------------------------------
# Corpus staging — run across the app pages, report per app, write to STAGING.
# --------------------------------------------------------------------------

@dataclass
class StageReport:
    staged: int = 0
    per_app: list[CascadeCounts] = field(default_factory=list)

    @property
    def total_world(self) -> int:
        return sum(c.world for c in self.per_app)

    @property
    def total_ambiguous(self) -> int:
        return sum(c.ambiguous for c in self.per_app)

    @property
    def total_located(self) -> int:
        return sum(c.located for c in self.per_app)

    @property
    def total_unverified(self) -> int:
        return sum(c.unverified for c in self.per_app)


def _process_one(rf: "Retrofit", text: str, html: bool) -> tuple[str, "CascadeCounts"]:
    """Produce the retrofit output for ONE document, choosing the SAFE path per type:

      * structured app page (has source_tier records) -> rewrite source_tier values
        (surgical JSON-value change) + inject the visible banner.
      * HTML PROSE page (no records) -> banner ONLY. The inline text annotator can append
        a <span> inside a <script> data literal on some pages (found on apply-day: 24/511
        prose pages), which would corrupt the JS. So for HTML we do NOT modify the body
        inline — the banner (computed from the same counts) is the visible layer, and it
        cannot corrupt the page. Counts are still computed via annotate() for the banner.
      * MARKDOWN / non-HTML -> inline annotation (no scripts to corrupt) + no banner.
    """
    if html and _TIER_RECORD.search(text):
        out, counts = rf.retrofit_app_page_tiers(text)
        return inject_banner(out, counts), counts
    if html:
        # compute counts by annotating a COPY, but ship the ORIGINAL body + banner only
        _annot, counts = rf.annotate(text, html=True)
        return inject_banner(text, counts), counts
    # markdown / fragment: inline annotation is safe (no <script> data literals)
    return rf.annotate(text, html=False)


def stage_corpus(paths: Iterable[str], staging_dir: str, *,
                 retrofit: Optional[Retrofit] = None,
                 apply_in_place: bool = False) -> StageReport:
    """Run the cascade over each app page. By default writes an ANNOTATED COPY under
    `staging_dir` (never over the live page) and records per-app located/unverified.

    `apply_in_place=True` is the ship path Mahmood runs after review — it rewrites the
    live page. This function NEVER sets that itself; it is opt-in by the caller."""
    rf = retrofit or Retrofit()
    rep = StageReport()
    os.makedirs(staging_dir, exist_ok=True)
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        html = p.lower().endswith((".html", ".htm"))
        annotated, counts = _process_one(rf, text, html)
        counts.path = p
        rep.per_app.append(counts)
        target = p if apply_in_place else os.path.join(staging_dir, os.path.basename(p))
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(annotated)
        rep.staged += 1
    return rep


if __name__ == "__main__":
    # The ship path. STAGED by default (writes annotated copies to --staging, never over
    # the live page). Mahmood runs `--apply` to rewrite the live pages in place AFTER
    # review. Reports located vs unverified per class.
    import argparse
    import glob as _glob

    ap = argparse.ArgumentParser(description="Retrofit: locate-then-mark app-page world-claims")
    ap.add_argument("corpus", help="directory of app pages, or a glob")
    ap.add_argument("--staging", default="./retrofit-staging", help="where annotated copies go")
    ap.add_argument("--apply", action="store_true",
                    help="DANGER: rewrite live pages in place (default is staged copies)")
    a = ap.parse_args()
    if os.path.isdir(a.corpus):
        paths = sorted(_glob.glob(os.path.join(a.corpus, "*.html")) +
                       _glob.glob(os.path.join(a.corpus, "*.md")))
    else:
        paths = sorted(_glob.glob(a.corpus))
    rf = Retrofit()
    struct, prose = [], []
    for p in paths:
        try:
            txt = open(p, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        is_html = p.lower().endswith((".html", ".htm"))
        new, c = _process_one(rf, txt, is_html)
        (struct if (is_html and _TIER_RECORD.search(txt)) else prose).append(c)
        c.path = p
        tgt = p if a.apply else os.path.join(a.staging, os.path.basename(p))
        os.makedirs(os.path.dirname(tgt) or ".", exist_ok=True)
        open(tgt, "w", encoding="utf-8").write(new)
    s_rec = sum(c.world for c in struct); s_loc = sum(c.located_registry for c in struct)
    p_num = sum(c.world + c.ambiguous for c in prose); p_unv = sum(c.unverified for c in prose)
    print(f"structured app-data pages: {len(struct)}  records: {s_rec}  "
          f"located(registry): {s_loc}  unverified: {s_rec - s_loc}")
    print(f"prose HTML pages: {len(prose)}  claim numbers: {p_num}  "
          f"unverified(marked): {p_unv}")
    print(f"mode: {'APPLIED IN PLACE' if a.apply else 'STAGED (copies in ' + a.staging + ')'}")
