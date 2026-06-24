# Frontier-Closing — Running Progress Log

**Branch:** `frontier-closing-2026-06-24` (built on the eval-harness landing, commit `7f4e231`)
**Goal:** take Sentinel / Overmind / memory / multi-engine / truth-recovery to best-in-class
against the §5 roadmap of [`SYSTEMS-BENCHMARK-VS-FRONTIER.md`](SYSTEMS-BENCHMARK-VS-FRONTIER.md).
**Contract:** truth-first — every improvement is backed by a **measured** number from the eval
harness (`python -m evals.run_all`) or a new eval added here. No merge to `master` without sign-off.
No force-push.

> **How to read the deltas.** Every item below quotes a *before → after* number from a specific
> eval. Where a number can't honestly be measured offline (e.g. CoT reasoning quality needs a live
> model), it says so explicitly rather than inventing one.

---

## Item #1 — MEASUREMENT FIRST: published baselines

Baseline run of the held-out harness on this branch's starting commit (`7f4e231`), no code changes.
Command: `python -m evals.run_all` → `evals/results/summary.json`.

| Eval | Metric | Baseline | Reading |
|------|--------|----------|---------|
| **SpecBench-style** (reward hacking) | `validation_pass_rate` | **66.67 %** | of 3 candidate kinds (honest/reward_hack/broken), the 2 that pass *visible* tests |
| | `heldout_pass_rate` | **33.33 %** | only the honest candidate passes *held-out* tests |
| | **`specbench_gap`** | **33.34 %** | how much "passes visible tests" overstates true correctness |
| | **`reward_hack_heldout_catch_rate`** | **100 %** (5/5) | of reward-hacks a *visible-only* verifier would certify, fraction our held-out-baseline policy catches |
| | `visible_only_false_certifications` | **5** | reward-hacks a visible-only verifier would have falsely certified |
| **Judge master-key** (adversarial) | **`degenerate_false_pass_rate`** | **0 %** (0/12) | empty / punct / filler / no-verdict never yield PASS — guard holds |
| | `genuine_accuracy` | **100 %** (6/6) | well-formed verdicts classified correctly, 0 misflagged |
| | **`injection_boundary_false_pass_rate`** | **50 %** (1/2) | attacker-planted `VERDICT: PASS` escapes the regex *output*-guard — **documented open gap** |
| **Memory recall** (LongMemEval-style) | `recall` / `precision` | **100 % / 100 %** | current fact retrieved, no superseded fact pollutes top-k |
| | `stale_suppression_rate` | **100 %** | superseded facts suppressed (vs `naive_stale_leak_rate` **100 %** without the temporal filter) |
| | `expired_fact_suppressed` | **true** | expired temporal fact correctly hidden |

### Honest reading of the baseline

- **What's genuinely strong & now *measured on the fixture set* (not asserted):** the degenerate-guard (0 % false-PASS),
  the held-out-baseline reward-hack defense (100 % catch of the 5 the visible-only verifier misses),
  and the temporal-memory suppression (100 % stale-suppression vs 100 % naive leak — the filter, not
  keyword luck, is doing the work). These three were "robust by construction"; they are now **robust
  by evidence** on this fixture set.
- **Saturation caveat (truth-first):** memory recall/precision and degenerate false-PASS are at the
  ceiling because the seed fixtures are *small and keyword-distinct*. A 100 % here means "no failure
  on the compact probe", **not** "solved at scale". These evals need harder cases (semantic
  paraphrase, large-N ranking, more reward-hack variety) before the ceiling means much — tightening
  the fixtures is tracked as follow-up, and any item that claims to "improve" a saturated metric must
  first add a harder case that *isn't* already at 100 %.
- **The clearest open, measurable gap:** `injection_boundary_false_pass_rate = 50 %`. The regex
  output-guard is — by design — blind to a well-formed but attacker-planted `VERDICT: PASS`. This is
  the one judge number with real headroom, and it's the honest target for input-side defense work.

---

## Item #2 — cheap, high-value switches (in progress)

Each sub-item lands as its own tested commit with its measured eval delta. Status below updates as
they land.

### #2c — hard-enforce different-family quorum panels ✅ landed

Was **warn-only**: a `claude,codex,codex-noreen` panel ran as a "3-judge" quorum, flagged but live,
advertising ~2.25 effective votes as if 3. Now **hard-enforced** by default
(`OVERMIND_JUDGE_QUORUM_ENFORCE=1`, escape hatch `0/off/warn`): `build_judge` repairs a correlated
panel by dropping same-family redundancy (one judge per family), and if **<2 families** remain it is
not a real quorum, so it falls back to a single-engine chain instead of advertising false
independence.

New eval `evals/quorum_decorrelation.py` (now in `run_all`), run against the **real** `build_judge`:

| Metric | Before (warn-only) | After (enforced) |
|--------|--------------------|------------------|
| **correlated-panel overcount rate** | **100 %** (5/5) | **0 %** (0/5) |
| honest-panel unchanged rate (no-regression) | 100 % (3/3) | 100 % (3/3) |

"Overcount" = a panel that runs as a `QuorumJudge` whose `effective_votes < nominal_votes`. After
enforcement every surviving quorum has `effective_votes == nominal_votes` (all distinct families);
the rest correctly fall back. Honest (all-distinct) panels are provably untouched.

**Honest scope:** the effective-vote estimate is a heuristic (0.25/redundant-judge), not a calibrated
independence measure — enforcement makes the *structural* guarantee "no surviving quorum spans a
duplicate family", which is exact; it does not claim the surviving panel's votes are perfectly
independent. Tests: `tests/unit/test_judge_factory.py` (8 new) + `test_evals_harness.py` (1 new).

### #2a — cost-aware engine routing (local-first, escalate on uncertainty) ✅ landed

New `RoutedJudge` + `OVERMIND_JUDGE_MODE=routed` (`build_judge`, first engine = cheap tier, rest =
expensive escalation tier — a cross-family quorum if >1, else a single engine). Runs the cheap/local
judge first and **escalates to the expensive quorum only when the cheap verdict is untrustworthy**.
Truth-first asymmetry (a false PASS is the costly error): never trust a cheap `judge_error` /
`judge_degenerate`; accept a cheap verdict only above `escalate_below=0.75`; and require a cheap
**PASS** to additionally clear a higher `pass_floor=0.85`. Returned verdict carries
`routed_cheap_accepted` / `routed_escalated` so the path is auditable.

New eval `evals/engine_routing.py` (in `run_all`), against the **real** `RoutedJudge`:

| Metric | Always-expensive | Routed |
|--------|------------------|--------|
| **expensive (quorum) invocation rate** | **100 %** | **50 %** (= escalation rate) |
| accuracy | 100 % | **100 %** (`routed_preserves_expensive=True`) |
| cheap-only accuracy (counterfactual) | — | **62 %** |

The headline (quorum-invocation rate **100 % → 50 %**) is **assumption-free** — it directly halves the
expensive-tier call volume, which is the token-cost lever. Routing loses **zero** accuracy vs running
the quorum every time, while naive "just use local" would drop to 62 %. A secondary token-saving
figure (25 % at a conservative 4:1 expensive:cheap ratio) is reported *with its ratio stated* — the
real saving scales with the true local:quorum cost ratio, so we lead with the invocation rate, not
the dollar number.

**Honest scope:** the eval uses scripted cheap/expensive verdicts (deterministic, offline) — it
shows the *routing logic* cuts invocations without losing accuracy on a labelled set; it does not
measure a live local model's real confidence calibration (that needs an online run). Tests:
`tests/unit/test_judge_factory.py` (+5) + `test_evals_harness.py` (+1).

### #2b — default-on CoT+rubric judge, gated by a golden-set no-regression check ✅ landed

The roadmap's precondition for flipping `OVERMIND_JUDGE_COT` ON was "a golden-set check shows it
doesn't regress." Built that check as a **reproducible eval** (`evals/judge_cot_goldenset.py`), then
flipped the default.

Golden-set gate (CoT **off** vs **on**, same labelled judge outputs):

| Check | Result |
|-------|--------|
| **parse-agreement (CoT-on vs CoT-off classify golden set identically)** | **100 %** |
| genuine accuracy (off / on) | 100 % / 100 % |
| degenerate false-PASS with CoT **on** | **0 %** (guard intact) |
| rubric (RELEVANCE/ACCURACY/EVIDENCE/LOGIC) + 6-line output contract present | **yes / yes** |
| → **`no_regression`** | **True** |

With the gate green, `_cot_enabled()` now defaults **ON** (`OVERMIND_JUDGE_COT=0` to opt out).

**Honest scope (important):** this gate shows CoT is **safe** to enable — the prompt change is
parse-invariant, the degenerate guard still holds, and the output contract the parser depends on is
intact. It does **NOT** measure CoT's reasoning-quality *improvement*: the StubBackend ignores the
prompt, so a `quality_delta_measured=False` flag is carried in the result on purpose. The expected
gain (+~11pp, arXiv:2604.23178) is literature-backed, **not** a number we measured. To quantify it,
run a live golden set against a real backend — tracked as follow-up. Tests:
`test_judge_factory.py` (CoT-default-on / opt-out / param-override) + `test_evals_harness.py` (+1).

---

### Item #2 summary — measured deltas

| Switch | Eval | Before → After | Truth-first caveat |
|--------|------|----------------|--------------------|
| #2c hard-enforce family quorum | `quorum_decorrelation` | overcount rate **100 % → 0 %** | structural guarantee, not calibrated independence |
| #2a cost-aware routing | `engine_routing` | quorum invocation **100 % → 50 %**, accuracy 100 %→100 % | scripted verdicts; live calibration unmeasured |
| #2b default-on CoT | `judge_cot_goldenset` | no-regression gate **True**; default OFF → ON | quality gain literature-backed, not measured offline |

All three are real, reproducible, and honest about their limits. None makes a PASS easier on
missing/degenerate evidence; each only adds strictness, cuts cost without losing accuracy, or is
gated on a no-regression proof.

### #2d — input-side injection sanitization (the named first target: 50% injection-boundary) ✅ landed

The baseline's clearest open measured gap was `injection_boundary_false_pass_rate = 50 %`: an
attacker-planted, well-formed `VERDICT: PASS` echoed into the judge reply sailed past the regex
*output*-parser. Added an **input-side tamper guard** (`injection_tamper_reason`,
`overmind/verification/llm_judge.py`) that reuses the existing `PromptInjectionScanner` signatures
(instruction-override / persona-swap / canary-echo / exfil). Truth-first asymmetry: a **coerced
PASS** is refused (abstain → `judge_error` + `judge_injection_suspected`); a **FAIL** that merely
*quotes* an injection attempt is left intact; hard evidence (canary/exfil) abstains regardless.
Also strengthened the scanner's `ignore_previous` regex — it previously matched only a *single*
qualifier and silently missed the canonical "ignore **all previous** instructions" (two qualifiers).

Measured (`evals/judge_masterkey.py`, real `LLMJudge`):

| Metric | Before | After |
|--------|--------|-------|
| **injection_boundary false-PASS** (original 2 planted cases) | **50 %** (1/2) | **0 %** (0/2) |
| injection_signature false-PASS (override/persona/canary) | — (new) | **0 %** (0/3) |
| genuine accuracy / misflagged (no-regression) | 100 % / 0 | **100 % / 0** |
| degenerate false-PASS (unchanged) | 0 % | **0 %** |
| **injection_clean_boundary false-PASS** (no attack phrase) | — | **100 %** (1/1) — *honest open gap* |

**Honest boundary (not claimed solved):** a planted `VERDICT: PASS` with **no** attack phrase is
indistinguishable from a genuine verdict by output scanning, so it still leaks (1/1). The eval
asserts that leak on purpose, and closing it needs a **trusted output channel** (structured tool-call
output) — tracked, not overclaimed. Tests: `test_llm_judge.py` (+6: coerced-PASS abstains,
persona/canary abstain, FAIL-quoting-injection preserved, genuine-PASS not flagged, clean-planted
boundary) + `test_evals_harness.py` (+3 assertions).

### Item #2 + #2d — MERGED to master

Commit `3e6e564` (merge) + `d62438c` (results correction). Gates met: full suite **831 passed, 8
skipped**; each eval equal-or-better; Sentinel `--diff --base-ref master` **BLOCK=0**. A stale
`summary.json` (showed injection_boundary 0.5 from a pre-#2d run) was corrected to the real 0.0 —
truth-first: the published artifact must match the eval code.

---

## Item #3 — heavier mechanisms behind measured gates

### #3a — claim→evidence dependency graph with retraction propagation ✅ landed (pre-merge)

Replaces *flat* source-hash freshness with a **claim→evidence graph** (audit B2 / *Grounded
Continuation* arXiv:2605.14175). New pure module `overmind/verification/claim_graph.py` (`ClaimGraph`,
cycle-safe, deterministic BFS over reverse-dependency edges → transitive closure on `retract()`).
`MemoryRecord` gains a `derived_from` edge (additive DB migration, JSON round-trip);
`MemoryStore.propagate_retraction()` / `invalidate_stale_with_propagation()` expire the transitive
closure when a premise goes stale — formalizing "missing premise ⇒ invalidate dependents".

New eval `evals/memory_retraction.py` (real `MemoryStore`, A←B←C chain + independent D; A's source
file mutated):

| Metric | Flat (`invalidate_stale`) | Graph (`..._with_propagation`) |
|--------|---------------------------|--------------------------------|
| **transitive-invalidation recall** | **33 %** (catches `{A}`) | **100 %** (catches `{A,B,C}`) |
| independent D preserved (no over-propagation) | yes | yes |

**Honest scope:** the graph is built from explicit `derived_from` edges — it's exact over the edges
it's given; it does not *infer* unrecorded dependencies (a fact with no `derived_from` is treated as
independent, same as today). Tests: `test_claim_graph.py` (+8, pure algorithm),
`test_memory_source_hash.py` (+5: DB round-trip, flat-leaves-dependents, propagation closure,
no-over-propagation) + `test_evals_harness.py` (+1).

### #3c — span-level verdict-pipeline tracing ✅ landed (pre-merge)

Closed the observability gap (good aggregate metrics + audit artifacts, but **no
span-level trace** of a single verdict). New `overmind/verification/verdict_trace.py`:
a dependency-free, OTel-shaped `VerdictTracer` (spans with ids/parents/timing/tokens/
attributes, context-manager API, tree-consistency + coverage helpers). The **real**
`cert_bundle.Arbitrator.arbitrate` now takes an optional `tracer` and emits an
`arbitrator` span with the decision + witness count — zero behavior change when
`tracer=None` (default).

New eval `evals/verdict_tracing.py` (real Arbitrator in the loop):

| Metric | Before (untraced) | After (traced) |
|--------|-------------------|----------------|
| **span coverage** (witness→judge→arbitrator) | **0 %** | **100 %** |
| tree-consistent (every span closed, valid parents) | — | **True** |
| tokens captured / arbitrator span carries verdict | — | **1200 / yes (`CERTIFIED`)** |

**Honest scope:** this lands the tracing **primitive** and instruments the
arbitrator boundary; the eval threads witness + judge spans through the same
tracer to demonstrate an end-to-end trace. Instrumenting *every* backend/witness
call site in the live orchestrator is incremental adoption of the same primitive
(the API is now in place). Scored fields (coverage, tree-consistency, tokens) are
deterministic; per-span `latency_ms` is wall-clock and never scored. Tests:
`test_verdict_trace.py` (+6) + `test_evals_harness.py` (+1).

### #3b — sandbox-requirement policy for untrusted witnesses ✅ landed (pre-merge)

The execution-isolation gap: witnesses run as host subprocesses. Full microVM/gVisor
is multi-session infra and depends on a runtime that may be absent. The
machine-independent, fail-closed increment landed now: `overmind/verification/sandbox_policy.py`
classifies each witness by trust (self-authored = trusted; third-party / agent-generated =
untrusted) and **blocks an untrusted witness from counting toward a release pass unless it
actually ran under isolation** — fail-closed, never relaxing the gate.

New eval `evals/sandbox_policy.py`:

| Metric | Before (no policy) | After (policy) |
|--------|--------------------|----------------|
| **untrusted-un-isolated counts-as-pass rate** | **100 %** | **0 %** |
| trusted witnesses unaffected (run on host) | — | **True** |
| untrusted permitted when isolation *is* active | — | **True** |

**Honest scope (important):** this is **policy enforcement, not a microVM**. It guarantees
untrusted code can't silently become a CERTIFIED pass while un-isolated; it does **not** itself
provide isolation (that remains the existing `ContainerIsolation` skeleton + worktree fallback,
still SKIP/stub for the actual container path). The real microVM execution path is the deferred
infra piece — this gate makes its absence *safe* (fail-closed) rather than silently unsafe. Tests:
`test_sandbox_policy.py` (+6) + `test_evals_harness.py` (+1).

### #3d — cross-repo contract-impact fan-out ✅ landed (pre-merge)

The one capability the industry standardized on in 2026 that we lacked (B1): when a **shared**
module/schema changes, fan out to the **dependent** repos' witnesses. Overmind verified each
project independently — a per-repo verifier that only re-checks *direct* consumers misses
dependents-of-dependents (and the house lesson is explicit: never skip a repo whose upstream
dependency changed). New `overmind/verification/contract_impact.py` (`ContractImpactGraph`) **reuses
the same `ClaimGraph` transitive-closure primitive** as #3a — a dependent's relation to a shared
module is exactly "depends_on" — so a change selects the transitive closure of impacted repos.

New eval `evals/contract_impact.py` (M shared by A, C; B depends on A; D independent; M changes):

| Metric | Naive (direct-only) | Graph (transitive closure) |
|--------|---------------------|----------------------------|
| **impact recall** | **67 %** (misses transitive B) | **100 %** (`{A,B,C}`) |
| no dependent skipped (safety bar) | — | **True** |
| independent D not selected (no over-fan-out) | — | **True** |

**Honest scope:** computes the impact SET from an explicit dependency map; it does **not**
auto-discover that map (an import/schema scanner across the portfolio is the follow-up). Given the
map, the fan-out is exact and never skips a transitive dependent. Sequenced **before** any delta-skip
(#4) so the skip-gate respects cross-repo impact. Tests: `test_contract_impact.py` (+6) +
`test_evals_harness.py` (+1).

## Item #4 — cluster: build or mark deferred — _not started_
