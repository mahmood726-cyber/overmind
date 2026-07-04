"""Reliability-hardening primitives (supervised drain, cap-log, anti-wedge,
routing guard, checkpoint/resume, auth preflight).

All modules here are ADDITIVE and consumed opt-in — importing this package does
not change any existing behavior. See harness/RELIABILITY.md for the workstream.
"""
