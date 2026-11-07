# Systems state — 2026-11-07

**Outcome: open PRs account-wide 565 -> 435; in scope 210 -> 82.** Sections below "Integration log" record what landed.

Measured today via GitHub GraphQL/REST and local git. Out of scope (other sessions): allmeta,
meta-harness, rapidmeta-kit / RapidMeta harness, paper pipeline. Section "Integration log" is
appended as work lands.

## Portfolio numbers

- 718 repos under mahmood726-cyber. **565 open PRs**; 355 are in out-of-scope repos
  (allmeta 207, meta-harness 110, rapidmeta-kit 38).
- **In scope: 210 open PRs in 59 repos** — 157 Dependabot, 53 people/agents.
  (`gh search prs` caps at 200 and silently under-reports; these counts are per-repo GraphQL totals.)
- CI rollup on the 210: 180 success, 22 failure, 8 none. Mergeability: 179 clean, 21 conflicting,
  10 unknown. 28 are drafts. 99 date from May 2026.
- No in-scope repo has branch protection or a ruleset (0 of 44 sampled), so nothing but discipline
  gates a trunk push.

## Host constraints (these shaped the plan)

| Constraint | Measured | Consequence |
|---|---|---|
| CPU / RAM | 100% CPU; 1.1 GB free of 15.9 GB; 32 `claude`, 157 `bash`, Codex active | One test-gate lane at a time; no parallel suites |
| Disk | C: 11 GB free (96%); F: 11 GB free (98%) | Blobless clones in `C:\Projects\_int`, deleted after use |
| `C:\overmind`, `C:\Sentinel`, `C:\E156`, `C:\ProjectIndex` | NTFS junctions into F: (verified for overmind and Sentinel; the others report identical state) | "C: mirrors" in AGENTS/LIVE_CONTEXT are not mirrors. If F: fails there is no fallback |

## Per-system state

| System | Trunk @ last commit | Trunk CI | Open PRs | Local checkout |
|---|---|---|---|---|
| **Overmind** `F:\overmind` | master 4c85950, 10-29 | success | 1 (#2 draft, 61 commits ahead, green) | on `feat/shared-fact-store-2026-07-13`: 18 ahead, 1 behind master, 9 untracked; 7 worktrees |
| **Sentinel** `F:\Sentinel` | main a11c573, 10-29 | success | 2 (#6 draft, 116 ahead, "do not auto-merge"; #2 draft May docs) | on `sentinel-ast-shadow-2026-07-11`: 3 ahead, **7 behind main**, 3 dirty |
| **E156** `F:\E156` | master, 11-06 | success | 1 (#88 draft, red, source-rights HOLD) | on `wip/preserve-2026-07-12`: 45 ahead, 26 behind, **312 dirty** |
| **e156-ecosystem-starter** | main, 11-06 | success | 19 (11 draft; 7 conflicting); active worker campaign | no local checkout found in the candidates |
| **ubcma** `F:\ubcma` | master, 07-01 | success | 3 Dependabot, all mergeable | on `wip/preserve-2026-07-12`: 96 ahead, 1 behind, 25 dirty; 7 worktrees |
| **ubcma-dta** `F:\ubcma-dta` | worktree of ubcma | — | — | `methods-dta`: 16 ahead, 35 behind, 1 dirty |
| **Beast** `F:\Beast` | main, 06-08 | success | 0 | `improve/gated-work-20260704`: 3 ahead, 0 behind, clean. 3 commits never PR'd; last Pages run failed then succeeded |
| **ProjectIndex** `F:\ProjectIndex` | master c719362, 05-25 | — | 0 | 9 dirty |
| **rmfw** `C:\rmfw` | none | — | — | empty directory, not git; no GitHub repo by that name |

Other trunks that are **red**: AlBurhan, hta-artifact-standard-v2, llm-meta-analysis,
metaTransportEngine, rapidmeta-finerenone (out of scope). Trunks with **no CI at all**:
Framinghampaper, GuidelineLag, Lassopaper, transcendent-meta-analysis-lab.

## Critical: the ship gate is not running

`data/nightly_reports/latest.json` is dated **2026-05-17**. Task Scheduler has no `Overmind Nightly
Verifier`, `Overmind Morning Watchdog` or `Overmind Memory Consolidation`, so the watchdog that would
have reported this is gone as well. AGENTS/rules call this verdict "the authoritative ship gate":
any "Overmind verified" claim after 2026-05-17 has no nightly behind it. Both launchers also defaulted
to `C:\Users\user\...\python.exe`, which does not exist under the `mahmo` account.

## Top structural problems (first pass)

1. **Every live root is on a stale side branch, not trunk.** Overmind, Sentinel, E156 and ubcma all
   run from `wip/*` or feature branches. Hardening merged to trunk does not reach what the machine
   executes: F:\Sentinel lacks #5 "Enforce blocking pre-push hooks by default", and its hook still
   reads `MODE="${SENTINEL_MODE:-warn}"`. A merge to trunk is not a deployment here.
2. **Dependabot is the backlog.** 157 of 210 PRs, ungrouped, 8 per repo, mostly untouched since May.
3. **Stale `wip/preserve-*` branches hold unique work.** They were created as a safety net and never
   reconciled, so trunks and live roots keep diverging (E156 45/26, ubcma 96/1, Overmind 22/6).
4. **Fail-closed work sits in long-lived drafts.** Overmind #2 and Sentinel #6 together carry 177
   commits and are explicitly drafts, so the fixes they claim are not live anywhere.
5. **The C: "mirrors" are junctions**, so the documented fallback does not exist.

## Triage so far (Dependabot, the 157)

| Class | Repos | Plan |
|---|---|---|
| Green PR CI, trunk green | 26 repos, ~140 PRs | Batch per repo: baseline gate, merge, gate, ff push, ls-remote |
| Red PR CI | AlBurhan 3, hta-artifact-standard-v2 4 (of 6), metaTransportEngine 5 | Blocked on red trunk. Left |
| Conflicting | overlap-detector 2 | Dependabot rebase |
| No runnable local gate | to be determined per repo | Left: an unexecuted gate is not a pass |

## Integration log (2026-11-07)

Every merge below was gated on the merged tree and proven with `git ls-remote` or GitHub state.

### Overmind

- **Merged #3** (`3198c91`): launcher fix, wedging/liveness, shared fact store, plus 8 review fixes.
  Local gate 1582 passed, 20 skipped, exit 0; CI green on 3.11, 3.12, 3.13.
- **`F:\overmind` moved to master** (was on a feature branch), so the hardening is now live.
- **Left: #2 and successor #4.** #2 had a confirmed P0: every COMPLETED task became PAUSED at startup,
  and nothing requeues PAUSED. Its body bars automatic merge. **#4** is #2 plus fixes on current master:
  1692 passed, 21 skipped, exit 0; CI green. It is a draft for Mahmood.
- Superseded branch: `fix/memory-valid-from-recall-20261029` (tree identical to 4c85950). Not deleted.
- Unmerged eval branches: `wip/preserve-2026-07-12` contains 5 chain branches. `precision-fix`,
  `recover/premerge-verify` and `improve/mem-recall-locomo` each hold unique work.

### Sentinel

- **Merged #7** (`18716a7`): main now contains what the live checkout runs. Local gate 925 passed,
  1 load-only timeout; CI green on Ubuntu and Windows. CI caught a self-scan failure the local gate
  missed: planted fixtures blocked it, fixed with `sentinel:skip-file`.
- **Closed #2** (superseded: says 28 rules, the manifest has 64).
- **Left: #6, successor #8, #9.** #6 would reject all 52 deployed hooks, and its body bars auto-merge.
  **#8** is #6 plus fixes: 1146 passed, 1 load-only timeout. Blocked on the HMAC key: manifest drift is
  43 rules and could not be re-signed here. **#9** makes the hook scan pushed refs, not HEAD. It has
  5 failing static-shape tests and needs rebasing after #8. Not merge-ready.
- **`F:\Sentinel` was not moved.** It has uncommitted WIP (`writer.py`, `provenance.py`), and changing
  the live scanner while other sessions are pushing is Mahmood's call.

### Other systems

- **Beast**: main fast-forwarded to `cbe3155` (Knapp-Hartung p-value now matches its CI; continuous
  arm counts). 111 tests pass.
- **cinema #1, fragility-atlas #9** merged. fragility-atlas `E156-PROTOCOL.md` still quotes the old
  403/58% figures.
- **Dependabot: 129 of 157 merged across 24 repos.** Gated per repo: trunk baseline, merge, same gate,
  no new failures, fast-forward push, ls-remote. 52 were adjacent one-line bumps re-applied with zero
  context. No pushed trunk has a failed check; 24 still had CI pending when this was written, so
  trunk CI for the last pushes is unconfirmed. Limits: requirement floors above the installed version
  were tested on the older version (PR CI covers the floor). bias-forensics and e156-student-starter
  keep one local-only failure each, identical before and after, with trunk CI green.
- **28 Dependabot left**: overmind-public 8 (its suite is unstable here: baseline 36 failed, 17 errors),
  overmind-testbed 5 (no gate: tests need local project paths), hta-artifact-standard-v2 6, AlBurhan 3,
  metaTransportEngine 5 (red trunks), ubcma 1 (conflict).
- **Closed superseded**: rmstnma #1 (subset of #2), hta-transportability #1,
  hta-unified-intelligence #1, value-based-hta #1. Branches kept.
- **AlBurhan #4, llm-meta-analysis #2** open. AlBurhan's real root cause: `aact-kit` is not on PyPI.
  It now pins the source repo, but aact-kit needs Python >=3.10 and CI's matrix has 3.9.
  llm-meta-analysis: `Test (Python 3.10)` is green; Lint (307 violations) and image builds remain red.
- **Not touched**: e156 #88 (deliberate source-rights HOLD), e156-ecosystem-starter (active campaign,
  Synthesis content under that hold).

### Needs Mahmood

1. Re-register the nightly: `scripts/install_overmind_task.ps1`. Takes about 73 minutes a night on a
   saturated box. Until then nothing has verified the portfolio since 2026-05-17.
2. Overmind #4: accept it? A persisted COMPLETED task is not revalidated (same as master).
3. Sentinel: provide the HMAC key for #8; then decide #9; then move `F:\Sentinel` to main.
4. hta-artifact-standard-v2 PCG32: the DES fallback fails the reference vector, and the fix changes
   reported meanCost and meanQALY.
5. fact-store content in Overmind: `lanes/tuesday_demo.py`, `other_lanes.py`, `known_bad.py` and seeds
   are one-off RapidMeta content. Also check `evals/judge_cot_goldenset.py` and
   `overmind/evidence/data/gold_reviews/*` on public master against the ground-truth rule.
6. RISKY PRs with concrete bugs, left open:
   - Pairwise70 #3: changes bootstrap CIs at k=3,4; touches the GRMA 0.940 coverage claim.
   - Lassopaper #1: tau2_null=0 becomes NA, then is dropped.
   - dataextractor #1: `HR 0.74 (95% CI 0,58-0,95)` parses as CI [0, 58].
   - trial-truthfulness-atlas #1: unbounded surname match ("Park" hits "Parkinson").
   - screen-reproducible #1: Screen vs NB flips sign; body says not to merge without review.
   - Held by their bodies: cardiooracle #6, Framinghampaper #1, llm-meta-analysis #1.
   - rct-extractor-v2 #16 is clean, but merging turns master red: 4 jobs call scripts absent from the repo.
7. `import overmind` outside the repo loads a stale site-packages copy (`pip install -e`).
8. Group Dependabot updates in `dependabot.yml`; not done, ran out of budget.
