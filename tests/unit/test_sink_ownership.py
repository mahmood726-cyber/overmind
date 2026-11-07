"""Part IV trip-tests — the channel OWNS the physical write.

Part III's named top residual (all four rounds, both families): the channel
validates and renders but does not own the physical OS write. These tests prove
the close at the layer the bypass lives — the ``open`` call — AND prove the guard
is non-vacuous by PLANTING a raw emitter and showing it is refused (red-before-
green: a gate that cannot be tripped is a false witness).
"""
from __future__ import annotations

import os
import runpy
import textwrap

import pytest

from overmind.gates.sink import SINK, SinkGuard, SinkViolation, _write_intent
from overmind.gates.channel import write_report, seal_deliverables, ExportChannel
from overmind.gates.contract import Claim, SourceTier
from overmind.gates.resolver import LocatorResolver, Resolution


@pytest.fixture
def protected(tmp_path):
    """Protect a fresh deliverable root for the duration of one test, then release
    it so the always-installed audit hook goes inert again (it cannot be removed)."""
    root = tmp_path / "deliverables"
    root.mkdir()
    SINK.protect(str(root))
    try:
        yield root
    finally:
        SINK.clear()
        SINK.violations.clear()


class _StubResolver(LocatorResolver):
    def __init__(self):
        super().__init__(aact_path=None)

    def resolve(self, locator, claimed_value=None):
        if "NCT12345678" in (locator or ""):
            ok = claimed_value in (None, 3)
            return Resolution(True, ok, "stub", ground_truth=3, reason="")
        return Resolution(False, None, "stub", reason="unknown id")


# --- the central claim: a raw write to a protected artifact is refused ---------

def test_raw_write_to_protected_path_is_refused(protected):
    """THE PLANTED VIOLATION. A lane opens a deliverable file directly and tries to
    write a world-claim number. The audit hook refuses it before a byte lands. This
    is the test going RED on the exact bypass Part III named."""
    target = protected / "slides.md"
    with pytest.raises(SinkViolation, match="raw write to protected deliverable"):
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("recovery multiplier: 2.07x")  # a raw world-claim number
    assert not target.exists(), "the write must be refused BEFORE the file is created"
    assert SINK.violations and SINK.violations[-1].path.endswith("slides.md")


def test_channel_write_report_is_authorized(protected):
    """GREEN. The SAME path, written through the channel, succeeds — because
    write_report enters SINK.authorized_write(). Ownership means the channel is the
    ONE origin allowed, not that writes are banned."""
    target = protected / "slides.md"
    good = Claim("matched arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    rendered = ExportChannel(resolver=_StubResolver()).emit(good)
    body = write_report(str(target), [rendered], header="# Tuesday slides")
    assert target.exists()
    assert "NCT12345678#armcount=3" in target.read_text(encoding="utf-8")
    assert body.startswith("# Tuesday slides")


def test_append_and_oscreate_are_also_write_intent(protected):
    """Not just mode 'w' — append and os.open with O_CREAT are writes too, so the
    guard cannot be dodged by choosing a different open flavour."""
    target = protected / "report.md"
    with pytest.raises(SinkViolation):
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("HR 0.63")
    with pytest.raises(SinkViolation):
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT)
        try:
            os.write(fd, b"0.921")
        finally:
            try:
                os.close(fd)
            except OSError:
                pass


def test_reads_are_never_blocked(protected):
    """A read of a protected path is fine — only writes are owned. (Set up the file
    via the authorized channel first, then read it raw.)"""
    target = protected / "r.md"
    with SINK.authorized_write():
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("seed")
    with open(target, "r", encoding="utf-8") as fh:  # raw read: allowed
        assert fh.read() == "seed"


def test_unprotected_path_is_untouched(protected, tmp_path):
    """A write OUTSIDE any protected root is not the sink's business — no false
    positives on logs/caches/temp files."""
    other = tmp_path / "not_a_deliverable.log"
    with open(other, "w", encoding="utf-8") as fh:  # must NOT raise
        fh.write("loop index 42, 0.5s elapsed")
    assert other.exists()


def test_planted_rogue_module_is_refused_at_runtime(protected):
    """Plant a whole rogue LANE (its own .py) that writes a fabricated number to a
    protected deliverable via raw open, execute it, and confirm the sink refuses it.
    This proves the ownership holds for code that never imported the gates."""
    rogue = protected.parent / "rogue_lane.py"
    out = protected / "leaked.md"
    rogue.write_text(textwrap.dedent(f"""
        def run():
            with open(r"{out}", "w", encoding="utf-8") as fh:
                fh.write("fabricated sensitivity 85.8%")
    """), encoding="utf-8")
    mod = runpy.run_path(str(rogue))
    with pytest.raises(SinkViolation):
        mod["run"]()
    assert not out.exists()


def test_forged_rendered_is_refused_by_write_report(protected):
    """Codex round-4 MOST SERIOUS: a hand-built Rendered (not from emit) must NOT ride
    the sanctioned writer. write_report requires the emit-minted seal."""
    from overmind.gates.channel import Rendered, write_report, ChannelViolation
    forged = Rendered(
        text="999 [fabricated mortality] <NCT00220779#om[1]>",
        value=999, locator="NCT00220779#om[1]", source_tier="registry",
        resolution=None, claim_text="fabricated mortality")  # no valid seal
    target = protected / "forged.md"
    with pytest.raises(ChannelViolation, match="invalid seal"):
        write_report(str(target), [forged])
    assert not target.exists()


def test_sealed_rendered_from_emit_is_accepted(protected):
    from overmind.gates.channel import write_report
    good = Claim("matched arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    rendered = ExportChannel(resolver=_StubResolver()).emit(good)
    assert rendered.seal_valid
    write_report(str(protected / "ok.md"), [rendered])   # accepted


def test_forged_rendered_with_swapped_text_is_refused(protected):
    """Codex round-5: the seal omitted `text` (the string actually written), so a valid
    seal could be reused with a swapped text. The seal now covers text — swapping it
    invalidates the seal."""
    from overmind.gates.channel import Rendered, write_report, ChannelViolation
    good = Claim("matched arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3")
    r = ExportChannel(resolver=_StubResolver()).emit(good)
    swapped = Rendered(text="999 [fabricated mortality] <NCT00000000#om[1]>",
                       value=r.value, locator=r.locator, source_tier=r.source_tier,
                       resolution=None, claim_text=r.claim_text, seal=r.seal)  # reuse seal
    assert swapped.seal_valid is False
    with pytest.raises(ChannelViolation, match="invalid seal"):
        write_report(str(protected / "swap.md"), [swapped])


def test_hardlink_into_protected_root_is_refused(protected, tmp_path):
    """Codex round-5: os.link (hardlink) points a protected path at content written
    elsewhere, never firing 'open' under the root. The os.link audit event is guarded."""
    src = tmp_path / "src.dat"
    with open(src, "w", encoding="utf-8") as fh:
        fh.write("fabricated 0.921")
    dst = protected / "linked.md"
    try:
        with pytest.raises(SinkViolation):
            os.link(str(src), str(dst))
    except OSError as e:
        pytest.skip(f"os.link unsupported here: {e}")


def test_symlink_into_protected_root_is_refused(protected, tmp_path):
    src = tmp_path / "src2.dat"
    with open(src, "w", encoding="utf-8") as fh:
        fh.write("fabricated 0.5")
    dst = protected / "symlinked.md"
    try:
        with pytest.raises(SinkViolation):
            os.symlink(str(src), str(dst))
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"os.symlink unsupported/needs privilege here: {e}")


def test_os_replace_into_protected_root_is_refused(protected, tmp_path):
    """Codex round-4: write outside the root, then os.replace INTO it — the rename
    destination hook must catch this (the 'open' event never fired on the dst)."""
    scratch = tmp_path / "scratch.tmp"
    with open(scratch, "w", encoding="utf-8") as fh:   # outside protected root: ok
        fh.write("fabricated 85.8%")
    dst = protected / "smuggled.md"
    with pytest.raises(SinkViolation, match="rename"):
        os.replace(str(scratch), str(dst))
    assert not dst.exists()


def test_authorization_is_thread_local(protected):
    """One thread being inside authorized_write must not authorize another thread —
    else a background writer could ride a foreground channel write."""
    import threading
    target = protected / "threaded.md"
    result = {}

    def raw_writer():
        try:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("0.67")
            result["blocked"] = False
        except SinkViolation:
            result["blocked"] = True

    with SINK.authorized_write():          # this thread is authorized...
        t = threading.Thread(target=raw_writer)  # ...the child is NOT
        t.start()
        t.join()
    assert result["blocked"] is True


# --- unit coverage of the write-intent classifier ------------------------------

@pytest.mark.parametrize("mode,flags,expect", [
    ("w", 0, True), ("a", 0, True), ("x", 0, True), ("r+", 0, True),
    ("r", 0, False), ("rb", 0, False), ("", os.O_RDONLY, False),
    ("", os.O_WRONLY, True), ("", os.O_RDWR, True),
    ("", os.O_CREAT if hasattr(os, "O_CREAT") else 0, True),
])
def test_write_intent_classifier(mode, flags, expect):
    assert _write_intent(mode, flags) is expect


def test_seal_deliverables_registers_roots(tmp_path):
    g_root = tmp_path / "d1"
    g_root.mkdir()
    try:
        roots = seal_deliverables(str(g_root))
        assert os.path.abspath(str(g_root)) in roots
    finally:
        SINK.clear()


def test_guard_is_inert_without_protected_roots(tmp_path):
    """The always-installed hook must cost nothing and block nothing when no root is
    protected — a fresh SinkGuard with no roots lets every write through."""
    fresh = SinkGuard()
    # exercise the hook directly with no roots set
    fresh._hook("open", (str(tmp_path / "x"), "w", 0))  # must not raise
    assert not fresh.violations
