"""Multi-reviewer screening consensus with signed attestations (Phase 3 / #4).

Closes the "collaboration" gap competitors lead on, the local-first way:
each reviewer keeps a decisions file (JSONL, ideally on their own git branch);
this computes inter-rater agreement (Cohen's/Fleiss κ), the consensus decision
per item, and the conflicts that need adjudication — then **cryptographically
signs each reviewer's decision set** (TruthCert signer) so a decision set can't
be silently altered, and signs the consensus bundle.

Decisions file format (one JSON object per line):
    {"item_id": "PMID123", "decision": "include|exclude|maybe", "reason": "..."}
Reviewer identity = the JSON "reviewer" field, else the file stem.

Stdlib + the existing overmind signer; deterministic; offline.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from overmind.verification.signers import select_signer


def load_reviews(review_dir: Path) -> dict[str, dict[str, str]]:
    """Return {reviewer: {item_id: decision}} from *.jsonl in review_dir."""
    reviews: dict[str, dict[str, str]] = {}
    for f in sorted(Path(review_dir).glob("*.jsonl")):
        decisions: dict[str, str] = {}
        reviewer = f.stem
        for line in f.read_text(encoding="utf-8-sig").splitlines():  # tolerate BOM
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = obj.get("item_id")
            dec = (obj.get("decision") or "").lower()
            if item and dec:
                decisions[item] = dec
                if obj.get("reviewer"):
                    reviewer = obj["reviewer"]
        reviews[reviewer] = decisions
    return reviews


def _cohen_kappa(a: dict, b: dict, items: list[str]) -> float | None:
    if not items:
        return None
    cats = sorted({a[i] for i in items} | {b[i] for i in items})
    n = len(items)
    po = sum(1 for i in items if a[i] == b[i]) / n
    ca, cb = Counter(a[i] for i in items), Counter(b[i] for i in items)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 4)


def _fleiss_kappa(reviews: dict, items: list[str]) -> float | None:
    raters = list(reviews)
    n = len(raters)
    if n < 2 or not items:
        return None
    cats = sorted({reviews[r][i] for r in raters for i in items})
    N = len(items)
    p_j = {c: 0 for c in cats}
    Pbar_sum = 0.0
    for i in items:
        counts = Counter(reviews[r][i] for r in raters)
        for c in cats:
            p_j[c] += counts[c]
        Pi = (sum(counts[c] ** 2 for c in cats) - n) / (n * (n - 1))
        Pbar_sum += Pi
    Pbar = Pbar_sum / N
    for c in cats:
        p_j[c] /= (N * n)
    Pe = sum(v ** 2 for v in p_j.values())
    return 1.0 if Pe == 1 else round((Pbar - Pe) / (1 - Pe), 4)


def _consensus_decision(votes: list[str]) -> tuple[str, bool]:
    """(decision, is_conflict). Conflict = include AND exclude both present."""
    cnt = Counter(votes)
    conflict = cnt.get("include", 0) > 0 and cnt.get("exclude", 0) > 0
    decision = cnt.most_common(1)[0][0]
    return decision, conflict


def compute_consensus(reviews: dict[str, dict[str, str]]) -> dict:
    reviewers = list(reviews)
    all_items = sorted({i for d in reviews.values() for i in d})
    complete = [i for i in all_items if all(i in reviews[r] for r in reviewers)]

    consensus: dict[str, str] = {}
    conflicts: list[str] = []
    agree = 0
    for item in all_items:
        votes = [reviews[r][item] for r in reviewers if item in reviews[r]]
        dec, conflict = _consensus_decision(votes)
        consensus[item] = dec
        if conflict:
            conflicts.append(item)
        if item in complete and len(set(votes)) == 1:
            agree += 1

    kappa = (_cohen_kappa(*(reviews[r] for r in reviewers[:2]), complete)
             if len(reviewers) == 2 else _fleiss_kappa(reviews, complete))
    return {
        "reviewers": reviewers,
        "items_total": len(all_items),
        "items_complete": len(complete),
        "percent_agreement": round(agree / len(complete), 4) if complete else None,
        "kappa": kappa,
        "kappa_method": "cohen" if len(reviewers) == 2 else "fleiss",
        "conflicts": conflicts,
        "consensus": consensus,
    }


def _sign(payload: dict) -> dict:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    res = select_signer().sign(raw)
    return {
        "sha256": hashlib.sha256(raw).hexdigest()[:16],
        "method": res.method,
        "signature": res.signature[:24] + ("…" if len(res.signature) > 24 else ""),
        "signed": res.method not in ("", "none"),
    }


def attest(reviews: dict[str, dict[str, str]], consensus: dict) -> dict:
    reviewer_attestations = {
        reviewer: {"n_decisions": len(decisions), **_sign({"reviewer": reviewer, "decisions": decisions})}
        for reviewer, decisions in reviews.items()
    }
    consensus_attestation = _sign({"consensus": consensus["consensus"],
                                   "conflicts": consensus["conflicts"]})
    any_signed = any(a["signed"] for a in reviewer_attestations.values())
    return {
        "reviewer_attestations": reviewer_attestations,
        "consensus_attestation": consensus_attestation,
        "note": ("signed" if any_signed else
                 "UNSIGNED — set TRUTHCERT_HMAC_KEY or an Ed25519 key for real attestations"),
    }


def run(review_dir: Path) -> dict:
    reviews = load_reviews(review_dir)
    if not reviews:
        return {"error": f"no *.jsonl reviewer files in {review_dir}"}
    consensus = compute_consensus(reviews)
    consensus["attestations"] = attest(reviews, consensus)
    return consensus
