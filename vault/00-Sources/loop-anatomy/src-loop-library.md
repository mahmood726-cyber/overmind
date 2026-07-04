# Loop Library (Forward Future) — concrete loop templates

**URL:** https://signals.forwardfuture.com/loop-library/
**What:** curated repeatable agent loops, each stated as objective + proof + explicit STOPPING CONDITION.

## VERIFIED (fetched page) — templates we adopt (stop conditions quoted verbatim)
- **Multi-LLM convergence loop** → methods cross-vendor witness — *"only when both approve the same
  unchanged version."*
- **Clodex adversarial-review loop** → our Codex-checker — *"when Codex approves, only accepted findings
  remain, progress stalls, or iteration cap is reached."* (Supplies the hard iteration-cap STOP.)
- **Quality streak loop** → RapidMeta QA — *"After [N] successful cases in a row"*; adds regression+benchmark coverage.
- **Production error sweep** → error sweep — *"If no actionable errors are present, stop without making changes."*
- **Research-to-artifact loop** → journal-upgrade — proof *"important claims trace to sources, uncertainty
  is explicit"*; stop *"when the artifact meets its acceptance criteria."*
- **Post-release baseline / recovery proof** → clinic monitoring — stop *"when every scenario reaches its
  predefined consecutive-success streak."*

## Ties to
[[src-ai-edge-loop-guide]] (the `/loop`+`/goal` realization) · [[swipe-file]] (filled-in specs).
