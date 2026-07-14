"""Planted RED->GREEN proofs for the retrofit cascade (Part V, Fix #1).

The retrofit's whole reason to exist is that BOTH single-layer errors are F1:
  * stamping UNVERIFIED on a number we could have located (over-marking), and
  * trusting a locator's SYNTAX without dereferencing it (laundering / under-marking).

Each test below is a planted violation that goes RED under a naive single-layer
approach and GREEN under the cascade. A test that has never been seen to fail is not
evidence, so each RED is demonstrated against the OLD `mark_unverified` behaviour.

These use the LIVE AACT snapshot for the registry layer (real dereference). If the
snapshot is absent, the registry layer fails closed — so the located-count tests are
skipped rather than silently passing on a fabricated resolution.
"""
from __future__ import annotations

import pytest

from overmind.gates.resolver import default_resolver
from overmind.gates.retrofit import (
    Retrofit,
    TIER_ABSTRACT,
    TIER_OA,
    TIER_REGISTRY,
    TIER_UNVERIFIED,
)
from overmind.gates.sweep import mark_unverified

# Real AACT NCTs (verified present in the local snapshot) and a syntactically-valid
# NCT that does NOT exist — the laundering plant.
_REAL_NCT = "NCT01860976"
_FAKE_NCT = "NCT99999999"


def _aact_live() -> bool:
    return default_resolver().resolve(_REAL_NCT).resolved


aact = pytest.mark.skipif(not _aact_live(), reason="AACT snapshot unreachable")


@aact
def test_plant_laundering_fake_nct_is_marked_unverified():
    """RED: old mark_unverified trusts the fake NCT's syntax and leaves the number
    UNMARKED (it looks verified). GREEN: the cascade RESOLVES the NCT, it fails, and
    the number is marked UNVERIFIED. This is the exact gated-laundering hole."""
    doc = f"The pooled RR was 0.31 in {_FAKE_NCT}, a decisive mortality benefit."

    old, _ = mark_unverified(doc)
    assert "UNVERIFIED" not in old  # RED: syntax-only leaves the fabrication unmarked

    new, counts = Retrofit().annotate(doc)
    assert "UNVERIFIED" in new       # GREEN: resolved, failed, marked
    assert counts.unverified == 1
    assert counts.located_registry == 0


@aact
def test_plant_overmarking_real_nct_is_registered_not_stamped():
    """RED: a naive 'stamp everything' would mark a genuinely trial-linked number
    UNVERIFIED. GREEN: the cascade dereferences the real NCT and tags it `registered` —
    a located number is NOT stamped UNVERIFIED. (A bare NCT with no #om[id] anchor is
    `registered` = trial real, value not verified — NOT the value-verified `registry`.)"""
    doc = f"The pooled RR was 0.67 in {_REAL_NCT} across both arms."
    new, counts = Retrofit().annotate(doc)
    assert "registered" in new
    assert "UNVERIFIED" not in new
    assert counts.registered == 1
    assert counts.located_registry == 0   # no #om anchor -> not value-verified
    assert counts.unverified == 0


@aact
def test_plant_codex_break_fabricated_value_on_real_nct_not_registry():
    """The exact Codex + agy Part-V break: 'Mortality was 99% in <real NCT>' must NOT be
    upgraded to the value-verified `registry` badge on NCT-existence alone. It is
    `registered` (trial real, value NOT verified) — existence is not verification."""
    doc = f"Mortality was 99% in {_REAL_NCT}, a decisive benefit."
    new, counts = Retrofit().annotate(doc)
    assert "registry: value verified" not in new
    assert "registered: trial exists, value not verified" in new
    assert counts.located_registry == 0
    assert counts.registered == 1


@aact
def test_bare_worldclaim_with_no_id_is_unverified():
    doc = "Mortality reached 14% at 12 weeks with no citation anywhere."
    new, counts = Retrofit().annotate(doc)
    assert "UNVERIFIED" in new
    assert counts.unverified == 1


def test_definite_internal_number_is_left_untagged():
    """The retrofit must not tag test counts / timings / versions — over-tagging those
    is the OTHER dishonesty. Only world-claims and ambiguous numbers get a tier tag."""
    doc = "The suite is 1,501 tests passing in 4.2 s on python 3.13."
    new, counts = Retrofit().annotate(doc)
    assert "UNVERIFIED" not in new
    assert "registry" not in new
    assert counts.world == 0


@aact
def test_every_tag_is_one_of_the_four_tiers():
    doc = (
        f"Effect 0.67 in {_REAL_NCT}.\n"       # registry
        f"Effect 0.31 in {_FAKE_NCT}.\n"       # unverified (fake)
        "Response rate 40% with no id.\n"       # unverified (bare)
        "Ran 1,501 tests in 4 s.\n"            # internal (untagged)
    )
    new, counts = Retrofit().annotate(doc, html=True)
    assert counts.registered == 1        # bare real NCT -> registered (not value-verified)
    assert counts.unverified == 2
    # the internal line carries no tier span
    internal_line = [l for l in new.splitlines() if "1,501 tests" in l][0]
    assert "om-tier" not in internal_line


@aact
def test_annotate_is_idempotent():
    doc = f"Effect 0.67 in {_REAL_NCT}. Bare 40% here."
    once, c1 = Retrofit().annotate(doc)
    twice, c2 = Retrofit().annotate(once)
    assert once == twice                    # second pass changes nothing
    assert c2.located == 0 and c2.unverified == 0  # already-tagged lines are skipped


def test_oa_and_abstract_layers_fail_closed_but_are_counted():
    """Offline, the OA and abstract layers recover nothing — but the report must show
    they were ASKED, so it never implies a fetch that did not happen."""
    doc = "Response rate 40% with no id at all."
    _, counts = Retrofit().annotate(doc)
    assert counts.located_oa == 0
    assert counts.located_abstract == 0
    assert counts.oa_attempts >= 1
    assert counts.abstract_attempts >= 1
    assert counts.unverified == 1


@aact
def test_app_page_structured_tier_upgrade_and_downgrade():
    """The app-page-safe path: a real NCT's `extracted` record is UPGRADED to registry,
    a fabricated NCT's record is DOWNGRADED to unverified. No markers appended to the
    script blob — the JSON stays valid."""
    page = (
        '<script>var TRIALS=[];'
        f'var K={{"{_REAL_NCT}": {{"nct": "{_REAL_NCT}", "outcome": "ACR20", "source_tier": "extracted"}},'
        f'"{_FAKE_NCT}": {{"nct": "{_FAKE_NCT}", "outcome": "death", "source_tier": "extracted"}}}};'
        '</script>'
    )
    new, counts = Retrofit().retrofit_app_page_tiers(page)
    assert f'"nct": "{_REAL_NCT}", "outcome": "ACR20", "source_tier": "registered"' in new
    assert f'"nct": "{_FAKE_NCT}", "outcome": "death", "source_tier": "unverified"' in new
    assert counts.registered == 1        # NCT resolves -> registered (existence, honest)
    assert counts.unverified == 1
    # idempotent: registry stays registry, unverified stays unverified
    again, c2 = Retrofit().retrofit_app_page_tiers(new)
    assert '"source_tier": "extracted"' not in again


@aact
def test_text_annotate_does_not_corrupt_script_blocks():
    """A world-claim number inside a <script> JSON blob must NOT be annotated (that would
    break the JS). Only rendered prose outside the script is tagged."""
    page = (
        f'<p>Pooled RR 0.67 in {_REAL_NCT}.</p>\n'
        f'<script>var x = {{"rr": 0.31, "nct": "{_FAKE_NCT}"}};</script>\n'
        '<p>Bare 40% response.</p>'
    )
    new, _ = Retrofit().annotate(page, html=True)
    script_line = [l for l in new.splitlines() if "var x" in l][0]
    assert "om-tier" not in script_line          # script untouched -> JSON intact
    assert '{"rr": 0.31, "nct":' in script_line   # exact JS preserved
    assert "om-tier" in [l for l in new.splitlines() if "Bare 40%" in l][0]  # prose tagged


def test_banner_is_visible_names_unverified_and_flags_fabricated():
    """The apply-day fix: source_tier is written to an UNREAD data field, so the retrofit
    injects a self-contained FIXED banner that renders regardless of the app's JS. It must
    name the UNVERIFIED trials and flag placeholder-pattern ids as likely fabricated."""
    from overmind.gates.retrofit import (CascadeCounts, render_provenance_banner,
                                         inject_banner, _BANNER_ID)
    counts = CascadeCounts(path="x", registered=5, unverified=2,
                           unresolved_ncts=["NCT05000550", "NCT01234567"])
    banner = render_provenance_banner(counts)
    assert "position:fixed" in banner              # cannot be clipped by overflow-hidden
    assert "z-index:2147483647" in banner          # on top of the app
    assert "5 trial record" in banner              # registry-linked count visible
    assert "NCT01234567" in banner                 # the unverified id NAMED
    assert "NCT05000550" in banner and "FABRICATED" in banner  # placeholder flagged stronger
    # injected right after <body>, idempotent
    page = "<html><body class='x'><div>app</div></body></html>"
    once = inject_banner(page, counts)
    assert once.index(_BANNER_ID) > once.index("<body")
    assert once.index(_BANNER_ID) < once.index("app")   # banner precedes app content
    assert inject_banner(once, counts) == once          # idempotent


@aact
def test_staging_never_touches_the_live_file(tmp_path):
    from overmind.gates.retrofit import stage_corpus
    live = tmp_path / "live_app.html"
    original = f"<p>Effect 0.67 in {_REAL_NCT}. Bare 40% here.</p>"
    live.write_text(original, encoding="utf-8")
    staging = tmp_path / "staging"
    rep = stage_corpus([str(live)], str(staging))
    # live file is byte-for-byte unchanged; annotation only in staging
    assert live.read_text(encoding="utf-8") == original
    staged = (staging / "live_app.html").read_text(encoding="utf-8")
    assert "om-tier" in staged
    assert rep.staged == 1
