# Overmind Makefile — measurement harness entrypoints.
#
# `make evals` runs the held-out measurement suite (SpecBench-style gap, judge
# master-key, memory recall) and writes reproducible JSON to evals/results/.

PYTHON ?= python

.PHONY: evals evals-specbench evals-judge evals-memory test

evals:
	$(PYTHON) -m evals.run_all

evals-specbench:
	$(PYTHON) -m evals.specbench_style

evals-judge:
	$(PYTHON) -m evals.judge_masterkey

evals-memory:
	$(PYTHON) -m evals.memory_recall

test:
	$(PYTHON) -m pytest -q
