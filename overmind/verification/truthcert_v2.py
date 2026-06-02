"""TruthCert v2 (Phase 2): evidence snapshot + per-project-type rubric scoring.

A **read-only overlay** on a signed ``CertBundle`` — it never mutates the bundle
(the bundle's signature covers ``witness_results``, so mutation would void it).
It adds two things the bare PASS/FAIL verdict lacks:

  1. **evidence_snapshot** — a curated, bounded proof per witness (the few key
     lines, not the full logs) plus provenance (source_hash, project_path).
     Portable and auditable: you can see *why* a verdict was reached without the
     raw multi-MB transcripts (the SmartSnap "judge the evidence" idea).

  2. **rubric score** — does the verdict's EVIDENCE meet what this project_type /
     risk tier should require? Catches **"CERTIFIED but vacuous"**: e.g. a browser
     app that "passed" only because it had no executed test witness (test_suite
     SKIP), or a math-heavy project certified without a numerical witness.

Pure-functional, stdlib only, deterministic. Operates on any object exposing the
CertBundle / WitnessResult / ScopeLock attributes (duck-typed for easy testing).
"""
from __future__ import annotations

import re

_PASS_VERDICTS = {"PASS", "CERTIFIED"}
_FAIL_VERDICTS = {"FAIL", "REJECT"}
_SALIENT = re.compile(r"\b(pass|fail|error|assert|traceback|ok|skip|warn|cve|vuln)", re.IGNORECASE)


def _key_lines(text: str, max_lines: int = 4, max_len: int = 200) -> list[str]:
    """A few salient lines from a witness log — prefer pass/fail/error markers,
    else the last non-empty lines. Each line truncated to keep snapshots small."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return []
    salient = [ln for ln in lines if _SALIENT.search(ln)]
    chosen = (salient or lines)[-max_lines:]
    return [(ln[:max_len] + "…") if len(ln) > max_len else ln for ln in chosen]


def build_evidence_snapshot(bundle) -> dict:
    lock = bundle.scope_lock
    witnesses = []
    for w in bundle.witness_results:
        log = w.stdout if w.stdout else w.stderr
        witnesses.append({
            "witness": w.witness_type,
            "verdict": w.verdict,
            "exit_code": w.exit_code,
            "elapsed_s": round(getattr(w, "elapsed", 0.0) or 0.0, 2),
            "evidence": _key_lines(log),
        })
    signed = bool(getattr(bundle, "signature_method", "") not in ("", "none"))
    return {
        "provenance": {
            "project_id": bundle.project_id,
            "project_path": getattr(lock, "project_path", None),
            "source_hash": getattr(lock, "source_hash", None),
            "verdict": bundle.verdict,
            "bundle_hash": getattr(bundle, "bundle_hash", None),
            "timestamp": getattr(bundle, "timestamp", None),
            "signed": signed,
        },
        "witnesses": witnesses,
    }


# Per-project-type rubric: which witness types must be PRESENT and not SKIP for
# the evidence to be considered complete. Keep conservative — only require what
# a type genuinely should have executed.
_RUBRICS: dict[str, dict] = {
    "browser_app": {"require_nonskip": ["test_suite"],
                    "note": "a browser app should have an executed test/E2E witness"},
    "hybrid_browser_analytics_app": {"require_nonskip": ["test_suite"],
                    "note": "analytics app should have executed tests"},
    "python_tool": {"require_nonskip": ["test_suite"],
                    "note": "a python tool should run its test suite"},
    "r_project": {"require_nonskip": ["test_suite"],
                    "note": "an R project should run validation/tests"},
    "unknown": {"require_nonskip": [], "note": "no type-specific evidence required"},
}


def _nonskip_types(bundle) -> set[str]:
    return {w.witness_type for w in bundle.witness_results if w.verdict != "SKIP"}


def _math_heavy(project) -> bool:
    return (int(getattr(project, "advanced_math_score", 0) or 0) >= 10
            or str(getattr(project, "advanced_math_rigor", "")).lower() in {"high", "extreme"})


def score_rubric(project, bundle) -> dict:
    ptype = getattr(project, "project_type", "unknown") or "unknown"
    rubric = _RUBRICS.get(ptype, _RUBRICS["unknown"])
    required = list(rubric["require_nonskip"])
    # Math-heavy projects must show a numerical witness regardless of type.
    if _math_heavy(project):
        required.append("numerical")

    present = _nonskip_types(bundle)
    met = [r for r in required if r in present]
    gaps = [r for r in required if r not in present]

    pass_like = bundle.verdict in _PASS_VERDICTS
    any_pass_witness = any(w.verdict == "PASS" for w in bundle.witness_results)
    # A pass-like verdict with NO executed PASS witness = vacuous (passed because
    # nothing actually ran).
    vacuous_pass = bool(pass_like and not any_pass_witness)

    score = 1.0 if not required else round(len(met) / len(required), 3)
    return {
        "project_type": ptype,
        "required_nonskip": required,
        "met": met,
        "gaps": gaps,
        "vacuous_pass": vacuous_pass,
        "score": score,
        "note": rubric["note"],
    }


def assess(project, bundle) -> dict:
    snapshot = build_evidence_snapshot(bundle)
    rubric = score_rubric(project, bundle)
    if bundle.verdict in _FAIL_VERDICTS:
        assessment = "fail"
    elif bundle.verdict in _PASS_VERDICTS and (rubric["gaps"] or rubric["vacuous_pass"]):
        assessment = "certified_with_gaps"
    elif bundle.verdict in _PASS_VERDICTS:
        assessment = "clean"
    else:
        assessment = bundle.verdict.lower()  # UNVERIFIED etc.
    return {
        "assessment": assessment,
        "verdict": bundle.verdict,
        "rubric": rubric,
        "evidence_snapshot": snapshot,
    }
