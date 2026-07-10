# Peer Benchmark 2026-07-10 — Our Harness vs. Comparable Systems (purpose-anchored)

**Date:** 2026-07-10 · **report-only, no code changes, frozen repos untouched.**
Companion to [`SYSTEMS-BENCHMARK-2026-07-10.md`](SYSTEMS-BENCHMARK-2026-07-10.md).

**The purpose everything is judged against (do not drift):** *a truth-gated, heterogeneous-vendor
**reproduction-and-verification** orchestrator for quantitative **evidence-synthesis** — reproduce a pooled
estimate from open data, cross-check it across independent vendors, and **flag/abstain** rather than emit a
wrong "pass."* Peers are scored **only** on dimensions that bear on that job; generic agent-framework features
(handoffs, streaming, tool ergonomics) are out of scope.

**Grounding (verified this pass):** `master` HEAD `a650361` ("enforce fail-closed consensus in the live judge
decision", confirmed on `origin/master`); **1277 test functions** (`grep -rho "def test_"` = 1277, exact match);
deterministic consensus core = `overmind/review/consensus.py` + `cluster-harness/harness/consensus.py`.

> **Honesty labels.** 🟢**L** verified-live today · 🟡**F** ours, fixture/code-only (logic proven, not live
> accuracy) · **★** peer, publicly benchmarked · **✓/claim** peer, paper/README-claimed (not re-run) · **—**
> not a goal / absent. No peer system was executed for this doc; peer numbers are self-reported upper bounds.

---

## 1. Core matrix — the truth-gate (where we compete, and mostly lead)

Only three families can even be *on* this chart, because only they touch verification: **JE** = judge
ensembles / self-consistency / debate; **CF** = conformal-abstain (CAP / ToolChain-CRC); **AF** = agent
frameworks (LangGraph / CrewAI / AutoGen / OpenAI+Claude SDK). Rows are the primitives our purpose demands.

| Dimension (anchored to reproduction-verification) | **Ours** | JE | CF | AF |
|---|:---:|:--:|:--:|:--:|
| **Cross-vendor, distinct-family** corroboration of a result | 🟢**L** | ✓claim | — | — |
| **Fail-closed on ambiguity** — abstain, don't *resolve* to an answer | 🟢**L** | ○ | ★ | — |
| **Deterministic, model-free** decision core (no LLM in the verdict) | 🟢**L** | — | ○ | — |
| **Verdict bound to objective witnesses** (tests + numeric-to-tolerance + reproduction ground-truth, signed) | 🟢**L** | — | — | — |
| **Heterogeneous-vendor multi-PC** execution substrate | 🟢**L** | — | — | ○ |

**AF is `—` across the top four on purpose:** LangGraph/CrewAI/AutoGen are model-agnostic *orchestrators* and
OpenAI/Claude SDKs are single-vendor — none ship a consensus/truth-gate primitive at all
([framework showdown](https://qubittool.com/blog/ai-agent-framework-comparison-2026)). They are peers for
*running* the work, not for *gating* it.

---

## 2. Depth on the dimensions where we lead (the defensible core)

### 2a. Cross-vendor consensus-or-flag — **LEAD, but the concept is not ours; the *composition* is**
- **What we do (verified live today):** `consensus.evaluate()` accepts a result **iff a mutually-agreeing
  cluster spans ≥2 *distinct vendor families*** (Codex≠agy≠deterministic), numeric agreement to **1e-9**;
  otherwise it FLAGS with a quantified spread and names the dissenter. Live round today: 3 agreements→ACCEPT,
  2 seeded disagreements→FLAG, all correct.
- **Nearest peer (honest):** cross-family judge panels **do exist** — e.g. Llama-3.3-70B + Cerebras-GPT-OSS-120B
  + Qwen3-32B with a meta-judge ([truth-ensembles](https://gist.github.com/bigsnarfdude/21cbae2ef56c01e0f53c223b0e2ca0b1)),
  and cross-model disagreement as an error signal is a 2026 staple
  ([2603.25450](https://arxiv.org/html/2603.25450)). **We did not invent this.**
- **The purpose-specific difference:** those panels judge **free-text quality** and *resolve* to a score. Ours
  corroborates a **reproduced numeric estimate to tolerance** and its output feeds a *gate*, not a ranking.
- **Honest limit:** verified live on **2 families** (Codex+agy) today; the 3-family caught-defect A/B/C numbers
  remain from prior runs (headless Claude unavailable, pc2 offline).

### 2b. Fail-closed on ambiguity (flag-on-any-dissent) — **LEAD operationally; CF leads formally**
- **What we do:** the gate **abstains** on disagreement (→ UNVERIFIED, enforced in the live orchestrator,
  `master a650361`). Verified live today: a panel where **2 vendors agreed and 1 conflicted was FLAGGED, not
  accepted** — i.e. no majority-rubber-stamp. This is the exact defense for our threat model (a fabricated stat
  that a majority might wave through).
- **Nearest peer (honest):** most judge/debate stacks treat disagreement as a **triage/escalation** signal that
  *resolves* to an answer by escalating to a stronger model
  ([debate judges 2510.12697](https://arxiv.org/html/2510.12697v1)) — the opposite disposition to abstention.
  **CF genuinely beats us on the *formal* side:** CAP gives a finite-sample abstention guarantee (90% coverage,
  +22.2% hallucination-AUROC, >70% lower calibration error — [CAP, PMLR v304](https://proceedings.mlr.press/v304/tayebati26a.html));
  ToolChain-CRC extends risk control under drift ([2606.18467](https://arxiv.org/pdf/2606.18467)).
- **The purpose-specific difference:** for reproduction, "escalate-and-answer" is the *wrong* default — a
  disputed pooled estimate should surface for human check, not get auto-resolved by a bigger model. Our
  disposition matches the purpose; CF's *guarantee* is what we lack.
- **Honest limit:** our abstention is a policy, **not a calibrated risk bound**; the conformal gate that would
  close this is landed but **fixture-only**, no published coverage number.

### 2c. Deterministic model-free core + objective-witness binding — **LEAD (genuinely rare)**
- **What we do:** the accept/flag decision is **plain deterministic code** — `values_agree()` (tolerance
  compare) + `extract_number()` — so **the verdict itself cannot hallucinate**. That verdict is then **bound to
  objective witnesses**: passing tests + numerical baselines + a **private reproduction corpus** (match-or-beat
  on 7/7 published meta-analyses, cross-checked to R/metafor ≤1e-4), emitted in a **signed CertBundle** with an
  objective-witness floor (a judge PASS without a passing objective witness is downgraded to abstain).
- **Nearest peer (honest):** judge ensembles put an **LLM meta-judge** at the arbitration point — itself
  fallible and non-deterministic; none bind the verdict to reproduction witnesses. Conformal frameworks are
  model-free at the *thresholding* step but aren't cross-vendor or witness-bound.
- **Why this is the real moat for the purpose:** a verifier for *quantitative* claims must not have an LLM in
  its own decision path, and must tie "pass" to a reproduced number + ground truth. That combination —
  deterministic verdict **+** objective-witness/provenance binding **+** a private ground-truth corpus nobody
  else can score against — is not something the JE/CF/AF systems do.
- **Honest limit:** "deterministic core" covers the *consensus arithmetic*; the upstream **extraction** of the
  number from a vendor's text still uses the vendor (that's why cross-vendor + witness-binding matter). Fixture
  evals prove the logic; live-vendor accuracy is still item #1 below.

---

## 3. Supporting stack — where peers lead on measurement (kept brief, on purpose)

These bear on the harness but are **not** the truth-gate core; peers are ahead here mainly on *measurement*,
not idea:

| Dimension | Ours | Peer leader | Honest gap |
|---|:---:|---|---|
| Long-term memory recall | 🟡**F** | **Mem0/Letta/Zep** — LongMemEval **93.4/94.8/63.8%** ([mem0](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)) | our store has the architecture (temporal validity, decay, claim-graph) but **no LongMemEval number** |
| Pre-push static gate | 🟢**L** | **VibeGuard** — 100%R/89.5%P ([2604.01052](https://arxiv.org/abs/2604.01052)); AI-SAST = semantic | Sentinel is broader (64 rules incl. a rare fabrication family) but **42/64 regex, P/R unmeasured** |
| Robust verifier model | 🟡**F** | **CompassVerifier** — trained verifier ([2508.03686](https://arxiv.org/abs/2508.03686)) | our judge is a prompt+regex guard, not a learned RM |

(LangGraph's durable checkpoint/time-travel graph beats our lease/requeue Dispatch on *resumability* — noted,
but it's an orchestration convenience, not a truth-gate dimension, so it's out of the core scoring.)

---

## 4. Verdict — lead / parity / lag (purpose-anchored)

- **LEAD (verified-live, uniquely ours):** a **deterministic, model-free consensus-or-flag gate that
  fail-closes on any cross-vendor dissent, binds the verdict to objective reproduction witnesses, and runs
  across heterogeneous vendors on distinct nodes.** No peer combines all four — JE has an LLM meta-judge that
  *resolves*; CF abstains formally but isn't cross-vendor or witness-bound; AF ships no truth-gate.
- **PARITY (don't overclaim):** cross-model *disagreement-as-signal* is a common 2026 pattern
  ([AdversaBench 2606.24589](https://arxiv.org/pdf/2606.24589)); we didn't invent it. Distribution and pre-push
  gating as *concepts* are common.
- **LAG (mostly measurement, not capability):** formal conformal risk bound (**CF**), published memory recall
  (**Mem0/Letta/Zep**), semantic static analysis + measured P/R (**VibeGuard/AI-SAST**), trained verifier
  (**CompassVerifier**), resumable graph (**LangGraph**).

**One line:** *uniquely combines a deterministic, fail-closed, cross-vendor, witness-bound consensus gate
(verified-live) and matches-or-beats on a private reproduction corpus — but is not yet publicly benchmarked
against peers on accuracy or memory recall.* That is the defensible claim; "world's best verifier" is not, yet.

## 5. To credibly claim best-for-purpose, still need (tied to scorecard open items)
1. **★ Live-vendor accuracy number** (scorecard #4) — today proved the *mechanism*, not an accuracy figure.
2. **Run LongMemEval once** — every memory peer posts a number; we post none.
3. **A formal coverage bound for the conformal gate** — so abstention can stand next to CAP.
4. **Measure Sentinel P/R** + move hot regex rules to AST — so the gate claim is measured.

*Peer numbers are self-reported upper bounds; re-run on our data before trusting any. 🟢L verified 2026-07-10;
🟡F fixture-only. Scores shipped code at `master a650361`.*
