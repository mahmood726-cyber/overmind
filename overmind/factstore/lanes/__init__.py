"""Adoption layer — the WIRING that makes the shared fact store actually protect
something. The store (architecture fix #1) was built and trip-tested but *nothing
called it*: a gate nothing calls protects nothing.

Each module here wires one live lane's EMIT POINTS to the store: it records that
lane's on-screen / shipped numbers as facts (with real source locators), verifies
the real ones through the cross-family panel, and proves the known-bad ones are
unconsumable. The proof is runnable — ``python -m overmind.factstore.lanes`` runs
every lane and prints a number-by-number pass/fail table, exiting non-zero if any
number that is supposed to be reportable cannot pass ``consume_verified``.

Priority order matches the risk of a bad number reaching Mahmood's mouth on
Tuesday: the demo lane first, then the corpus/harms/pico/pre-extracted/gold lanes,
with the known-bad artefacts seeded synthetic and proven blocked.
"""
# Submodules (hypotheses, tuesday_demo, known_bad, ...) are imported directly by
# callers, e.g. ``from overmind.factstore.lanes import tuesday_demo``. They are NOT
# eagerly imported here — that would create a circular import when a submodule is run
# as ``python -m overmind.factstore.lanes.<name>``.
__all__ = ["hypotheses", "tuesday_demo", "known_bad"]
