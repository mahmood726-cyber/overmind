"""Operator-configurable policies layered on top of the verdict engine.

The verdict engine itself (`overmind.verification.witnesses`,
`overmind.cert_bundle.Arbitrator`) is deterministic and intentionally policy-free.
This package adds policies on top — escalation rules, threshold alarms,
release gates — that an operator can tune without touching the engine.
"""
