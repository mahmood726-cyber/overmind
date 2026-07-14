"""The backstop — assume a lane escaped. Re-derive what we already ship.

The gates stop the NEXT bad number. This sweep asks the harder question about
the numbers ALREADY in our deliverables, slides, and app pages: if each had to
pass the export channel today, how many would? A number in a markdown report
with no NCT/PMID/DOI beside it has no locator to follow — it would be REFUSED.

This is deliberately unflattering. The point is to name the honest state of the
system, not to pass. Mahmood: *"Report how many numbers we are currently shipping
that would fail the gates. I expect it to be ugly. Report it anyway."*

Method (conservative — it UNDER-counts failures if anything):
  1. Extract claim-shaped numbers from each deliverable: percentages, effect
     sizes / proportions (decimals with >=2 sig figs), and N= counts.
  2. For each, look in the SAME sentence for a dereferenceable id (NCT/PMID/
     PMC/DOI). No id in the sentence  ->  the number has no locator  ->  it would
     fail the export gate's locator requirement.
  3. For the ones that DO cite an NCT, actually resolve it against AACT and
     report how many of those NCTs even exist.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable

from .resolver import LocatorResolver, default_resolver

# claim-shaped numbers (not every digit — dates, versions, line refs are excluded)
_PCT = re.compile(r"(?<![\w.])\d{1,3}(?:\.\d+)?\s?%")
_PROP = re.compile(r"(?<![\w.])0?\.\d{2,}")               # 0.67, .921 — proportions/effects
_RATIO = re.compile(r"\b(?:RR|OR|HR|SMD|MD)\s*[=:]?\s*\d+\.\d+", re.IGNORECASE)
_N = re.compile(r"\b[Nn]\s*=\s*\d{2,}")
_ID_IN_CONTEXT = re.compile(r"NCT\d{8}|PMID:?\s?\d+|PMC\d+|10\.\d{4,9}/\S+", re.IGNORECASE)
_NCT = re.compile(r"NCT\d{8}", re.IGNORECASE)
# lines that are code/version/date noise, not prose claims
_NOISE_LINE = re.compile(r"^\s*(?:[#>|`]|\d+\.\d+\.\d+|commit\b|\* )", re.IGNORECASE)


# --- world-claim vs internal classification (the retrofit's denominator fix) ---
# A number FAILS the export gate only if it is a WORLD-CLAIM: a fact about a trial,
# an effect, or a corpus statistic that a reader would act on. Numbers ABOUT the
# harness itself — test counts, timings, file counts, versions, loop indices — are
# INTERNAL: they need no NCT/PMID locator and inflating the fail-count with them is
# dishonest in the OTHER direction. This classifier narrows the 36-89% band.
_WORLD_TOKENS = re.compile(
    r"\b(?:RR|OR|HR|SMD|MD|CI|AUC|SROC|recall|sensitiv|specific|efficac|mortalit|"
    r"survival|hazard|odds|risk\s?ratio|relative\s?risk|pooled|meta[- ]?analys|"
    r"prevalence|incidence|response\s?rate|remission|patients?|participants?|"
    r"subjects?|enrol|randomi|placebo|arm\b|dose|outcome|endpoint|trial|cohort|"
    r"coverage|poolab|adjudic|p\s?[=<>]|tau\^?2|I\^?2|heterogeneit|effect\s?size"
    # Codex round-4 false-negatives: clinical claims with no stats keyword. Positively
    # catch the biomarker names, change verbs, and clinical timepoints they used, so
    # 'LDL-C fell by 38.1% after 12 weeks' / 'adverse events in 14%' classify as world
    # WITHOUT flipping the default (which over-marked every bare number to 93%).
    r"|LDL|HDL|HbA1c|cholesterol|glucose|glyca|blood\s?pressure|systolic|diastolic|"
    r"adverse|serious\s?event|event\s?rate|biomarker|baseline|follow[- ]?up|"
    r"reduc|decreas|increas|improv|\bfell\b|\brose\b|declin|elevat|lower(?:ed|ing)?|"
    r"\bweeks?\b|\bmonths?\b|\bdays?\b|per\s?cent|percentage\s?point"
    # Codex round-5: lab markers described with 'test result' were caught by the
    # internal 'test' token. Named clinical markers make world win (checked first).
    r"|eGFR|GFR|creatinin|CRP|proBNP|BNP|troponin|bilirubin|albumin|ferritin|"
    r"\bALT\b|\bAST\b|ejection\s?fraction|LVEF|viral\s?load|CD4|proteinuria|"
    r"lab\s?(?:test|result|value)|assay|titer|titre)",
    re.IGNORECASE)
_INTERNAL_TOKENS = re.compile(
    # Codex round-6: bare 'test' forced clinical instruments ('WOMAC pain test',
    # 'tuberculin skin test', '6-minute walk test') into 'internal' (unmarked). Require
    # 'test' in a CODE context (unit test, test suite/case/file, tests pass/green) — a
    # clinical 'test' now falls through to 'ambiguous', which IS marked on screen.
    r"\b(?:unit\s?test|test\s?(?:suite|case|file|count|harness|runner)|"
    r"tests?\s?(?:pass|passed|green|fail|failed|collected|ran)|passed|pass\b|green|"
    r"assert|coverage\s?run|file|files|line|lines|"
    r"commit|version|v\d|python|node|npm|pytest|duckdb|sqlite|seed|port|iteration|"
    r"epoch|byte|bytes|second|seconds|elapsed|latency|throughput|"
    r"loop|index|offset|branch|rule|rules|repo|repos|LOC\b|snippet)"
    # size / timing units attached to a number are harness internals, not world-claims
    r"|\d+(?:\.\d+)?\s?(?:[KMGT]B|[GM]Hz|ms|s|MB|GB)\b",
    re.IGNORECASE)


def classify_number(sentence: str) -> str:
    """world | internal. Ratios (RR/OR/HR) are always world-claims. Otherwise a number
    is INTERNAL only when its sentence carries harness/code vocabulary (test, file,
    version, timing) AND no trial/effect token — everything else defaults to WORLD.

    Codex round-4 caught the prior default ('no vocabulary -> internal') hiding real
    clinical claims: 'LDL-C fell by 38.1% after 12 weeks', 'adverse events in 14%',
    'event rate was 12%' carried no token in the narrow world list and slipped past
    UNVERIFIED marking. Flipping the default fails toward marking — a bare clinical
    percentage is treated as a world-claim that needs a locator, not silently kept."""
    if re.search(r"\b(?:RR|OR|HR|SMD|MD)\s*[=:]?\s*\d", sentence):
        return "world"
    world = bool(_WORLD_TOKENS.search(sentence))
    internal = bool(_INTERNAL_TOKENS.search(sentence))
    if world:
        return "world"
    if internal:
        return "internal"
    # A claim-shaped number with NEITHER vocabulary is genuinely ambiguous. Report it
    # as its own class so the retrofit denominator is a RANGE, not a default-driven
    # point: world-claims are the lower bound, world+ambiguous the upper bound. (A pure
    # default here — internal OR world — just moves the bias; naming the ambiguity is
    # the honest narrowing.)
    return "ambiguous"


# --- the different-family classifier layer (the ambiguous-tail shrink, Fix #4) ---
# The regex classifier's "ambiguous" band is same-family (one author's vocabulary). A
# DIFFERENT family (Codex/GPT-5 or agy/Gemini) decorrelates it — the whole point. We do
# NOT trust the second family to run live on every number (it is a model, not a gate);
# instead its verdicts on the AMBIGUOUS band are cached to a data file and consulted here.
# A sentence the second family ALSO could not decide stays "ambiguous" and is still marked
# on screen — bounded and visible beats precise and wrong.
import json as _json

_SECOND_FAMILY: dict | None = None


def _second_family_verdicts() -> dict:
    global _SECOND_FAMILY
    if _SECOND_FAMILY is None:
        path = os.path.join(os.path.dirname(__file__), "data", "second_family_verdicts.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                _SECOND_FAMILY = _json.load(fh).get("verdicts", {})
        except (OSError, ValueError):
            _SECOND_FAMILY = {}
    return _SECOND_FAMILY


def classify_with_second_family(sentence: str) -> str:
    """world | internal | ambiguous, consulting a cached DIFFERENT-FAMILY verdict for the
    regex-ambiguous band. If the regex is already decisive (world/internal) that stands;
    only the 'ambiguous' residual is offered to the second family, and only its
    world/internal decisions are taken — a second-family 'ambiguous' (or an unseen
    sentence) stays ambiguous and is still marked. Decorrelation, not a same-author guess."""
    base = classify_number(sentence)
    if base != "ambiguous":
        return base
    key = re.sub(r"\s+", " ", sentence).strip()[:160]
    verdict = _second_family_verdicts().get(key)
    if verdict in ("world", "internal"):
        return verdict
    return "ambiguous"


def _destination_bucket(path: str) -> str:
    """Kampala's priority order: what a researcher sees FIRST. app-page > slides >
    deliverable. Used to order the retrofit, not to change the count."""
    low = path.lower()
    if low.endswith((".html", ".js", ".ipynb")):
        if "rapidmeta" in low or "app" in low or "dashboard" in low or "students" in low:
            return "app_page"
        return "app_page"           # any html/js/notebook is a rendered surface
    if "slide" in low or "tuesday" in low or low.endswith(".pptx"):
        return "slides"
    return "deliverable"


@dataclass
class DocResult:
    path: str
    numbers: int = 0
    with_locator: int = 0        # id in the SAME sentence (strict co-location)
    doc_has_any_id: bool = False # any resolvable id anywhere in the document
    nct_cited: int = 0
    nct_resolved: int = 0
    samples_naked: list[str] = field(default_factory=list)
    world_numbers: int = 0       # DEFINITE world-claim (a trial/effect token present)
    world_located: int = 0       # definite world-claim WITH a co-located id
    ambiguous_numbers: int = 0   # neither world nor internal vocabulary — unknown
    ambiguous_located: int = 0
    internal_numbers: int = 0    # test counts / timings / versions — no locator needed
    bucket: str = "deliverable"  # app_page | slides | deliverable (priority order)

    @property
    def naked(self) -> int:
        return self.numbers - self.with_locator

    @property
    def world_unverified(self) -> int:
        """DEFINITE world-claims with NO co-located id — must be marked UNVERIFIED."""
        return self.world_numbers - self.world_located

    @property
    def ambiguous_unverified(self) -> int:
        return self.ambiguous_numbers - self.ambiguous_located


def _sentences(text: str) -> list[str]:
    # split on sentence/newline boundaries so a number and its citation must be
    # genuinely co-located, not paragraphs apart
    parts = re.split(r"(?<=[.!?])\s+|\n", text)
    return [p for p in parts if p.strip()]


def _claim_numbers(sentence: str) -> list[str]:
    hits = []
    for rx in (_PCT, _RATIO, _N, _PROP):
        hits += rx.findall(sentence)
    return hits


def sweep_text(text: str, path: str, resolver: LocatorResolver) -> DocResult:
    res = DocResult(path=path)
    res.doc_has_any_id = bool(_ID_IN_CONTEXT.search(text))
    res.bucket = _destination_bucket(path)
    for sent in _sentences(text):
        if _NOISE_LINE.match(sent):
            continue
        nums = _claim_numbers(sent)
        if not nums:
            continue
        has_id = bool(_ID_IN_CONTEXT.search(sent))
        nct = _NCT.search(sent)
        kind = classify_number(sent)
        for _n in nums:
            res.numbers += 1
            if kind == "world":
                res.world_numbers += 1
                if has_id:
                    res.world_located += 1
            elif kind == "ambiguous":
                res.ambiguous_numbers += 1
                if has_id:
                    res.ambiguous_located += 1
            else:
                res.internal_numbers += 1
            if has_id:
                res.with_locator += 1
            elif kind == "world" and len(res.samples_naked) < 3:
                res.samples_naked.append(sent.strip()[:110])
            if nct:
                res.nct_cited += 1
                if resolver.resolve(nct.group(0)).resolved:
                    res.nct_resolved += 1
    return res


def sweep_files(paths: Iterable[str], *, resolver: LocatorResolver | None = None) -> dict:
    resolver = resolver or default_resolver()
    docs = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        docs.append(sweep_text(text, p, resolver))
    total = sum(d.numbers for d in docs)
    located = sum(d.with_locator for d in docs)
    # Lower bound on failure: a number in a document that contains NO resolvable id
    # anywhere cannot possibly be dereferenced. Numbers in docs that DO cite an id
    # somewhere *might* be traceable (though the export gate still needs a per-number
    # locator). Reporting both bounds answers the reviewers' co-location critique.
    in_docs_with_no_id = sum(d.numbers for d in docs if not d.doc_has_any_id)
    # THE RETROFIT DENOMINATOR FIX: of all claim-shaped numbers, how many are
    # world-claims (need a locator) vs internal (test counts/timings/versions)?
    world = sum(d.world_numbers for d in docs)
    world_located = sum(d.world_located for d in docs)
    ambiguous = sum(d.ambiguous_numbers for d in docs)
    ambiguous_located = sum(d.ambiguous_located for d in docs)
    internal = sum(d.internal_numbers for d in docs)
    # per-destination rollup, in Kampala's priority order
    buckets: dict[str, dict] = {}
    for d in docs:
        b = buckets.setdefault(d.bucket, {"documents": 0, "world": 0, "located": 0,
                                          "unverified": 0, "ambiguous": 0, "internal": 0})
        b["documents"] += 1
        b["world"] += d.world_numbers
        b["located"] += d.world_located
        b["unverified"] += d.world_unverified
        b["ambiguous"] += d.ambiguous_numbers
        b["internal"] += d.internal_numbers
    return {
        "documents": len(docs),
        "numbers": total,
        "with_locator": located,
        # strict co-location: an UPPER bound on how many would fail the export gate
        # (the gate does require each number to carry its own locator)
        "would_fail_export_gate": total - located,
        "fail_fraction": (total - located) / total if total else 0.0,
        # document-level: a LOWER bound (no id anywhere -> definitely undereferenceable)
        "no_id_in_document": in_docs_with_no_id,
        "lower_bound_fail_fraction": in_docs_with_no_id / total if total else 0.0,
        "nct_cited": sum(d.nct_cited for d in docs),
        "nct_resolved": sum(d.nct_resolved for d in docs),
        # --- the narrowed denominator, as an honest RANGE ---
        "world_numbers": world,               # DEFINITE world-claims (lower bound)
        "world_located": world_located,
        "world_unverified": world - world_located,
        "ambiguous_numbers": ambiguous,       # neither vocabulary — the uncertainty band
        "ambiguous_located": ambiguous_located,
        "ambiguous_unverified": ambiguous - ambiguous_located,
        "internal_numbers": internal,         # DEFINITE internal — not a gate failure
        # world-claim denominator range: [definite world, world+ambiguous]
        "world_denom_low": world,
        "world_denom_high": world + ambiguous,
        # unverified world-claims range (must be marked): low..high
        "unverified_low": world - world_located,
        "unverified_high": (world - world_located) + (ambiguous - ambiguous_located),
        "world_fraction_of_all": world / total if total else 0.0,
        "world_fail_fraction": (world - world_located) / world if world else 0.0,
        "by_bucket": buckets,
        "per_doc": docs,
    }


_UNVERIFIED_MD = " [UNVERIFIED: no resolvable trial id]"
_UNVERIFIED_HTML = ' <span class="overmind-unverified" title="no resolvable trial id — not gate-verified">⚠ UNVERIFIED</span>'


def mark_unverified(text: str, *, html: bool = False) -> tuple[str, int]:
    """The retrofit ACTION, not just the count: annotate every world-claim number in
    a sentence that has NO co-located resolvable id with a visible UNVERIFIED marker.
    A number we cannot dereference is shown as un-verified on screen — never silently
    kept. Idempotent (skips already-marked sentences) and conservative (only marks
    world-claim sentences, so test counts/timings are left alone). Returns
    (annotated_text, count_marked). This is what a RapidMeta app page / slide export
    runs so Kampala sees which numbers are backed by a real locator and which are not."""
    marker = _UNVERIFIED_HTML if html else _UNVERIFIED_MD
    already = "overmind-unverified" if html else "UNVERIFIED"
    out_lines = []
    marked = 0
    for line in text.splitlines():
        if _NOISE_LINE.match(line) or already in line:
            out_lines.append(line)
            continue
        nums = _claim_numbers(line)
        has_id = bool(_ID_IN_CONTEXT.search(line))
        # On screen, mark BOTH definite world-claims AND ambiguous numbers with no id —
        # only DEFINITE internal (test counts/timings) is left alone. Fail toward
        # marking: a reader seeing UNVERIFIED on a truly-internal number loses nothing;
        # a reader NOT seeing it on a real un-located world-claim is the F1 mistake.
        if nums and not has_id and classify_number(line) in ("world", "ambiguous"):
            out_lines.append(line.rstrip() + marker)
            marked += 1
        else:
            out_lines.append(line)
    return "\n".join(out_lines), marked


def _iter_deliverables(root: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        for fn in filenames:
            # residual #4: cover the reflective / non-Python surfaces too — a
            # world-claim rendered in an .html app page, a .js bundle, or an .ipynb
            # notebook is just as un-gated as one in Python. Named + now measured.
            if fn.endswith((".md", ".html", ".js", ".ipynb")):
                out.append(os.path.join(dirpath, fn))
    return out


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if len(args) == 1 and os.path.isdir(args[0]):
        files = _iter_deliverables(args[0])
    else:
        files = args
    r = sweep_files(files)
    print(f"documents scanned:        {r['documents']}")
    print(f"claim-shaped numbers:     {r['numbers']}")
    print(f"  with co-located id:     {r['with_locator']}")
    print(f"  UPPER-bound fail (strict co-location): {r['would_fail_export_gate']} "
          f"({r['fail_fraction']*100:.1f}%)")
    print(f"  LOWER-bound fail (no id anywhere in doc): {r['no_id_in_document']} "
          f"({r['lower_bound_fail_fraction']*100:.1f}%)")
    print(f"NCTs cited / resolved:    {r['nct_cited']} / {r['nct_resolved']}")
