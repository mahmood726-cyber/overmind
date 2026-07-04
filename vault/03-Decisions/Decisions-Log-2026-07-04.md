# Decisions Log — 2026-07-04

Key decisions recorded today. **Truth-first provenance tags:**
- ✅ **VERIFIED** — confirmed from files/reports on disk (path cited).
- ⚠ **SESSION-REPORTED** — stated in the session brief but **not verifiable from any file found on disk**
  (a disk search for the relevant terms returned nothing). Recorded as reported; **do not treat as
  confirmed** until a source is located.

---

## Fleet / verification decisions (VERIFIED)

### ✅ Codex fleet re-authenticated mid-session — cross-vendor witnessing restored
Both Codex seats began the session `401 / refresh-token revoked`; Mahmood re-logged in interactively on
pc1 mid-session, after which both seats ran real `codex exec` completions and delivered genuine
second-vendor confirmations. **Decision:** interactive `codex login` on pc1 is the accepted unblock path;
headless re-auth is not possible. Recipe: [[Codex-agy-Auth-Recipe-SOP]].
*Source:* `F:\ubcma\verification\2026-07-04-{codex-two-seat,codex-postreauth}.md`.

### ✅ agy adopted as a standing THIRD vendor
`agy v1.0.16` was run as an independent third vendor and produced a genuine third perspective (corroborated
Codex, went deeper on Copas, found 2 new comparator defects). **Decision:** keep agy in the cross-vendor
lane alongside Claude + Codex. *Source:* `F:\ubcma\verification\2026-07-04-agy-thirdvendor.md`.

### ✅ Truth-first fix discipline held — no headline moved
The two P0 fixes were applied with full re-derivation; both were numerically inert on the shipped headlines
(k-fold Δ −2.4e-5; Copas moved a comparator column only). **Decision:** ship the fixes as latent-correctness
improvements; **no manuscript headline edited**. One contested finding (wave-1 P0s refuted by Codex WAVE-2)
is left **open for a tie-break**, not force-resolved. *Source:* `2026-07-04-p0p1-fixes.md`. See
[[P0-P1-Bug-Fixes]].

### ✅ Vault / three-layer memory model adopted (this artifact)
Adopt an Obsidian-compatible markdown **vault** as the human-readable memory layer, mirrored by MemClaw
(machine layer) and compiled by Wiki-Ingest. **Decision:** seed it now as a knowledge artifact (outside the
ship path). *Source:* `F:\overmind\workflow-upgrade\2026-07-04-implementation-checklist.md` §4.6. See
[[README]].

---

## Clinic decisions (⚠ SESSION-REPORTED — not found on disk)

> A disk search across `F:\` for `palpitation`, and for clinic/booking/ECG-watch notes dated today,
> returned **no matching source file**. The four items below are recorded **as reported in the session
> brief**. They are plausible and may live outside the searched roots (a different drive, an app DB, or an
> external system), but **they are not corroborated by any artifact I could read.** Locate and link a
> source before promoting any of these to VERIFIED.

- ⚠ **Clinic pivot to palpitations.** Reported: the clinic's focus pivoted to palpitations. *No source file
  found.*
- ⚠ **Email-only booking + a live fix.** Reported: booking moved to email-only, with a live fix applied
  today. *No source file / commit found on disk.*
- ⚠ **ECG watch retired.** Reported: the ECG watch offering was retired. *No source file found.*
- ⚠ **Fleet auth state** (clinic-adjacent framing) — the *verification* fleet-auth state **is** verified
  above; if "fleet auth" here refers to a clinic system specifically, that clinic-specific state is **not
  found on disk.**

*If these belong to a clinic repo/app elsewhere, add it to the searched roots and re-run the audit, then
move each item up to the VERIFIED section with its path.*

## Ties to
[[Codex-agy-Auth-Recipe-SOP]] · [[_Verification-MOC]] · [[Home]].
