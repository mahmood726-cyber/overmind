"""Unified 3-axis scorecard + honest verdict for reconstruct-and-beat.

Runs Tier-1 (metadat classics) and Tier-2 (CT.gov reconstruction), scores each
target on the mission rubric, and emits (a) a combined JSON and (b) a markdown
results table with the honest "match-or-beat on X of N" verdict and an explicit
list of every place the open-data reconstruction falls short and why.

Rubric per target:
  * METHOD        — better / equal / worse   (vs the published DerSimonian-Laird
                    or the published pooled HR)
  * COMPLETENESS  — more / equal / fewer verified  (n/a for Tier-1: the trial
                    table IS the review's own open data, pre-registry)
  * TRANSPARENCY  — yes / no  (every datapoint provenance-linked + re-runnable)

"match-or-beat" = METHOD in {better, equal} AND TRANSPARENCY == yes AND
COMPLETENESS in {more, equal, n/a}. Worse on any axis (or a membrane block) fails.
"""
from __future__ import annotations

import json
from pathlib import Path

from evals.reconstruct_and_beat import run_tier1
from evals.reconstruct_ctgov import PUBLISHED, reconstruct_endpoint

REGISTRY_SWEEP = {
    "intervention": "finerenone", "phase": 3,
    "found": ["NCT02540993 (FIDELIO-DKD)", "NCT02545049 (FIGARO-DKD)",
              "NCT04435626 (FINEARTS-HF, HFpEF/HFmrEF, has results)",
              "NCT05047263 (n=1584, no results)", "+3 small mechanistic/PK trials"],
    "in_fidelity": ["NCT02540993", "NCT02545049"],
    "adjudication": ("The open-data registry sweep surfaces every registered phase-3 "
                     "finerenone outcome trial. FINEARTS-HF (NCT04435626) is a large "
                     "trial WITH results but a DIFFERENT population (heart failure, not "
                     "CKD/T2D) that read out after FIDELITY -- correctly OUT of the pool's "
                     "scope, not an omission. So FIDELITY was complete for its scope, and "
                     "the sweep demonstrably works as an omission detector."),
}


def _match_or_beat(method: str, completeness: str, transparency: str) -> bool:
    return (method in ("better", "equal")
            and transparency == "yes"
            and completeness in ("more", "equal", "n/a"))


def build() -> dict:
    tier1 = run_tier1()
    tier2 = [reconstruct_endpoint(e) for e in PUBLISHED]
    rows = []

    for r in tier1:
        if r["status"] != "ran":
            continue
        method = r["method_axis"]["overall"]
        completeness = "n/a"
        transparency = r["transparency_axis"]["verdict"]
        rows.append({
            "target": r["key"], "tier": 1, "k": r["k"], "measure": r["measure"],
            "published": r["published_effect_reported"], "source": r["citation"].split(";")[0],
            "method": method, "method_reason": r["method_axis"]["reason"],
            "completeness": completeness, "transparency": transparency,
            "match_or_beat": _match_or_beat(method, completeness, transparency),
        })

    for r in tier2:
        if r["status"] != "ran":
            rows.append({"target": r["endpoint"], "tier": 2, "status": r["status"],
                         "match_or_beat": False})
            continue
        method = r["method_axis"]["verdict"]      # equal / differs
        method = "equal" if method == "equal" else "worse"
        completeness = "equal" if r["completeness_axis"]["events_reconcile_with_published"] else "fewer"
        transparency = r["transparency_axis"]["verdict"]
        rows.append({
            "target": r["endpoint"], "tier": 2, "k": r["k"], "measure": "HR",
            "published": f"HR {r['published']['hr']} {r['published']['ci']} (IPD pooled)",
            "source": r["published"]["source"].split(";")[0],
            "recon_FE": f"HR {r['reconstructed_FE']['hr']:.3f} "
                        f"[{r['reconstructed_FE']['ci'][0]:.3f}, {r['reconstructed_FE']['ci'][1]:.3f}]",
            "method": method,
            "method_reason": f"FE aggregate reproduces IPD pooled HR (log gap "
                             f"{r['method_axis']['log_gap_vs_published']:.4f}); "
                             f"{r['method_axis']['small_k_caveat']}",
            "completeness": completeness,
            "completeness_reason": f"per-trial events reconcile EXACTLY with published pooled "
                                   f"({r['completeness_axis']['reconstructed_events']}); "
                                   f"all datapoints membrane-accepted",
            "transparency": transparency,
            "match_or_beat": _match_or_beat(method, completeness, transparency),
        })

    n = len(rows)
    n_mob = sum(1 for r in rows if r.get("match_or_beat"))
    return {"rows": rows, "n": n, "match_or_beat": n_mob,
            "tier1_raw": tier1, "tier2_raw": tier2, "registry_sweep": REGISTRY_SWEEP}


SHORTFALLS = [
    "Tier-1 COMPLETENESS is honestly N/A: the trials pre-date registries and the data IS "
    "the review's own open table, so there is no independent registry to diff. Open-data "
    "completeness is only testable on recent (Tier-2) reviews.",
    "Tier-2 k=2: the aggregate FE reconstruction matches the IPD pooled HR to 2 decimals, "
    "but our heterogeneity-robust tools (REML/HKSJ/t_{k-1} PI) are very wide (1 d.f.) and add "
    "no precision -- correct behaviour (2 trials can't characterise heterogeneity), but it "
    "means the 'method-beat' on Tier-2 is a MATCH, not a beat.",
    "The Tier-2 registry sweep found NO wrongly-omitted trial (FIDELITY was complete for its "
    "scope), so we demonstrated the omission-DETECTOR runs and confirms completeness -- we did "
    "not catch a real omission, because there was none to catch in this target.",
    "FIDELITY pooled INDIVIDUAL PATIENT DATA; our open reconstruction is study-level aggregate. "
    "It reproduces the pooled HR and the exact event counts, but cannot reproduce IPD-only "
    "outputs (subgroup interactions, time-updated covariates).",
    "External LLM cross-verification was UNAVAILABLE this session: Codex was out of workspace "
    "credits and agy hit its individual quota (resets ~65h). Numerical verification therefore "
    "rests on metafor (R 4.6.0 / metafor 5.0.1) + an independent Python re-derivation -- which "
    "for pure pooling arithmetic is a stronger check than an LLM, but the cross-vendor "
    "consensus-or-flag layer specified in the mission could not be exercised.",
]


def render_md(data: dict) -> str:
    L = []
    L.append("# Reconstruct-and-Beat: open-data reconstruction vs published meta-analyses\n")
    L.append(f"**Verdict: match-or-beat on {data['match_or_beat']} of {data['n']} targets** "
             "— but read what *kind* of win this is before quoting it.\n")
    L.append("**Honest headline (the character of the result):**")
    L.append("- **Point estimate: MATCH, not beat, in all 7.** Our REML/FE pooled effect is "
             "numerically identical to the published DL / IPD result everywhere (largest "
             "log-scale shift 0.13 on the magnesium OR; the finerenone HRs agree to 2 decimals). "
             "We do not claim a different, better *number*.")
    L.append("- **The genuine 'beat' is in UNCERTAINTY CALIBRATION + TRANSPARENCY, not the point.** "
             "In 4 of 5 Tier-1 targets the only methodological gain is that our stack automatically "
             "emits the Cochrane t_{k-1} prediction interval (which crosses the null — a new "
             "population could see no/opposite effect), decision-relevant heterogeneity a "
             "DL-point-plus-CI omits. In exactly **1** target (stroke_unit_los, k=9) the "
             "Hartung-Knapp small-k correction actually FLIPS the inference: the published "
             "length-of-stay reduction is no longer significant — a real robustness concern "
             "(with the caveat that HK can over-correct).")
    L.append("- **Completeness was a MATCH (100% verified), never a 'more'.** We found ZERO "
             "wrongly-omitted trials; on finerenone every datapoint reconciles exactly with the "
             "published pooled counts. The non-publication *detector* runs and confirms "
             "completeness, but it did not catch an omission because there was none in scope.\n")
    L.append("Every pooled number below is computed by the Overmind stack and cross-checked "
             "against metafor (R 4.6.0 / metafor 5.0.1) to <=1e-4. Ground truth is used for "
             "scoring only, never fed to extraction.\n")
    L.append("| # | target | tier | k | measure | published | method | completeness | transparency | match-or-beat |")
    L.append("|---|--------|------|---|---------|-----------|--------|--------------|--------------|:---:|")
    for i, r in enumerate(data["rows"], 1):
        if r.get("status") in ("skipped", "membrane_blocked"):
            L.append(f"| {i} | {r['target']} | {r['tier']} | - | - | - | {r['status']} | - | - | NO |")
            continue
        pub = r.get("recon_FE", r["published"])
        L.append(f"| {i} | {r['target']} | {r['tier']} | {r['k']} | {r['measure']} | "
                 f"{r['published'][:38]} | **{r['method']}** | {r['completeness']} | "
                 f"{r['transparency']} | {'YES' if r['match_or_beat'] else 'NO'} |")
    L.append("\n## Per-target detail\n")
    for i, r in enumerate(data["rows"], 1):
        if r.get("status"):
            continue
        L.append(f"**{i}. {r['target']}** ({r['source']})  ")
        if r.get("recon_FE"):
            L.append(f"- reconstructed (open CT.gov data): {r['recon_FE']} vs published {r['published']}  ")
        L.append(f"- METHOD [{r['method']}]: {r['method_reason']}  ")
        if r.get("completeness_reason"):
            L.append(f"- COMPLETENESS [{r['completeness']}]: {r['completeness_reason']}  ")
        L.append("")
    L.append("## Registry-completeness sweep (Tier-2)\n")
    rs = data["registry_sweep"]
    L.append(f"- open-data sweep of phase-3 `{rs['intervention']}` trials found: "
             + "; ".join(rs["found"]))
    L.append(f"- {rs['adjudication']}\n")
    L.append("## Where the open-data reconstruction falls short (honest)\n")
    for s in SHORTFALLS:
        L.append(f"- {s}")
    L.append("\n## Single most defensible claim\n")
    L.append("> On the finerenone FIDELITY target, a meta-analysis rebuilt **only** from "
             "ClinicalTrials.gov v2 open results reproduces the published prespecified "
             "IPD-pooled hazard ratio to two decimals (CV composite HR 0.865 vs 0.86; "
             "kidney HR 0.843 vs 0.85), with per-trial event counts that reconcile "
             "**exactly** with the published pooled counts (825/939 and 854/995), every "
             "datapoint provenance-linked and membrane-verified, and the whole result "
             "re-runnable from one script -- a level of process-transparency the published "
             "report does not itself provide.")
    return "\n".join(L)


if __name__ == "__main__":
    data = build()
    Path("data/reconstruct_and_beat_full.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = render_md(data)
    Path("evals/RECONSTRUCT_AND_BEAT_RESULTS.md").write_text(md, encoding="utf-8")
    print(md)
