# SOPs / Reusable Workflows — MOC

Distilled, **versioned** standard operating procedures from today's loop/harness patterns. Each note
carries a version header (`v1.0`, dated) so we can audit what worked and evolve it (vault workflow #2:
SOPs under git; [[src-sanyuan-skills|Skill Forge/Review]] to author + audit). These are the reusable
substrate under the one-off [[_Verification-MOC|verification]] work.

## SOPs
- [[Cross-Vendor-Witness-SOP]] — how to obtain a genuine independent second/third-vendor witness (the
  method behind today's triple-vendor result).
- [[RapidMeta-QA-SOP]] — deterministic-sample re-pool + display-defect audit for the dashboards.
- [[Gated-Additive-Deploy-SOP]] — flag-gated, shadow→measured-zero-regression→enforce rollout with a
  one-flag rollback (the governing rollout principle).
- [[Single-Writer-Rule-SOP]] — one writer per artifact; truth-first re-derivation of every affected number.
- [[Codex-agy-Auth-Recipe-SOP]] — the concrete fleet auth recipe (CODEX_HOME per seat,
  `--skip-git-repo-check` / sandbox flags, `node2_ed25519` SSH).

## Provenance
Sourced from `F:\overmind\workflow-upgrade\2026-07-04-{cutting-edge-improvements,implementation-checklist}.md`
and today's verification reports. Grounded in [[src-loop-engineering-cherny]] (build-order discipline) and
[[src-lfd]] (loss design).
