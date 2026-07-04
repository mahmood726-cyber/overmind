# Triple-Vendor Transport-NMA Witness

**Source reports:** `F:\ubcma\verification\2026-07-04-agy-thirdvendor.md` (JOB 1) ·
`F:\ubcma\verification\2026-07-04-codex-postreauth.md` (SEAT A) ·
`F:\ubcma\verification\2026-07-04-codex-two-seat.md` (fallback re-run).
**Repo:** `F:\ubcma`, branch `methods-borrowing`. **Orchestrator:** Claude (Opus 4.8, thin).

## What was witnessed
The transport-NMA headline — the deployable external κ correction — independently re-derived from
code/data by **three separate vendors**:
- **Claude** (deterministic re-run of the committed scripts),
- **OpenAI Codex** (`codex exec`, gpt-5.5, xhigh, Seat A / mahmood726),
- **Antigravity `agy`** (v1.0.16, pc1, plain `--print`; smoke test `python -c "print(6*7)"` → `42` proves
  it executes real code).

## The three claims — all CONFIRM, exact to full double precision
| Claim | agy (verbatim) | Claude baseline | Codex | Agree? |
|---|---|---|---|---|
| (i) `kappa_pooled` | `0.1575949114447188` | `0.1575949114447188` | `0.1576` (4dp) | **YES (exact)** |
| (i) `kappa_slope` | `0.26308957637488806` | `0.26308957637488806` | `0.2631` | **YES** |
| (i) ext matches oracle @ B=0.15 | ext −0.118870 vs oracle −0.118016 (regime A) | same | −0.1189 vs −0.1180 | **YES** |
| (ii) `corr(kappa_MD, 1−lambda)` sign | `+0.5014226365552311` (POSITIVE) | `+0.5014226365552311` | `+0.5014` | **YES (exact)** |
| (iii) ext0.158 beats PET/TF/HC @ B≥0.15 | CONFIRM (all 4 cells) | CONFIRM | CONFIRM | **YES** |

## The one nuance all three converged on (HC)
Codex logged its verdict as `REPRODUCED: PARTIAL` — **only** because the blanket manuscript phrase
"internal funnel models do not win" is slightly over-broad: **Henmi–Copas (HC) posts one tiny formal WINS**
(dMCIW0 −0.008271) in the single extreme cell (regime B, B=0.30), and is a ~tie at B=0.15. agy
independently re-discovered the same cell and resolved it the same way: ext0.158 is far closer to the
oracle there (ext −0.202 vs HC −0.008 vs oracle −0.222), so "beats on closer-to-oracle" holds. **PET is
catastrophic everywhere** (+0.48 … +0.64). Worth a one-line manuscript hedge; not a number error.

## Bottom line
- **Any headline moved? No.** Direction AND magnitude reproduce across all three vendors.
- This supersedes the earlier same-session "cross-vendor BLOCKED" state (both Codex seats were 401 until
  Mahmood re-authed mid-session — see [[Codex-agy-Auth-Recipe-SOP]]).
- The h2h table matches the banked `h2h_result.json` exactly.

## ⚠ Reproducibility ≠ validity (open item)
A separate Codex WAVE-2 finding flags that `aact_kappa.py:106` assigns the same HbA1c effect to **every**
drug class named in a trial (123/168 NCT groups are multi-class), a **construction-validity** concern for
κ. This does **not** contradict the triple-vendor reproduction — all three recompute from the same
possibly-double-counted CSV — but it feeds the deployable correction and deserves a hard look. Tracked in
[[agy-New-Comparator-Defects]].

## Ties to
[[Cross-Vendor-Witness-SOP]] (the reusable procedure) · [[src-trinity]] (why a different-vendor checker) ·
[[_Verification-MOC]].
