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
)

# Tiers, strongest to weakest. The tag shown on screen IS the grade.
TIER_REGISTRY = "registry"
TIER_OA = "oa_table"
TIER_ABSTRACT = "abstract"
TIER_UNVERIFIED = "unverified"

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
    TIER_REGISTRY: " [registry]",
    TIER_OA: " [OA table]",
    TIER_ABSTRACT: " [abstract]",
    TIER_UNVERIFIED: " [UNVERIFIED: no resolvable trial id]",
}
_TAG_HTML = {
    TIER_REGISTRY: ' <span class="om-tier om-registry" title="located: NCT resolves in AACT registry">✓ registry</span>',
    TIER_OA: ' <span class="om-tier om-oa" title="located: recovered from Open-Access JATS results table">✓ OA table</span>',
    TIER_ABSTRACT: ' <span class="om-tier om-abstract" title="located: found in PubMed abstract">~ abstract</span>',
    TIER_UNVERIFIED: ' <span class="om-tier om-unverified" title="no resolvable locator — not gate-verified">⚠ UNVERIFIED</span>',
}
# a page already carrying any tier tag is idempotent-skipped
_ALREADY = re.compile(r'om-tier|UNVERIFIED|\[registry\]|\[OA table\]|\[abstract\]')


@dataclass
class CascadeCounts:
    """Per-document tally, by the tier that located each world-claim number."""
    path: str
    world: int = 0                 # definite world-claim numbers
    ambiguous: int = 0             # neither vocabulary — also marked, own class
    located_registry: int = 0
    located_oa: int = 0
    located_abstract: int = 0
    unverified: int = 0            # survived the whole cascade with no locator
    oa_attempts: int = 0           # numbers the OA layer was asked to recover
    abstract_attempts: int = 0     # numbers the abstract layer was asked to recover
    page_ncts: int = 0
    page_ncts_resolved: int = 0

    @property
    def located(self) -> int:
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

    def _locate(self, sentence: str, pool: dict[str, bool],
                counts: CascadeCounts) -> str:
        """The cascade for ONE world-claim/ambiguous number's sentence. Returns the tier."""
        # layer 1 — registry: a resolvable NCT co-located in the same sentence.
        m = _NCT.search(sentence)
        if m and pool.get(m.group(0).upper(), False):
            return TIER_REGISTRY
        # a co-located non-NCT resolvable id (PMID/PMC/DOI) is a locator, but we only
        # confirm it against ground truth for NCT (AACT) offline. A resolvable-syntax
        # PMID with no reachable backend is NOT counted as located — that is exactly the
        # "gated laundering" the resolver refuses. So a PMID-only sentence falls through
        # to the OA/abstract layers, which fail closed offline -> unverified. Honest.

        # layer 2 — OA JATS table (fail closed offline, but COUNT the attempt)
        counts.oa_attempts += 1
        nct = m.group(0).upper() if m else None
        if nct and self.oa.recover(nct, None, None):
            return TIER_OA
        # layer 3 — PubMed abstract (fail closed offline, COUNT the attempt)
        counts.abstract_attempts += 1
        if nct and self.abstract.recover(nct, None, None):
            return TIER_ABSTRACT
        return TIER_UNVERIFIED

    def annotate(self, text: str, *, html: bool = False) -> tuple[str, CascadeCounts]:
        """Locate-then-mark every world-claim and ambiguous number, tagging each with the
        tier that located it (registry/OA/abstract) or UNVERIFIED. Idempotent. Only
        definite-internal numbers (test counts/timings/versions) are left untagged."""
        counts = CascadeCounts(path="")
        pool = self._page_nct_pool(text)
        counts.page_ncts = len(pool)
        counts.page_ncts_resolved = sum(1 for v in pool.values() if v)
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
            kind = classify_number(line)
            if kind not in ("world", "ambiguous"):
                out.append(line)          # definite internal — no locator needed
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
                elif tier == TIER_OA:
                    counts.located_oa += 1
                elif tier == TIER_ABSTRACT:
                    counts.located_abstract += 1
                else:
                    counts.unverified += 1
            # tag the line with the STRONGEST tier any of its numbers reached (a line
            # with a resolvable co-located NCT shows registry; a bare line shows
            # UNVERIFIED). One tag per line keeps the page readable.
            line_tier = self._line_tier(line, pool, counts)
            out.append(line.rstrip() + tags[line_tier])
        return "\n".join(out), counts

    def _locate_no_id(self, sentence: str, counts: CascadeCounts) -> str:
        """No id co-located at all. OA/abstract still get their (failing, counted)
        attempt so the report is honest about what was tried; then unverified."""
        counts.oa_attempts += 1
        counts.abstract_attempts += 1
        return TIER_UNVERIFIED

    def _line_tier(self, sentence: str, pool: dict[str, bool],
                   counts: CascadeCounts) -> str:
        """The strongest tier for the whole line (for the single on-screen tag). Does not
        re-count — counting already happened per-number in annotate()."""
        m = _NCT.search(sentence)
        if m and pool.get(m.group(0).upper(), False):
            return TIER_REGISTRY
        return TIER_UNVERIFIED


    # -- app-page structured retrofit (the SAFE app-page path) ---------------
    def retrofit_app_page_tiers(self, text: str) -> tuple[str, CascadeCounts]:
        """The app-page-safe retrofit: rewrite each embedded trial record's
        `source_tier` by running the cascade on its NCT, instead of appending markers to
        script blobs. `extracted` (the app's default, = unverified) is UPGRADED to
        `registry` when the NCT resolves in AACT, DOWNGRADED to `unverified` when the NCT
        is fabricated/unreachable. The page already renders `source_tier` as an on-screen
        badge, so this makes the grade visible where the researcher already looks — no
        markup surgery, no corruption risk. Idempotent (re-running yields the same tiers).

        Returns (new_text, counts) where counts.located_registry / counts.unverified are
        per-RECORD (one trial outcome), which is the granularity the cascade dereferences."""
        counts = CascadeCounts(path="")
        pool: dict[str, bool] = {}

        def _sub(m: re.Match) -> str:
            prefix, nct, _old_tier, close = m.group(1), m.group(2).upper(), m.group(3), m.group(4)
            if nct not in pool:
                pool[nct] = self._nct_resolves(nct)
            if pool[nct]:
                counts.located_registry += 1
                tier = TIER_REGISTRY
            else:
                # cascade layers 2/3 (OA/abstract) fail closed offline — counted, then unverified
                counts.oa_attempts += 1
                counts.abstract_attempts += 1
                counts.unverified += 1
                tier = TIER_UNVERIFIED
            counts.world += 1
            return f"{prefix}{tier}{close}"

        new = _TIER_RECORD.sub(_sub, text)
        counts.page_ncts = len(pool)
        counts.page_ncts_resolved = sum(1 for v in pool.values() if v)
        return new, counts


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
        # App pages carry structured `source_tier` records: retrofit those SAFELY (JSON
        # value rewrite, no script-blob corruption). Prose/markdown uses the text
        # annotator. A plain HTML page with no tier records also uses the text path,
        # which now skips <script>/<style> so it cannot corrupt embedded JS.
        if _TIER_RECORD.search(text):
            annotated, counts = rf.retrofit_app_page_tiers(text)
        else:
            annotated, counts = rf.annotate(text, html=html)
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
        if _TIER_RECORD.search(txt):
            new, c = rf.retrofit_app_page_tiers(txt); struct.append(c)
        else:
            new, c = rf.annotate(txt, html=p.lower().endswith((".html", ".htm"))); prose.append(c)
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
