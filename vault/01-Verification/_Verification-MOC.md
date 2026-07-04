# Verification — MOC (cross-vendor QA, 2026-07-04)

Summaries of today's cross-vendor QA reports on the **ubcma** methods repo (branch `methods-borrowing`)
and the **RapidMeta** dashboards. Each note links to its source report under
`F:\ubcma\verification\2026-07-04-*.md`.

**The headline:** the transport-NMA result is now witnessed by **three independent vendors** (Claude +
OpenAI Codex + Antigravity `agy`) to full double precision — **no shipped number moved.** Two P0 code
defects were fixed truth-first (both numerically inert on this corpus but real latent bugs); RapidMeta
re-pooling found the math is sound (27/28 exact) but a **systematic measure-LABEL defect** is broad.

## Notes
- [[Triple-Vendor-Transport-NMA-Witness]] — Claude = Codex = agy, exact to full precision; incl. the one
  HC one-cell nuance all three converged on.
- [[P0-P1-Bug-Fixes]] — the frozen-transform k-fold fix + Copas selection fix; what moved (a comparator
  column) and what did not (the headlines).
- [[RapidMeta-Repool-Findings]] — 27/28 numbers agree; the MD→"RR" mislabel defect, MALARIA/CTEPH blank
  renders, degenerate-CI defect.
- [[agy-New-Comparator-Defects]] — agy's 2 genuinely new confirmed comparator defects Codex missed, plus
  the deeper Copas-objective concern.

## Cross-vendor status at a glance
| Claim / artifact | Claude | Codex (gpt-5.5) | agy (v1.0.16) | Moved? |
|---|---|---|---|---|
| transport-NMA κ_pooled = 0.1575949114447188 | ✓ | ✓ (0.1576, 4dp) | ✓ (exact) | No |
| corr(κ_MD, 1−λ) = +0.5014226365552311 | ✓ | ✓ (+0.5014) | ✓ (exact) | No |
| ext-κ 0.158 beats PET/TF/HC @ B≥0.15 | ✓ | ✓ (PARTIAL phrase) | ✓ | No |
| P0 #2 k-fold "beats within-MA" MAE headline | fixed, CONFIRMED | refuted then reconciled | fix corroborated | No (−2.4e-5) |
| P0 #1 Copas comparator | fixed | flagged | deeper concern | comparator only |

> **Truth-first note (contested finding, unresolved):** in WAVE-2 Codex **refuted** both wave-1 Claude P0s
> (Copas, k-fold) on the current tree, contradicting the wave-1 bug-hunt — a **tie-break is still needed**;
> agy later corroborated the k-fold *fix* is present and sound. See [[P0-P1-Bug-Fixes]] and
> [[agy-New-Comparator-Defects]]. The κ NCT-duplication concern is *construction-validity*, not a
> reproducibility failure (both vendors recompute from the same CSV).
