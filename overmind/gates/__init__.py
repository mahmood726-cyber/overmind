"""overmind.gates — the ENFORCEMENT layer.

The fact store (overmind.factstore) *tracks* provenance and taint. That is
necessary but, on its own, decoration: on 2026-07-13 an audit found the store
had ZERO enforcement at the export/render/briefing boundary, which is the exact
path a fabricated diagnostic figure (DTA70) took to Mahmood's briefing.

This package is the missing chokepoint. Every number that crosses INTO a
document, slide, app page, or a message to the user must pass through a gate
here, and every gate FAILS CLOSED. A gate that cannot be tripped is not a gate.

Ranked by damage prevented (== how much truer it makes the Kampala answer),
per the 2026-07-13 cross-vendor review (Codex/GPT-5 + agy/Gemini, verbatim in
HARNESS-SELF-REVIEW-2026-07-13.md):

  Gate 1  export_gate    F2  synthetic / unlocated numbers cannot be exported
  Gate 2  layer_gate     F1  coverage/accuracy claims must declare their layers
  Gate 3  blindspot_map  F3  a blind spot shared by all checks is a LOUD failure
  Gate 4  panel          F4/F6/F7  cross-family, fail-closed, abstention != vote
  Gate 5  lane_brake     F5  a lane that serves no failure/Kampala datum: refused
"""
from .contract import Claim, ClaimType, SourceTier
from .export_gate import (
    ExportBlocked,
    guard_export,
    guard_export_from_store,
    guarded,
)
from .layer_gate import LayerCoverageError, guard_layers, APPLICABLE_LAYERS
from .blindspot_map import (
    ErrorClass,
    Check,
    BlindSpotError,
    coverage_report,
    assert_no_shared_blindspot,
    DEFAULT_CHECKS,
)
from .panel import (
    Vote,
    PanelError,
    AbstentionError,
    adjudicate,
)
from .lane_brake import LaneSpec, LaneRefused, admit_lane

__all__ = [
    "Claim", "ClaimType", "SourceTier",
    "ExportBlocked", "guard_export", "guard_export_from_store", "guarded",
    "LayerCoverageError", "guard_layers", "APPLICABLE_LAYERS",
    "ErrorClass", "Check", "BlindSpotError", "coverage_report",
    "assert_no_shared_blindspot", "DEFAULT_CHECKS",
    "Vote", "PanelError", "AbstentionError", "adjudicate",
    "LaneSpec", "LaneRefused", "admit_lane",
]
