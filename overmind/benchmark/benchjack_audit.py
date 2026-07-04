"""In-house adversarial audit of the private eval (AN-7, arXiv:2605.12673 BenchJack).

Our moat (D6) is only as trustworthy as the benchmark is un-gameable. This is a
BenchJack-style audit **method** (not a dependency) that red-teams the private
corpus for ways an agent could score WITHOUT solving the task, run before any
evolution cycle promotes a candidate. Discovered exploits become **negative-memory
regression fixtures** — which grows the moat (T8).

Probes (all read-only, deterministic, no code exec):
  * id-leak — does the task id encode the label, and could it reach the reviewer prompt?
  * keyword-shortcut — does a fixed phrase perfectly separate a reviewer-only defect
    class from clean tasks (so a model could pattern-match wording, not substance)?
  * template-uniformity — are a class's reviewer-only artifacts near-identical?
  * canary-present — does a planted witness-detectable defect exist (found-nothing fence)?
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from overmind.benchmark.reviewers import build_prompt
from overmind.benchmark.tasks import CLEAN, REVIEWER_ONLY_KINDS


@dataclass(slots=True)
class AuditExploit:
    name: str
    severity: str            # P0 / P1 / P2
    detail: str
    fixture_hint: str = ""   # how to turn it into a negative-memory regression fixture

    def to_dict(self) -> dict:
        return {"name": self.name, "severity": self.severity, "detail": self.detail,
                "fixture_hint": self.fixture_hint}


@dataclass(slots=True)
class AuditReport:
    exploits: list[AuditExploit] = field(default_factory=list)
    n_tasks: int = 0

    @property
    def clean(self) -> bool:
        return not self.exploits

    def to_dict(self) -> dict:
        return {"clean": self.clean, "n_tasks": self.n_tasks,
                "exploits": [e.to_dict() for e in self.exploits]}


def _probe_id_leak(tasks, keys) -> list[AuditExploit]:
    out: list[AuditExploit] = []
    # (a) id encodes the label by suffix?
    leaky = [t.id for t in tasks if t.id.rsplit("__", 1)[-1] in {
        "clean", "impossible", "repro", "ci_invalid", "direction", "measure_label",
        "method_mismatch", "comparator_swap", "missing_reference", "subgroup_mismatch"}]
    if leaky:
        out.append(AuditExploit(
            "id_encodes_label", "P1",
            f"{len(leaky)}/{len(tasks)} task ids encode the defect class in their suffix",
            "guard: the reviewer prompt must NEVER include the task id (verified by id_not_in_prompt)"))
    # (b) does the id actually reach the reviewer prompt? (the real leak)
    reached = [t.id for t in tasks if t.id in build_prompt(t)]
    if reached:
        out.append(AuditExploit(
            "id_in_prompt", "P0",
            f"{len(reached)} task ids appear in the reviewer prompt — direct answer leak",
            "regression fixture: assert task.id not in build_prompt(task) for every task"))
    return out


def _phrase_for_kind(kind: str) -> str | None:
    # the distinctive fixed phrase the generator injects per reviewer-only class
    return {
        "wrong_measure_label": "continuous",
        "method_mismatch": "Copas",
        "comparator_swap": "control group received the active treatment",
        "missing_reference": "borrows strength",
        "subgroup_mismatch": "subgroup restricted",
    }.get(kind)


def _probe_keyword_shortcut(tasks, keys) -> list[AuditExploit]:
    out: list[AuditExploit] = []
    clean_texts = [t.artifact.lower() for t in tasks if t.kind == CLEAN]
    for kind in sorted(REVIEWER_ONLY_KINDS):
        phrase = _phrase_for_kind(kind)
        if not phrase:
            continue
        p = phrase.lower()
        defect_texts = [t.artifact.lower() for t in tasks if t.kind == kind]
        if not defect_texts:
            continue
        in_all_defects = all(p in txt for txt in defect_texts)
        in_no_clean = all(p not in txt for txt in clean_texts)
        if in_all_defects and in_no_clean:
            out.append(AuditExploit(
                f"keyword_shortcut:{kind}", "P2",
                f"the phrase {phrase!r} perfectly separates '{kind}' defects from clean tasks — "
                f"a model could pattern-match wording, not substance",
                f"negative-memory fixture: paraphrase/vary the '{kind}' narrative so no single phrase "
                f"is a perfect separator"))
    return out


def _probe_template_uniformity(tasks, keys) -> list[AuditExploit]:
    out: list[AuditExploit] = []
    for kind in sorted(REVIEWER_ONLY_KINDS):
        texts = [t.artifact for t in tasks if t.kind == kind]
        if len(texts) < 3:
            continue
        # crude uniformity: the modal "Note/Analysis/Outcome" extra line shared across the class
        extras = [next((ln for ln in txt.splitlines()
                        if ln.startswith(("Note:", "Analysis label:", "Outcome:", "Method:"))), "")
                  for txt in texts]
        nonempty = [e for e in extras if e]
        if nonempty and len(set(re.sub(r"\s+", " ", e) for e in nonempty)) == 1:
            out.append(AuditExploit(
                f"template_uniformity:{kind}", "P2",
                f"all '{kind}' reviewer-only tasks share one identical extra line",
                f"negative-memory fixture: template-vary '{kind}' across fixtures"))
    return out


def _probe_canary(tasks, keys) -> list[AuditExploit]:
    has_witness_defect = any(keys.get(t.id) and keys[t.id].has_defect
                             and t.kind in {"impossible_cell", "reproduction", "ci_invalid"}
                             for t in tasks)
    if not has_witness_defect:
        return [AuditExploit("no_canary", "P0",
                             "no witness-detectable planted defect — a found-nothing pass can't be caught",
                             "add impossible_cell / reproduction canary tasks")]
    return []


def audit_corpus(tasks, keys) -> AuditReport:
    """Run all adversarial probes over the corpus. Returns discovered exploits."""
    exploits: list[AuditExploit] = []
    for probe in (_probe_id_leak, _probe_keyword_shortcut, _probe_template_uniformity, _probe_canary):
        exploits.extend(probe(tasks, keys))
    return AuditReport(exploits=exploits, n_tasks=len(tasks))


def exploits_to_fixtures(report: AuditReport) -> list[dict]:
    """Turn discovered exploits into negative-memory regression fixtures (grows D6)."""
    return [{"type": "negative_memory", "exploit": e.name, "severity": e.severity,
             "guard": e.fixture_hint or e.detail} for e in report.exploits]
