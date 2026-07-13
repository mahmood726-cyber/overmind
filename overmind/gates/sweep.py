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


@dataclass
class DocResult:
    path: str
    numbers: int = 0
    with_locator: int = 0        # id in the SAME sentence (strict co-location)
    doc_has_any_id: bool = False # any resolvable id anywhere in the document
    nct_cited: int = 0
    nct_resolved: int = 0
    samples_naked: list[str] = field(default_factory=list)

    @property
    def naked(self) -> int:
        return self.numbers - self.with_locator


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
    for sent in _sentences(text):
        if _NOISE_LINE.match(sent):
            continue
        nums = _claim_numbers(sent)
        if not nums:
            continue
        has_id = bool(_ID_IN_CONTEXT.search(sent))
        nct = _NCT.search(sent)
        for _n in nums:
            res.numbers += 1
            if has_id:
                res.with_locator += 1
            elif len(res.samples_naked) < 3:
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
        "per_doc": docs,
    }


def _iter_deliverables(root: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "__pycache__")]
        for fn in filenames:
            if fn.endswith((".md", ".html")):
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
