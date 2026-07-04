# swipe-file — reusable `/loop` specs, loss template, prompts

Vault workflow #5. Copy-paste ready. Grounded in verified commands ([[src-claude-code-docs]]).

## Standard `/loop` template
`/loop [verifiable end state], only touching [scope], stop after [X iterations or $budget], use [skill],
use verifier agents for [checkpoint], keep a memory file at [path].`

## The 4 lane specs (see the checklist for full text)
```text
# (a) RapidMeta QA
/loop until every dashboard passes the denominator fence (events<=N) + R-parity gate,
  only touching F:\rapidmeta-finerenone, stop after max 20 iters OR $15;
  if 50 validate in a row -> TASK_COMPLETE; after 3 unrecoverable retries -> TASK_FAILED:[reason],
  use rapidmeta-qa skill, verify with Codex(xhigh) on 2x2/denominator (found-nothing must FAIL cE>cN canary),
  memory F:\rapidmeta-finerenone\PROGRESS.md.

# (b) Methods cross-vendor witness
/loop until Claude AND a different vendor approve the SAME unchanged artifact,
  only touching <methods-repo>, stop after max 10 rounds OR $10;
  both approve -> TASK_COMPLETE; no convergence/stall -> TASK_FAILED:[reason],
  use methods-objective-gate skill, verify with Codex(xhigh)+agy (reviewer!=writer),
  memory <methods-repo>\PROGRESS.md.

# (c) Journal-upgrade
/loop until every claim traces to a source and uncertainty is explicit,
  only touching the manuscript doc, stop after max 15 iters OR $12;
  criteria met -> TASK_COMPLETE; blocked/exhausted -> TASK_FAILED:[reason],
  use journal-upgrade skill, verify with different-vendor citation/claim-fidelity check,
  memory <doc-dir>\PROGRESS.md.

# (d) Clinic monitoring
/schedule daily: /loop until every scenario hits its consecutive-success streak,
  only touching monitors+baselines (read-only prod), stop after max 8 checks/run OR $5;
  all streaks hit -> TASK_COMPLETE; scenario fails N times -> TASK_FAILED:[scenario],
  use baseline/recovery-proof skill, verify anomalies with different-vendor spot-check,
  memory <clinic-dir>\PROGRESS.md.
```

## LFD loss-function template (per loop) — [[src-lfd]]
- **TARGET:** <verifiable end state; blinded answer key; measured mechanically at right resolution>
- **CONSTRAINTS:** wall-clock, $ cap, allowed models/vendors/concurrency, methodology
- **INSTRUMENTS:** the CLI/gate that makes each constraint real (node --check, Playwright, byte/numeric
  diff, R-parity, truth-gate, `claude -p --output-format json` for $)
- **FORCED ENTROPY:** overfit-reflection each cycle, forced jump on stall, iteration/hypothesis log,
  planted-bug canary, cheat-museum

## Pro-tips
Cap iterations AND $ · effort `high` default / `xhigh` complex only · fresh subagent context ·
`/compact` before long runs · keep skills/CLAUDE.md SHORT.
