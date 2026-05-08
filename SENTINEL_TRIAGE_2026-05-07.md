# Sentinel Findings Triage — 2026-05-07

<!-- sentinel:skip-file — this audit document quotes hardcoded paths as
evidence (validation_details.json pdf_path columns, allmeta dosehtml
launchers, etc.). The paths are the data being analysed, not application
configuration. Same pattern as E156/rewrite-workbook.txt. -->

Read-only audit of the **141,992 BLOCK / 17,484 WARN** Sentinel violations
aggregated by Overmind's nightly_2026-05-06 report. No edits performed.
Corpus: 260 repos with sentinel-findings; analysed top-10 repos by
BLOCK count (covers ~94% of BLOCKs) and top-10 rules (covers 99.7% of
all violations).

## Headline numbers

| Bucket | Count | % of BLOCKs | Action |
|--------|-------|-------------|--------|
| **A. False positives in data/doc artifacts** | ~107,000 | ~75% | Tighten rule, then mass-resolve |
| **B. Real bugs in live code** | ~27,000 | ~19% | Fix per-repo, prioritised |
| **C. Process/config issues** | ~8,000 | ~6% | Batch-fix via .gitignore |

The 141K BLOCK count is alarming as a headline but the dominant signal
(75%) is **rule-vs-corpus mismatch**, not 75% of the codebase being
broken. The watchdog's `BLOCK_THRESHOLD = 30000` is being tripped almost
entirely by data-file false positives; the real-code defect rate is ~27K,
which is still significant but addressable.

## Rule-by-rule breakdown

### P0-hardcoded-local-path — 124,097 BLOCKs (87% of all BLOCKs)

By file type within the top-10 repos:

| File type | Count | % | Verdict |
|-----------|-------|---|---------|
| `.json` / `.txt` / `.csv` / `.yaml` data | 89,472 | 72.1% | **False positive** — reproducibility metadata, not code |
| `.py` / `.r` / `.js` / `.ps1` / `.bat` code | 17,341 | 14.0% | **Real bugs** — actionable |
| `.md` / `.html` docs | 17,284 | 13.9% | **Mixed** — docs may legitimately reference local paths |

Concrete examples:

- **A1 — Data artifacts (~89K false positives)**:
  `TruthCert-Validation-Papers/results/.../validation_details.json`
  contains thousands of `"pdf_path": "C:/Users/user/cardiology_rcts\\PMC*.pdf"`
  records. These are validation outputs from a one-shot pipeline run; the
  paths are reproducibility metadata, not source.
  Fix: rule should skip `**/results/**`, `**/data/**/*.json`,
  `**/data/**/*.csv`, plus the operator-supplied path-list `.txt`
  files in `C:/overmind/data/` (already carry `# sentinel:skip-file`
  but the marker isn't being honoured for non-source extensions).

- **A2 — E156 rewrite-workbook ledger (~thousands)**:
  `C:/E156/rewrite-workbook.txt` contains 387 `PATH: C:\Users\user\<project>`
  entries. This is the canonical submission ledger — local-only by design.
  Fix: add `rewrite-workbook.txt` to the rule's exclude list, or honour
  its existing `# sentinel:skip-file` marker.

- **B1 — Real hardcoded paths in shipping code (~17K)**: 
  `TruthCert-Validation-Papers/analysis/python/fetch_ctgov_results.py:`
  `OUTPUT_DIR = Path("C:/Users/user/Downloads/TruthCert-Validation-Papers/results")`.
  These are real bugs per `lessons.md "No hardcoded local paths in
  deployable code"`. Many cluster in the same project: TruthCert
  (R + Python analysis scripts), allmeta (dosehtml JS launchers).
  Fix: parameterise via env var or relative-path discovery.

- **B-overmind — `nightly_verify.bat` skip-marker not honoured**:
  The .bat file's first line is `REM sentinel:skip-file — the OVERMIND_PYTHON
  fallback path on line 12 is a Task-Scheduler-PATH workaround...` but
  the rule still fires 13× on this file. Either Sentinel isn't reading
  `REM <marker>` syntax (only `#` style), or it's only checking the
  first physical line. **Filed as a Sentinel rule-engine bug.**

### P0-localstorage-key-collision — 8,173 BLOCKs (5.8%)

100% concentrated in `C:/Projects/Finrenone` HTML reviews
(ABLATION_AF_REVIEW.html, ARNI_HF_REVIEW.html, ATTR_CM_REVIEW.html, …).
The collision pattern is well-documented in
`feedback_rapidmeta_screen_review.md` — same localStorage key reused
across review variants, causing cross-variant state pollution.

**Real bug class**, but expensive count is misleading: it's the same
N-key-collision pattern repeated across many HTMLs from the same
template. A single template-level fix could resolve thousands at once.

Fix: rotate to per-file storage keys (e.g. include filename hash in key),
or add a namespace prefix per review variant.

### P0-rapidmeta-data-integrity — 67 BLOCK + 1,495 WARN

100% in Finrenone HTMLs. Per `feedback_rapidmeta_data_extraction_lessons.md`,
real defect class — silent corruption patterns including NCT guess rate
30-50%, RD-vs-RR label confusion, replicate-trial value swaps, etc. The
6 ship-gates listed in that memory directly address this rule.

Fix: run the existing `aact_cross_check_v2.py` ship-gate per
`feedback_aact_cross_check_gate.md`; that gate caught 6 silent defects on
2026-05-04. Bulk fix is project-internal, not portfolio-wide.

### P1-py-parse-check — 972 BLOCKs

100% concentrated in **one file**: `rct-extractor-v2/_autostart_launcher.py`,
flagged 972 times. The leading underscore + repeated firing suggests this
is either a temp/scratch file that shouldn't be tracked, or a Sentinel
rule that fires per-line on a real but contained syntax error.

Fix: open the file. If it's a syntax-broken scratch, `git rm` it. If it's
real and broken, fix the syntax error (a single fix should resolve all 972).

### P1-js-parse-check — 149 BLOCKs

Concentrated in Finrenone (`generated_configs.js`, `_syntax_fix.js`,
`scripts/uat_audit.js`). Naming suggests generated/scratch files. Same fix
shape as P1-py-parse-check.

### P1-empty-dataframe-access — 84 WARNs

False-positive prone per `lessons.md "Empty-DataFrame access" — Sentinel
can't see upstream guards`. Sample shows
`df['col'].iloc[0] if 'col' in df.columns else None` — the column-presence
guard *is* defensive but doesn't address df.empty. Some are real, some are
upstream-protected.

Fix: per-file review. Add `# sentinel:skip-file` for provably-non-empty
files; add explicit `if df.empty:` guards for the rest.

### P1-unpopulated-placeholder — 297 WARNs

Heavily concentrated in E156 build-script Python files
(`scripts/build_showcase_v3.py` etc.) where the rule fires on f-string
brace-escapes (`{{const q=s.value...}}` in JS-emitting Python f-strings).

Fix: the rule should exclude Python source files where `{{` is preceded
by an f-string `f"..."` boundary, OR add `# sentinel:skip-file` to the
generator scripts (which are not themselves shipped templates).

### P0-claude-config-committed — 795 BLOCKs

`.claude/` directory contents committed to repos. Already covered by a
common pattern: one `.gitignore` line + `git rm -r --cached .claude/`
per affected repo. Mechanical batch-fix.

### P1-py-package-init-tracked — 3,672 (likely WARN)

`__init__.py` files tracked. May be legitimate (real packages) or
scratch (auto-created in dev). Per-file review needed but low-priority.

### P2-autogen-tracked — 407 WARNs

`E156/review-findings.md` flagged 407 times — same file, presumably
per-line. Either auto-regenerated at every nightly (so it shouldn't
be tracked) or the rule is over-firing on the same file.

Fix: `.gitignore` if regenerated; otherwise tighten the rule.

### P1-cochrane-v65-invariants — 90 WARNs

Real Cochrane RoB-2 / pooling-invariant violations in Finrenone HTMLs.
Real-bug class per `advanced-stats.md`, low count. Per-file fix.

## Per-repo prioritisation

Based on lifecycle status from MEMORY.md:

| Repo | BLOCK | Status | Priority |
|------|-------|--------|----------|
| `Finrenone` | 13,299 | Active deployed (RapidMeta apps) | **HIGH** — 8K localStorage real bugs + 1.5K rapidmeta data-integrity |
| `TruthCert-Validation-Papers` | 44,851 | Submission-tracked | **MED** — 89% data-file FPs; 14% real `.py`/`.r` paths to parameterise |
| `E156` | 35,960 | Submission ledger + scripts | **LOW after FP fix** — workbook + build scripts are 95% FP |
| `ProjectIndex` | 14,048 | Registry + audit scripts | **LOW** — mostly registry-data .json/.md |
| `rct-extractor-v2` | 5,411 | Active (851 tests) | **MED** — investigate `_autostart_launcher.py` 972-flag concentration |
| `SubmissionCockpit` | 4,931 | Active | **MED** |
| `evidence-inference` | 4,389 | Active (currently in Overmind SKIP) | **LOW** — heavy deps, in skip list |
| `overmind` | 3,134 | Verifier itself | **LOW** — mostly the legitimately-skipped .bat |
| `MLM501` | 3,014 | Active | **MED** |
| `allmeta` | 1,248 | Active (dosehtml launchers) | **MED** — JS files writing to user home are real bugs |

## Recommended remediation order

### Phase 1 — Tighten rules first (eliminates ~75% of count, no code changes)

1. **Honour `# sentinel:skip-file` markers in non-Python file types** — fixes the `.bat`/`.txt`/`.md` markers currently being ignored. Probable Sentinel rule-engine bug.
2. **Add file-type exclusions to `P0-hardcoded-local-path`**:
   - Skip `**/results/**/*.json`, `**/data/**/*.csv`, `**/data/**/*.txt` (output artifacts)
   - Skip `rewrite-workbook.txt` and similar ledger files
   - Skip `wiki/**/*.md` (archive snapshots)
3. **Tighten `P1-unpopulated-placeholder`** to skip `{{` inside Python f-string contexts.
4. **Tighten `P1-empty-dataframe-access`** to recognise `if df.empty:` and `if len(df) > 0:` guards in the preceding ~5 lines.

Expected reduction: 141,992 BLOCK → ~30,000-35,000 BLOCK. This brings the
total below the watchdog's `BLOCK_THRESHOLD = 30000` ceiling (or close
enough that the remaining excess is meaningful).

### Phase 2 — Fix real bugs in deployment-critical repos

1. **Finrenone localStorage collision** (8,173) — single template fix; rotate keys per-file.
2. **Finrenone rapidmeta-data-integrity** — run existing ship-gates (already documented).
3. **TruthCert hardcoded paths in `analysis/python/*.py` and `analysis/R/*.R`** — parameterise via env var or `Path(__file__).parent`-style discovery.
4. **allmeta dosehtml launchers** — `fs.writeFileSync('C:/Users/user/...')` writing R code to the user home is a real bug; redirect to `path.resolve(__dirname, ...)`.

### Phase 3 — Mechanical batch fixes

1. **`P0-claude-config-committed`** (795) — `.gitignore` + `git rm -r --cached .claude/` per affected repo. Loop-able across all repos with one script.
2. **`P1-py-package-init-tracked`** (3,672) — case-by-case; many will be legitimate `__init__.py` files.
3. **`P1-py-parse-check`** in `_autostart_launcher.py` (972) — investigate one file, fix or remove.

## Side findings

These came up during triage and are **not part of the requested triage**
but worth flagging so they don't get lost:

1. **`sentinel_portfolio_live` crashes nightly** — `nightly_2026-05-06.json:138-140`
   shows `"sentinel_portfolio_live": {"error": "live scan crashed: NameError:
   name 'os' is not defined"}`. Bug in Overmind's
   `_run_portfolio_sentinel_scan()` (`scripts/nightly_verify.py:367`) — missing
   `import os` in the function or a code path that uses `os` without
   importing it. Quick fix.

2. **Sentinel skip-file marker not honoured for `.bat`** — `nightly_verify.bat`
   carries `REM sentinel:skip-file` on line 2 but P0-hardcoded-local-path
   still fires 13× on the file. Either the marker matcher only accepts
   `#`-style comments, or it only checks the first physical line.
   Worth filing in Sentinel.

3. **The watchdog's `BLOCK_THRESHOLD` is tripping daily** because of the
   data-file FPs. Once Phase 1 lands, the threshold will start measuring
   what it was designed to measure.
