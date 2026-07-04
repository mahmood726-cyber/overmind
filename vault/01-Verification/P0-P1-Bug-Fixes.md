# P0 / P1 Bug Fixes (methods repos)

**Source report:** `F:\ubcma\verification\2026-07-04-p0p1-fixes.md`.
**Where:** P0s on `F:\ubcma` (branch `methods-borrowing`); P1s in `rapidmeta-finerenone` + `rmf-deploy`.
**Truth-first stance:** every affected committed number was **re-derived**; fixes done on Claude while
Codex auth was down.

## Headline: did any SHIPPED result move?
- **P0 #2 (field_learned k-fold) — the promoted "beats within-MA" headline: CONFIRMED, did NOT move.**
- **P0 #1 (Copas comparator): moved — but only a *comparator* column, never a proposed-method headline.**
- **P1 (a)+(b):** JS survival/proportion engines; not part of any shipped statistical headline.

## P0 #2 — field_learned k-fold: frozen-transform fix
**File:** `borrowing/field_scale/field_learned.py` (`build_features`, `gp_fit`, `predict_kfold`).
**Bug:** each fold re-ran `build_features` on its own subset, so year/log-precision were standardised by
per-subset mean/SD and `spec_code`/`ma_code` were assigned by per-subset `np.unique(return_inverse)` — the
same specialty/MA could get **different integer codes in train vs test**, corrupting the categorical
match-kernel and the distance standardisation for any family with ≥2 specialties/MAs.
**Fix (frozen transform):** build the feature matrix **once** on the full family block and slice its rows
per fold (`gp_fit(sub_tr, X=X[tr])`) — identical standardisation stats and category→code mapping for train
and held-out rows.
**Outcome:** learned-kernel MAE (honest 10-fold, 5-seed) **0.332494 → 0.332470 (Δ −2.4e-5)**; vs within-MA
margin −0.022973 → **−0.022997** — the fix *very slightly strengthened* the win. A **genuine latent
correctness defect that was numerically inert** on this corpus (10-fold rarely drops a whole
specialty/MA category, the only trigger for `np.unique` re-numbering). REPORT_BORROWING_FIELD §8 +
manuscript need no edits.

## P0 #1 — Copas selection never corrected for selection
**File:** `src/ubcma/comparators.py` (`copas_selection`, ~L184–235).
**Bug:** the ρ-grid loop stored no likelihood and selected `best = valid[0]` (ρ=0), returning the naive
REML pool mislabelled as Copas-corrected.
**Fix:** evaluate + store the profile log-likelihood at each ρ and select the maximiser (Copas & Shi 2000
MLE over the ρ grid); expose `rho_selected`.
**What moved (empirical aspirin, Verde 2021, k=6) — comparator column only:**
| cell | before | after | Sig? |
|---|---|---|---|
| Copas μ | −0.074 | **−0.085** | No (spans 0) |
| Copas 95% CI | [−0.171, 0.023] | **[−0.182, 0.012]** | unchanged verdict |

Simulation Copas row: bias +0.057→**+0.056**, RMSE 0.080→**0.079**, overall coverage 58.0%→**58.7%**,
strong-selection coverage 40.0%→**41.0%**, width unchanged. All non-Copas rows reproduce (MATCH @ tol 0.02,
paper stands). **AdaptShrink's default panel excludes Copas → no shipped/headline number affected.**

> ⚠ agy went **deeper** on Copas: the objective may still be mis-specified (`+logΦ(u)` sign vs the exact
> Copas–Shi observed-data likelihood), so it *under-corrects* rather than fully collapsing. Comparator-only,
> no headline affected. See [[agy-New-Comparator-Defects]].

## P1 (a)+(b) — RapidMeta survival + single-arm pools
- **(a)** `rapidmeta-survival-engine-v1.js` (RMST L533, interval-HR L589): for k<5 used DL τ² while
  labelling output `fixed_effect_k_lt_5` (FE label on an RE pool, too-narrow interval). **Fix:** REML τ²
  at every k≥2; relabel the k<5 fallback `reml_small_k`. The genuine FE fallback (`fit()` L679) untouched.
- **(b)** `vendor/single-arm-forest.js` (`logitPool`): raw DL τ² at any k≥2, no small-k guard. **Fix:**
  ported the Paule–Mandel τ² bisection solver from `vendor/pairwise-pool.js`; labels DL→PM.
- **Tests:** `tests/test_survival_engine.mjs` — **68 pass, 0 fail** (both repos), no fixture/label
  regression. Mirrored into `rmf-deploy/`.
- **Flagged, not silently changed:** `vendor/single-arm-proportion.js` still uses DL and now differs from
  the forest diamond by the DL→PM gap — out-of-scope, flagged for a follow-up sync.

## ⚠ Contested (unresolved) — tie-break needed
Codex WAVE-2 (`2026-07-04-codex-postreauth.md`) **refuted** both wave-1 Claude P0s on the current tree,
contradicting the wave-1 bug-hunt. agy later **corroborated the k-fold fix is present and sound**. The
disagreement on whether the original bugs reproduced is **not yet resolved** — do not treat either wave-1
P0 as settled without the tie-break.

## Ties to
[[Triple-Vendor-Transport-NMA-Witness]] · [[agy-New-Comparator-Defects]] · [[Single-Writer-Rule-SOP]] ·
[[_Verification-MOC]].
