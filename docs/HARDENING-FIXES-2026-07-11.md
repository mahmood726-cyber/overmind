# Cross-vendor review — stop-the-line fixes (2026-07-11)

Fixes for the P0/P1 findings in `CROSS-VENDOR-REVIEW-2026-07-11.md` (2 P0 fail-opens
+ the precision-fix blind spot, both P0s CORROBORATED by Codex A (openai) **and** agy
(google) **and** manual verification). **The precision-fix merge stays BLOCKED until
these land and the re-run numbers are reviewed.** Feature branch; not merged/pushed.

## Vendor liveness (real execs — status lies), verified this session
| lane | family | result |
|---|---|---|
| Codex A (laptop `100.80.183.43`) | openai | **LIVE** (`OK`) — dropped mid-session once, recovered |
| Codex PC1 (local `codex exec`) | openai | **LIVE** (`OK`, 10,332 tokens) — slow first response (sandbox runner) |
| Codex B (Noreen `.codex-noreen`) | openai | not used — report found it 401/revoked while the CLI exited 0 |
| agy (local) | google | **LIVE** (`OK`) — returned garbage once (cold-daemon churn), recovered on re-probe |

Genuine 2-family panel = **Codex A + agy**; the eval re-run below used it live.

---

## P0 — merge blockers (each now FAILS CLOSED, with a test proving it)

**Root cause (both):** the fail-closed decision was written as *"relabel a completed
check as skipped"* instead of *"return a failing result."* `VerificationResult.success`
defaults to `True` and is independent of `skipped_checks`, so *"don't count it as a
pass" ≠ "don't ship."* A gate that cannot return failure is not a gate.

### P0-1 — a FLAGGED consensus shipped (`success=True`)
`orchestrator.py` `_apply_completion_gates`: the `consensus_flagged` branch appended
`semantic_requirements` to `skipped_checks` **without returning**, falling through to
`success=True`; it also skipped the confident-FAIL early return, so enabling
fail-closed could flip a would-be FAIL to PASS.
**Fix:** the branch now **returns `VerificationResult(success=False, …)`** with
`semantic_requirements` recorded as a *required, failed* check. A non-PASS consensus
(FLAGGED **or** CONSENSUS_FAIL) never ships.
**Test:** `test_failclosed_flagged_quorum_fails_closed` (asserts `success is False`);
`test_failclosed_disagreement_does_not_flip_fail_to_pass`. The prior test that
asserted `success is True` on a flag was itself encoding the fail-open — corrected.

### P0-2 — total vendor outage bypassed the gate (`success=True`)
When ALL backends error, `QuorumJudge` tags `judge_error` **and** computes a
`NO_USABLE_RESPONSES` consensus — but `judge_available` short-circuited the whole
block before the consensus was consulted.
**Fix:** the consensus outcome is evaluated **before** the `judge_error`
short-circuit; an all-vendors-down (non-PASS) outcome fails closed.
**Test:** `test_failclosed_all_vendors_down_fails_closed`.

### P1-3 (compounds the P0s) — silent resolver→None disabled enforcement
`llm_judge._resolve_consensus_outcome`'s `except: return None` silently disabled
fail-closed enforcement. Now **WARN-logs with traceback** (still non-raising for
hot-path/circular-import safety) so a resolver regression is visible.

### P1-4 — low-confidence judge FAIL counted as a pass
A judge FAIL with confidence <0.7 was marked *completed* (a pass). Now a FAIL is
recorded **skipped** (never completed); a confident FAIL still blocks.

---

## P0-3 — the precision-fix blind spot: OVERSTATED SIGNIFICANCE (3-way agreement)

All three reviewers independently produced the same counterexample: a conclusion
claiming *"significantly reduces mortality"* while the CI **spans 1.0** sailed through,
because the calibrated rule says "a CI crossing 1.0 is never a defect." Correct as far
as it went — but it removed the check without adding the right one, and the class was
in **neither slice**, so recall=1.000 never tested it.

**Fix (taxonomy + prompt + eval, all three):**
- **New defect class** `overstated_significance` (`benchmark/tasks.py`,
  `REVIEWER_ONLY_KINDS`).
- **Prompt** (`REVIEW_INSTRUCTION_CALIBRATED`, propagates to `_PLUS`): *a conclusion
  asserting a SIGNIFICANT / clear / conclusive / demonstrated effect while the 95% CI
  INCLUDES 1.0 (p ≥ 0.05) IS a defect* — reconciled with the retained "a
  non-significant result DESCRIBED as such is not a defect."
- **Eval seeding** (`benchmark/generate.py`): each fixture whose true CI spans the null
  now also yields an `__overstated_significance` defect (conclusion claims
  significance; data valid so no witness fires). 24 seeded across the corpus →
  **10 in slice 1, 4 in slice 2** (both slices now test the class).
- **Tests:** `test_overstated_significance_seeded_only_when_ci_spans_null`; balanced-
  slice test updated for the conditional class.

**Re-run numbers (honest, even if recall drops — we now test a class we ignored):**

Live re-run, frozen `_PLUS` prompt (+ overstated criterion) + corroboration, both
vendors (Codex A + agy; agy's cold-daemon failures re-run locally to 100% usable):

| | recall | FAR (raw C) | FAR (corroborated) |
|---|:--:|:--:|:--:|
| slice 1 (149; **+10 overstated**) | **136/136 = 1.000** | 7/13 = 0.538 | **0/13 = 0.000** |
| slice 2 (96; **+4 overstated**) | **76/76 = 1.000** | 12/20 = 0.600 | **1/20 = 0.050** |
| **POOLED** | **212/212 = 1.000** [0.982,1.0] | — | **1/33 = 0.0303** [0.005,0.153] |

**The blind spot is CLOSED and recall did NOT drop.** Both vendors now flag the
overstated-significance defect ("the CI includes 1.0, so a claim of a significant /
conclusive effect overstates the evidence") — all 14 seeded overstated defects caught.
Pooled recall rose 198/198 → **212/212** (the 14 previously-untested defects) at the
**same pooled FAR 0.0303**.

**Honest cost — the criterion made the RAW prompt much noisier (this corrects an
earlier claim).** Raw-C FAR jumped from ~0 to **0.54 / 0.60**: primed to look for
overstated significance, the vendors over-flag clean *non-significant* artifacts
(plain directional conclusions, no explicit "significant") as overstated. **Fix #2
(corroboration) contains it** — the over-flags are single-vendor — bringing FAR back
to 0.000 / 0.050. So **corroboration is now LOAD-BEARING, not redundant**: the precision
doc's "Fix #2/#3 win nothing once Fix #1 lands" no longer holds with this criterion.
The one pooled residual FA is agy's structural-false-claim mode (a method/random-vs-
fixed over-read Codex correctly accepts; corroboration keeps it because it reads as
structural) — which clean it lands on varies run-to-run.

**Honest follow-up (not done here):** the criterion, as written, is too broad — it
should fire only on an EXPLICIT significance claim (significant / significantly /
conclusive / demonstrated), not on any directional conclusion over a wide CI. A more
precise wording would cut the raw FAR without needing corroboration to carry it. The
winning config already achieves FAR 0.0303 / recall 1.000, so this is a refinement,
not a blocker.

---

## P1 — correctness / security (overmind)

- **P1-7 (`kill_process_tree`)** — added `check=True` so a taskkill FAILURE triggers
  the `proc.kill()` fallback (local grandchildren no longer leak). Documented the
  boundary: the LOCAL tree is killed; a REMOTE `ssh…codex` process is not a local
  descendant — remote teardown is the SSH invoker's job (channel-close SIGHUP); a fully
  robust remote kill needs remote PID tracking (noted, not silently claimed). Test:
  `test_kill_process_tree_falls_back_when_taskkill_fails`.
- **P1-10 (`split_command`)** — a relative Windows path (`pytest tests\integration.py`)
  hit posix `shlex.split`, which ate the backslash → `testsintegration.py`. Now any
  command containing a backslash uses non-posix splitting. Test:
  `test_split_command_preserves_windows_relative_backslash`.
- **P1-11 (PowerShell validator)** — the exact-match block-list missed prefix forms
  (`-e`/`-en`/`-enc`/`-ec` → `-EncodedCommand`, `-c`/`-com` → `-Command`), so
  `powershell -enc <b64> -File ok.ps1` passed. Now any arg PowerShell would resolve to
  `-Command`/`-EncodedCommand` is blocked, even alongside a valid `-File`. Test:
  `test_validate_powershell_blocks_encodedcommand_prefixes`.

## P1 — cluster-harness (separate repo/branch `fix/quorum-lane-crash-panel-width-2026-07-11`)

- **P1-5** — a lane raising in `_run_one_lane` re-raised out of `run_quorum` between
  `mark_quorum_running` and `_persist`, wedging the job in RUNNING. Now a lane crash is
  counted as an unusable vote (panel still resolves + persists), and a top-level guard
  finalises the job to a terminal `error` on any other escape. Tests: lane-crash
  finalises terminal.
- **P1-12** — default panel width `max(quorum, 8)` dispatched the heavy verify prompt
  to every vendor; now defaults to the quorum count (a lane failure fail-closes to
  cannot_form_quorum instead of pre-burning all vendors). Test: default panel == quorum.

---

## Record correction — "no regression / no happy-path cost" was NOT fully true
The precision doc's §5 claim is corrected: (a) **P0-1** was a fail-open regression vs
the pre-merge FAIL path (now fixed); (b) **P1-10** was a Windows happy-path regression
(backslash corruption, now fixed); (c) **P1-12** added a happy-path dispatch cost (now
reduced). The consensus/reachability *modules* are opt-in and cheap when idle — the
claim held for those in isolation, but not end-to-end.

## Deferred (with reasons)
- **P1-6** (SQLite `database is locked` in the reroute path) — the *source* of some
  P1-5 lane crashes; P1-5 now CONTAINS it (error vote + terminal finalise). The lock
  itself (serialise the concurrent `mark_node_unreachable` writes) is a deeper
  cluster-harness change — deferred, contained.
- **P1-8** (safe_exec FD/reader leak on double-timeout), **P2-13** (pure-numeric
  witness excluded from disagreement — latent, QuorumJudge never sets `value`),
  **P2-14** (majority-of-dispatched floor), **P2-15/16** (reachability park/stampede),
  **P2-17/18** (router caps null-crash/fallback), **P2-19/20/23** (reranker
  thread-safety/OOM/network-claim — memory repo), **P2-21** (ReDoS nested-group),
  **P2-22** (jobtype NULL) — all real, non-blocking hardening debt; several live in
  other repos/branches outside this merge. Listed for a follow-up hardening pass.

## Regression status
Full overmind suite green except two environmental TIMING flakes under the concurrent
live-eval load (both proven pre-existing / load-induced, not caused by these changes):
`test_orchestrator_pauses_on_policy_block` (passes on re-run) and
`test_windows_powershell_pipeline_is_quiet_on_broken_pipe` (20s CLI-startup timeout
under load). Re-confirmed on a quiet machine below.
