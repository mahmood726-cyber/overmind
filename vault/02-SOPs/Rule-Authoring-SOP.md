# SOP — Rule / Skill Authoring (make guidance stick under pressure)

> **Version:** v1.0 · **Status:** active convention · **Owner:** whoever edits `rules/`, `lessons.md`, Sentinel rules, or vault SOPs
> **Change log:** v1.0 — codified 2026-07-05 by lifting obra/superpowers `writing-skills`
> (persuasion-principles + TDD-for-docs) — MIT, © 2025 Jesse Vincent / Prime Radiant — and
> adapting to our own guidance layer. Rationale in `C:\Projects\superpowers-trial-2026-07-05.md`.

## Purpose
Guidance is code that shapes agent behavior. A rule that reads well but gets rationalized away
under pressure is a **defect**, not documentation. This SOP is how to author `lessons.md` entries,
`rules/*.md` discipline, Sentinel rule messages, and vault SOPs so agents actually comply when a
competing incentive (time, sunk cost, "just this once") is pushing the other way.

## The rule
1. **Baseline the failure before writing the guidance (TDD-for-docs).** If you didn't watch an
   agent fail *without* the rule, you don't know the rule teaches the right thing. Reproduce the
   wrong behavior first (a real session, or a fresh-context micro-test), capture the exact
   rationalizations verbatim, then write guidance that closes *those specific* loopholes. No new
   rule for a failure you haven't actually observed.
2. **Match the form to the failure — the form that fixes one type backfires on another:**
   - *Skips/violates a known rule under pressure* → prohibition + rationalization table + red-flags
     list (authority framing; see #3). This is the ONLY case prohibitions belong.
   - *Complies but output has the wrong shape* (bloated, buried verdict, restated spec) → a
     **positive recipe/contract** stating what the output IS, in order. Prohibitions ("don't
     restate") measurably backfire here — under a competing incentive the agent negotiates with
     "don't X"; a recipe leaves nothing to negotiate.
   - *Omits a required element* → make it a **structural REQUIRED slot** in the template they fill,
     not a prose reminder near it.
   - *Behavior should depend on a condition* → a conditional keyed to an **observable predicate**
     ("if the baseline file exists, …"), not an unconditional rule with exemption clauses.
3. **For discipline rules, use the persuasion levers that raise compliance; avoid the ones that
   corrode it.** (Meincke et al. 2025, N≈28k: persuasion techniques moved compliance 33%→72%.)
   - **Authority** — imperative, bright-line, no-exceptions language ("YOU MUST", "Never", "Delete
     it. Start over.") removes decision fatigue and "is this an exception?" negotiation.
   - **Commitment** — require an explicit announcement/choice, track with todos.
   - **Scarcity** — bind to a moment ("BEFORE proceeding", "IMMEDIATELY after") to kill "I'll do
     it later".
   - **Social proof** — universal-failure framing ("checklists without todos = steps skipped,
     every time").
   - **Unity** — collaborative "our codebase / we both want quality" for judgment/feedback rules.
   - **Avoid Liking and Reciprocity for compliance** — they breed sycophancy and conflict with
     honest-feedback culture. Reference-only material uses clarity, no persuasion.
4. **Close every loophole explicitly and state spirit-over-letter.** Don't just state the rule —
   forbid the specific dodges ("don't keep it as reference / don't adapt it / delete means delete")
   and add the foundational line **"violating the letter is violating the spirit"** to cut off the
   whole "I'm following the spirit" class. Build the rationalization table from real baseline
   excuses; every excuse an agent made goes in it.
5. **Micro-test the wording before shipping (5+ reps, with a no-guidance control).** One
   fresh-context sample per rep; system prompt = the realistic context the rule will live in; user
   task = one that tempts the failure. **Always include a no-guidance control** — if the control
   doesn't fail, there's nothing to fix, don't write the rule. Read every flagged match by hand
   (template echoes masquerade as hits). **Variance is a metric**: five different interpretations
   across five reps means the wording isn't binding — tighten the form before adding words. No
   nuance clauses ("don't X unless it matters") — they reopen the negotiation.

## Why (past incidents)
Our worst silent-corruption bugs (465 reviews, 45+ project registry drift, placeholder leaks to
1000+ dashboards) each had a rule that *existed* but wasn't binding enough to fire under pressure.
This SOP is the authoring counter-discipline: it is why `lessons.md` entries carry the "learned"
date + concrete failure, why Sentinel BLOCK messages name the past incident, and why we prefer a
structural gate over a prose "please remember". A rule agents route around is worse than no rule —
it creates false confidence.

## Objective gate
The rule targets a failure you actually reproduced; its form matches the failure type (recipe for
shaping, prohibition only for discipline); loopholes are closed explicitly; and the wording beat a
no-guidance control across ≥5 reps with convergent (low-variance) output.

## Stop conditions
- **Success:** baseline failure captured → guidance written in the matched form → micro-test beats
  control with low variance → committed (single-writer, no force-push) with the provenance line.
- **Failure:** control doesn't exhibit the failure (nothing to fix — don't author) OR reps stay
  high-variance after two wording passes (the form is wrong, not the words — restructure) → log
  and stop; do not ship an unverified behavior-shaping rule.

## Ties to
[[Single-Writer-Rule-SOP]] (commit discipline for these edits) · [[Gated-Additive-Deploy-SOP]]
(ship additively) · [[_SOPs-MOC]] · `C:\Users\mahmo\.claude\rules\debugging.md` &
`lessons.md` "Debugging discipline" (sibling artifacts lifted in the same 2026-07-05 pass).
