"""Comparison / both-arms gate — the trial-level PICO check the arm gate can't see.

The arm gate (channel._guard_semantic + group_code) binds a number to the RIGHT
arm of a trial. It is blind to a different selection error, found on live data by
a real user in AMOXICILLIN_AOM: the number is correctly arm-bound, the NCT
resolves, the arm count is 2 — arithmetic + identity + arm gates all PASS — but
the TRIAL is a wrong-comparison inclusion because the drug of interest is present
in ALL randomised arms (background co-therapy); the randomised contrast is a
DIFFERENT agent.

Concrete: NCT03818815 (OP0201 for acute otitis media). Arms:
  ['Drug: OP0201 + Antibiotics', 'Placebo Comparator: Placebo +Antibiotics']
Amoxicillin-clavulanate was given to BOTH arms; the contrast was intranasal
OP0201 vs placebo (Pediatrics 2021, DOI 10.1542/peds.2021-051703). Pooling it in
an Augmentin-efficacy meta-analysis estimates nothing about Augmentin.

This gate fires when a claim declares it is a pooled drug-efficacy datum, i.e.
meta['drug_of_interest'] is set. It then REQUIRES meta['trial_arms'] (the trial's
arm labels) and BLOCKS when the drug is active in every arm and the design is not
a crossover (which has a within-subject placebo contrast). Fail closed: once the
drug is declared, an undeclared arm list is refused, not waved through.

Corpus measurement (both_arms_detector, 2026-07-14): 57/395 apps with parseable
arm metadata pool >=1 trial where the drug is active in all arms; 23 are the
TIER1 'different active agent is the contrast' class (OP0201, pembro+lenvatinib,
belimumab+rituximab, sunitinib+LY2510924, ...).
"""
from __future__ import annotations

import re
from .contract import Claim


class ComparisonError(RuntimeError):
    """A pooled drug-efficacy claim rests on a trial whose randomised contrast is
    NOT the drug of interest (the drug is background in all arms). Nothing emitted."""


# antibiotic class — so 'amoxicillin' matches an arm labelled only 'Antibiotics'
_ANTIBIOTICS = {
    "amoxicillin", "augmentin", "amox", "ampicillin", "penicillin", "azithromycin",
    "clarithromycin", "cefdinir", "cefaclor", "cefuroxime", "ceftriaxone",
    "clavulanate", "doxycycline", "erythromycin", "clindamycin", "antibiotic",
    "antibiotics",
}
_CLASS_MAP = {"antibiotics": _ANTIBIOTICS}

_DOSE = re.compile(
    r"\b\d+(\.\d+)?\s*(mg|mcg|µg|μg|g|kg|ml|iu|units?|q\d*w|qd|bid|tid|weekly|daily|"
    r"every|/kg|/day)\b", re.I)
_NOISE = re.compile(
    r"\b(arm|arms|group|groups|cohort|cohorts|drug|comparator|open|label|part|phase|"
    r"dose|dosing|regimen|standard|high|low|maximum|matching|match|iv|oral|sc|"
    r"subcutaneous|intranasal|active|experimental|control|followed|then|first|second|"
    r"third|expansion|titration|skipping|period|healthy|chronic|naive|refractory|"
    r"reduction|interval|prolongation|addendum|excluding|non|responder|responders)\b",
    re.I)


def _norm(s: str) -> str:
    s = (s or "").lower().replace("→", " / ")
    s = re.sub(r"[^a-z0-9+/\-\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _agentify(piece: str) -> set[str]:
    out = set()
    for m in re.findall(r"\b[a-z]{2,}-?\d{2,}\b", piece):   # op0201, bay2433334, ly2510924
        out.add(m.replace("-", ""))
    p = _DOSE.sub(" ", piece)
    p = re.sub(r"\b\d+\b", " ", p)
    p = re.sub(r"[^a-z\s\-]", " ", p)
    p = _NOISE.sub(" ", p)
    p = re.sub(r"\s+", " ", p).strip(" -")
    for w in p.split():
        w = w.strip("-")
        if len(w) >= 4:
            out.add(w)
    return out


def _active_agents(arm: str) -> set[str]:
    """ACTIVE (non-placebo) agents in an arm label; placebo pieces are dropped."""
    agents: set[str] = set()
    for piece in re.split(r"[+/,;]| vs | then | followed by ", _norm(arm)):
        piece = piece.strip()
        if not piece or "placebo" in piece:
            continue
        agents |= _agentify(piece)
    return agents


def _is_crossover(arm: str) -> bool:
    a = _norm(arm)
    return "placebo" in a and bool(
        re.search(r"\bthen\b|→|placebo\s*/\s*\w|\w\s*/\s*placebo", a))


def _class_members(drug: str) -> set[str] | None:
    for members in _CLASS_MAP.values():
        if drug in members:
            return members
    return None


def _drug_active_in(arm: str, drug: str, members: set[str] | None) -> bool:
    agents = _active_agents(arm)
    for w in agents:
        if drug in w or w in drug:
            return True
    if members:
        for w in agents:
            if w in members:
                return True
    return False


def evaluate(drug: str, arms: list[str]) -> tuple[bool, str]:
    """Return (is_wrong_comparison, reason). A wrong comparison = drug active in ALL
    arms (not crossover), so the randomised contrast is something other than the drug."""
    arms = [a for a in (arms or []) if str(a).strip()]
    if len(arms) < 2:
        return (False, "fewer than 2 arm labels — cannot assess comparison")
    drug = (drug or "").lower().strip()
    members = _class_members(drug)
    active = [_drug_active_in(a, drug, members) for a in arms]
    if not all(active):
        return (False, "drug active in only some arms — normal drug-vs-control design")
    if any(_is_crossover(a) for a in arms):
        return (False, "crossover / delayed-start — within-subject placebo contrast exists")
    # drug active in all arms: identify the real contrast agent(s), if any
    per_arm = [_active_agents(a) for a in arms]

    def _is_drug(w: str) -> bool:
        return drug in w or w in drug or bool(members and w in members)

    non_drug = [{w for w in s if not _is_drug(w)} for s in per_arm]
    union = set().union(*non_drug) if non_drug else set()
    inall = set.intersection(*non_drug) if non_drug and all(non_drug) else set()
    contrast = sorted(union - inall)
    if contrast:
        return (True, f"drug {drug!r} active in ALL arms; randomised contrast is a "
                      f"different agent ({', '.join(contrast)}) — background co-therapy")
    return (True, f"drug {drug!r} active in ALL arms; only dose/schedule differs — "
                  f"no drug-vs-control contrast")


def guard_comparison(claim: Claim) -> None:
    """Fires only for a claim that declares meta['drug_of_interest'] (a pooled
    drug-efficacy datum). Then meta['trial_arms'] is REQUIRED and the drug must not
    be the background co-therapy of every arm. No-op for claims that do not declare
    a drug of interest — backward compatible, but fail-closed once declared."""
    meta = getattr(claim, "meta", None) or {}
    drug = str(meta.get("drug_of_interest") or "").strip()
    if not drug:
        return  # not a pooled drug-efficacy claim — this gate does not apply
    arms = meta.get("trial_arms")
    if not isinstance(arms, (list, tuple)) or not arms:
        raise ComparisonError(
            f"REFUSED (comparison-UNVERIFIED): {claim.text!r} declares "
            f"drug_of_interest={drug!r} but no meta['trial_arms']. A pooled "
            f"drug-efficacy datum must declare the trial's arm labels so the gate can "
            f"confirm the drug is the randomised contrast, not background co-therapy "
            f"present in every arm (the OP0201/NCT03818815 selection error).")
    wrong, reason = evaluate(drug, list(arms))
    if wrong:
        raise ComparisonError(
            f"REFUSED (wrong comparison): {claim.text!r} pooled under drug {drug!r}, but "
            f"{reason}. Arms={list(arms)!r} at {claim.locator!r}. This trial does not "
            f"estimate {drug!r} vs control — exclude it or restate the question.")
