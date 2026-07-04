# Harness-scan merge record — 2026-07-04

Source: `C:\Projects\harness-scan-2026-07-04.md` (frontier scan, 27 findings, 3 tiers).
This records **what was merged** (adopt-now only), the **citation-verification results**, and the
**promising / rejected** tiers left unmerged (recorded, not adopted). No heavy dependency added; all
merges additive + no-regression; each merged as its own commit.

## Citation verification (before quoting any number)
| Claim | Result | Action |
|---|---|---|
| **arXiv:2604.12198 — 96.6% / 1.8%** (re-execution vs reading) | **VERIFIED** by direct fetch: "85 of 88 critiques (96.6%) surface only after… run a calculation, reading-only ceiling 1.8%" | **Quoted** in D2/D3 (AN-1) |
| **rewardhackwatch** — Apache-2.0, trajectory-only, regex+AST, **89.7% F1** | **VERIFIED** repo is Apache-2.0, does not execute code, regex+AST+DistilBERT layers; 89.7% F1 on MALT is **authors' self-reported** (not independently reproduced) | Integrated as clean-room regex+AST (AN-6); F1 **not quoted as ours** |
| **OpenAI Agents SDK** — control/compute split + snapshot/rehydrate | primary page **403'd**; **corroborated** via multiple secondary sources (RunState / session / snapshot persistence levels) | AN-10 provenance IDs merged with the corroboration caveat |
| **Crab 100% recovery** (arXiv:2604.28138) | **VERIFIED** but scoped: 100% on shell-intensive + code-repair only (8% chat baseline, 87% traffic cut, 1.9% overhead) | **PV-tier — not merged**; recorded only (validate on our tasks first) |
| **Wald-SPRT "maintains accuracy"** (arXiv:2605.19193) | accuracy claim **unverifiable from PDF** (per scan) — not independently checked | **PV-tier — not merged / not quoted** |
| **LangGraph "73,000×"** | **vendor claim** | **Rejected tier — not merged / not quoted** |

## Merged — adopt-now (this session)
| ID | Delta | Commit | Kind |
|---|---|---|---|
| **AN-2** ⭐ | Two-slice FROZEN-benchmark rule (sealed slice evolution never reads/scores/tunes; promotion needs a frozen win too) — **live in the harness before the real A/B/C run** | `49920a3` | code + governance |
| **AN-6** | Eval-gaming pre-filter (clean-room regex+AST, trajectory-only, no code exec) over any PASS | `6370199` | code + fence |
| **AN-3** | Kish `n_eff` decorrelation sub-gate under D1 — consensus measured, not assumed; recorded per verdict | `a6fdbda` | code + spec |
| **AN-5** | `passk` (all-k-succeed) promotion bar + signature-determinism witness under D3 | `ab6fd2a` | code + spec |
| **AN-7** | In-house BenchJack-style adversarial corpus audit before promotion; exploits → negative-memory fixtures (found 10 real ones) | `fbb4ac8` | code + spec |
| **AN-1** | Cited 96.6%-re-execution axiom under D2/D3 + Reproduce→Review→Reflect + %-within-tolerance | `cf14109` | spec |
| **AN-4** | check≠repair separation + reproducibility snapshot (Stage-4/D2) | `cf14109` | spec |
| **AN-8** | success-is-silent/failures-verbose gate-output contract + ratchet rule (§0) | `cf14109` | spec |
| **AN-9** | clean-context verification + capability-router-not-difficulty-escalator (Stage-4/§1.5) | `cf14109` | spec |
| **AN-10** | symmetric cross-vendor provenance (workflow/snapshot/op IDs) + OpenAI max_tokens_per_thread (D4/D5/D7) | `cf14109` | spec |
| **AN-11** | cost-per-accepted-reproduction + rework multiplier (D5/§3.3) | `cf14109` | spec |

*(AN-12 order-randomization/length-norm judge contract, AN-13 mixed-evidence regression class, AN-14
reliability gate sub-scores, AN-15 accepted-without-revision abstention tier — also adopt-now in the
scan's table but outside the explicit priority list; deferred to a follow-up, recorded here.)*

## Recorded, NOT merged — promising-needs-validation (shadow-first; measure on §3 corpus)
PV-1 Crab turn-boundary checkpoint driver · PV-2 Claude Code Dynamic Workflows backend · PV-3 Wald-SPRT
sequential consensus governor (non-binding futility) · PV-4 duh forced-adversarial-framings (AGPL, mechanism
only) · PV-5 star-chamber agreement tiers · PV-6 trajectory "recovery-tips" memory class · PV-7 git-native
durable task-DB · PV-8 OTel common trace schema (swappable exporters) · PV-9 ReproRepo/REPRO-Bench seed
material. **Each must beat/validate on the frozen+held-out slices before it touches a ship path.**

## Recorded, NOT merged — rejected (with reason, per scan §4.3)
Heavyweight orchestration frameworks (LangGraph/Temporal/DBOS/Restate/Inngest/hatchet-icepick) — rip-replace
of working Dispatch, borrow only the idempotency-key concept · Managed agent services (hosted black boxes
conflict with D2/D4; OpenAI legacy Evals EOL Nov 2026 = do-not-gate-on-it) · Activation-based hack monitoring
(needs activation access closed vendors don't expose) · Semantic-Quorum/PBFT (BFT solves adversarial collusion,
not our correlated-judge threat) · RL-side reward-hacking fixes (confirmed to fail) · LLM-council long-tail +
persona bundles (redundant) · Antigravity IDE / Claude-in-Chrome / Codex Remote / Sonnet-5-as-default
(end-user surfaces or model swap; Sonnet-5 goes on an eval-gated allowlist, never auto-promoted) ·
trained memory-skill model (already rejected in RELIABILITY.md).

**Consistency:** the rejected tier matches the standing guardrail (no heavyweight-framework rip-replace) and
the prior `RELIABILITY.md` rejections.
