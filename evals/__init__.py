"""Overmind/Sentinel measurement harness.

Held-out evals that turn "robust by design" into "robust by evidence".
Implements recommendation #1 of docs/SYSTEMS-BENCHMARK-VS-FRONTIER.md.

Three evals, each writing a reproducible JSON score to ``evals/results/``:

1. ``specbench_style``  — SpecBench-style validation-vs-held-out gap for the
   witness pipeline (the reward-hacking signal).
2. ``judge_masterkey``  — adversarial / master-key judge eval (false-PASS rate
   on degenerate inputs, accuracy on genuine ones).
3. ``memory_recall``    — LongMemEval-style memory recall/precision probe
   (does recall return the CURRENT fact and suppress superseded ones?).

Run all three with ``python -m evals.run_all`` or ``make evals``.

Truth-first contract: these evals never loosen judge / Sentinel / witness
behaviour to make a score look good. The numbers are reported as measured.
"""
