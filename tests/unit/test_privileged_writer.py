"""Part V Fix #3 — the separate privileged writer, and the OS boundary it needs.

Two things are proven here, and one is honestly NAMED as still-open:

  * The writer PROCESS validates sealed `Rendered` handoffs over IPC and refuses forged
    ones — a lane with no OS write permission gets bytes to disk ONLY through it.
  * PLANTED RED->GREEN: with an OS ACL deny-write on the deliverable root, a `ctypes
    CreateFileW`, a `subprocess` redirect, and a plain `open('w')` are ALL refused by the
    OS — the exact in-process escapes agy named (ctypes/subprocess) closed BELOW Python,
    where no audit hook could reach them.
  * NAMED residual: on a single OS account the writer and lane share one SID, so the deny
    cannot simultaneously grant the writer and deny the lane, and a pre-opened fd escapes
    the deny. The irrevocable boundary is the separate-service-account deployment — code
    cannot substitute for it on one principal. This is asserted as a known limitation, not
    hidden.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile

import pytest

from overmind.gates.channel import ExportChannel
from overmind.gates.contract import Claim, SourceTier
from overmind.gates.resolver import LocatorResolver, Resolution
from overmind.gates.privwriter import (
    PrivilegedWriterClient,
    _dict_to_rendered,
    _rendered_to_dict,
    deny_write,
    undeny_write,
)

win_only = pytest.mark.skipif(os.name != "nt", reason="Windows ACL enforcement only")


class _Stub(LocatorResolver):
    def __init__(self):
        super().__init__(aact_path=None)

    def resolve(self, loc, val=None):
        if "NCT12345678" in (loc or ""):
            return Resolution(True, val in (None, 3), "stub", ground_truth=3)
        return Resolution(False, None, "stub")


@pytest.fixture
def shared_key(monkeypatch):
    # writer child inherits the env, so a shared key makes seals verify cross-process
    monkeypatch.setenv("OVERMIND_RENDER_KEY", "test-shared-render-key")


def _emit_one():
    ch = ExportChannel(resolver=_Stub())
    return ch.emit(Claim("arm count", 3, SourceTier.REGISTRY, "NCT12345678#armcount=3"))


# -- the writer validates handoffs (IPC end-to-end) ------------------------------
def test_writer_writes_sealed_rendered(shared_key, tmp_path):
    r = _emit_one()
    cli = PrivilegedWriterClient.spawn()
    try:
        out = str(tmp_path / "out.md")
        resp = cli.write(out, [r], header="Report")
        assert resp["ok"] is True
        assert os.path.exists(out)
    finally:
        cli.close()


def test_writer_refuses_forged_rendered(shared_key, tmp_path):
    """A hand-tampered Rendered (value swapped, seal now stale) is refused by the writer —
    the number never reaches disk. This is the type+seal contract enforced across the
    process boundary, not merely in the emitter's process."""
    r = _emit_one()
    forged = _dict_to_rendered({**_rendered_to_dict(r), "value": 999,
                                "text": "999 [arm count] <NCT12345678#armcount=3>"})
    cli = PrivilegedWriterClient.spawn()
    try:
        out = str(tmp_path / "bad.md")
        resp = cli.write(out, [forged])
        assert resp["ok"] is False
        assert "invalid seal" in resp["error"]
        assert not os.path.exists(out)
    finally:
        cli.close()


def test_writer_refuses_header_with_a_number(shared_key, tmp_path):
    r = _emit_one()
    cli = PrivilegedWriterClient.spawn()
    try:
        resp = cli.write(str(tmp_path / "h.md"), [r], header="results: 42% improvement")
        assert resp["ok"] is False
        assert "claim-shaped number" in resp["error"]
    finally:
        cli.close()


def test_writer_refuses_unshared_key_seal(monkeypatch, tmp_path):
    """A Rendered emitted under one key handed to a writer that does NOT share it is
    refused — the cross-process seal is fail-closed, not decorative."""
    monkeypatch.setenv("OVERMIND_RENDER_KEY", "emitter-only-key")
    r = _emit_one()
    # writer child gets a DIFFERENT key
    env = os.environ.copy()
    env["OVERMIND_RENDER_KEY"] = "writer-different-key"
    cli = PrivilegedWriterClient.spawn(env=env)
    try:
        resp = cli.write(str(tmp_path / "x.md"), [r])
        assert resp["ok"] is False
        assert "invalid seal" in resp["error"]
    finally:
        cli.close()


# -- PLANTED RED->GREEN: the OS refuses the in-process escapes --------------------
def _ctypes_create_write(path: str) -> bool:
    """Attempt a raw ctypes CreateFileW+write. Returns True if it SUCCEEDED (byte on
    disk), False if the OS refused. This is the exact escape agy named — it bypasses
    every CPython audit hook because it never calls Python's open."""
    GENERIC_WRITE = 0x40000000
    CREATE_ALWAYS = 2
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID = ctypes.c_void_p(-1).value
    k = ctypes.windll.kernel32
    h = k.CreateFileW(path, GENERIC_WRITE, 0, None, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, None)
    if h in (INVALID, -1, 0xFFFFFFFFFFFFFFFF):
        return False  # ACCESS_DENIED (WinError 5) — refused below Python
    k.CloseHandle(h)
    return True


@win_only
def test_planted_ctypes_write_refused_under_acl_deny(tmp_path):
    """RED: no deny -> a raw ctypes write to the root SUCCEEDS (the in-process escape is
    real). GREEN: with the OS deny-write ACE on the lane's principal, the SAME ctypes
    write is REFUSED by the operating system — the escape agy named, closed below Python."""
    root = str(tmp_path)
    red_target = os.path.join(root, "red.bin")
    assert _ctypes_create_write(red_target) is True   # RED: ctypes escapes, byte on disk
    assert deny_write(root), "icacls deny failed to apply"
    try:
        green_target = os.path.join(root, "green.bin")
        assert _ctypes_create_write(green_target) is False  # GREEN: OS refuses
        assert not os.path.exists(green_target)
    finally:
        undeny_write(root)


@win_only
def test_planted_subprocess_write_refused_under_acl_deny(tmp_path):
    """RED->GREEN for a child subprocess write — the other escape agy named."""
    root = str(tmp_path)
    def child_write(target):
        # a child python that tries to write raw — a genuinely separate process
        code = f"open(r'{target}','w').write('x')"
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    r_red = child_write(os.path.join(root, "sp_red.txt"))
    assert r_red.returncode == 0 and os.path.exists(os.path.join(root, "sp_red.txt"))  # RED
    assert deny_write(root)
    try:
        r_green = child_write(os.path.join(root, "sp_green.txt"))
        assert r_green.returncode != 0                       # GREEN: OS refuses the child
        assert not os.path.exists(os.path.join(root, "sp_green.txt"))
    finally:
        undeny_write(root)


@win_only
def test_planted_plain_open_refused_under_acl_deny(tmp_path):
    root = str(tmp_path)
    with open(os.path.join(root, "o_red.txt"), "w") as fh:   # RED
        fh.write("x")
    assert deny_write(root)
    try:
        with pytest.raises(PermissionError):                 # GREEN
            open(os.path.join(root, "o_green.txt"), "w")
    finally:
        undeny_write(root)


# -- the NAMED residual: escapes that ONE account cannot close -------------------
@win_only
def test_named_residual_preopened_fd_escapes_acl_deny(tmp_path):
    """HONEST NAMING (not a pass to celebrate): a file descriptor opened BEFORE the deny
    still writes — ACLs gate opens, not live handles. So the writer must never hand or
    leak a writable fd to the root; the separate-principal model closes this because the
    lane never possesses the fd. Asserted as a KNOWN limitation so it cannot be forgotten."""
    root = str(tmp_path)
    fh = open(os.path.join(root, "pre.txt"), "w")   # fd obtained while still granted
    try:
        assert deny_write(root)
        try:
            fh.write("still writable via a pre-opened handle\n")
            fh.flush()
            # the escape is REAL: the byte landed despite the deny
            assert os.path.getsize(os.path.join(root, "pre.txt")) > 0
        finally:
            undeny_write(root)
    finally:
        fh.close()


def test_named_residual_single_account_documented():
    """The deepest residual, asserted in code so the claim cannot silently widen: on a
    single OS principal the writer and lane share one SID, so `deny_write` cannot grant
    the writer while denying the lane. The module docstring states this and points at the
    separate-service-account deployment as the only irrevocable close (agy's finding)."""
    from overmind.gates import privwriter
    doc = privwriter.__doc__ or ""
    assert "DISTINCT OS principal" in doc or "distinct OS principal" in doc
    assert "service account" in doc
