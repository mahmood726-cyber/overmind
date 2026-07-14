"""The separate privileged writer process (HARNESS-SELF-REVIEW Part V, Fix #3).

Part IV §7.1, named by BOTH external families every round, was the deepest residual:
*in-process is not a security boundary.* The `sink.py` audit hook owns `open`/`rename`/
`link`/`symlink`, stopping the accidental and naive-malicious lane — but `authorized_write()`
is a public context, and a determined **same-process** attacker escapes any CPython hook:
`ctypes`/`libc.write`, `os.write` on a pre-opened fd, a TOCTOU mutation after the seal
validates but before the syscall, or a child `subprocess`. agy, verbatim (rounds 4 & 6):
*"securing Python from within the same process space is notoriously difficult … the hard
guarantee is Privilege Separation: run the data-processing harness and the data-writing
channel in separate processes with different OS user accounts."*

This module is that separate writer:

  * The **writer process** (`python -m overmind.gates.privwriter serve`) is the ONLY
    party that writes to a registered deliverable root. It reads write requests over IPC
    (one JSON object per line on stdin), reconstructs each `Rendered`, verifies its
    emit()-minted HMAC **seal**, and writes the file. A request carrying an unsealed or
    forged `Rendered` is refused — the number never reaches disk.
  * The **lane** holds a `PrivilegedWriterClient`; it can HAND the writer a validated
    `Rendered` over the pipe but has **no OS write permission** to the root itself. A raw
    `ctypes`/`subprocess`/`open` write from the lane is refused by the operating system
    (an ACL deny-write on the lane's principal), not by a Python hook it can walk around.

The security property this buys — and its exact limit — are proven in
`tests/unit/test_privileged_writer.py`:
  * PROVEN (RED->GREEN): with the deliverable root ACL-denied for the lane's principal, a
    planted `ctypes CreateFileW`, a `subprocess` redirect, and a plain `open('w')` are all
    refused by the OS (WinError 5 / PermissionError) — the in-process escapes agy named
    are closed BELOW Python.
  * NAMED (the residual, not papered over): on a SINGLE OS account the writer and lane
    share one SID, so the deny cannot grant the writer while denying the lane, and the
    same SID could re-grant the ACE. The irrevocable boundary requires the writer under a
    DISTINCT OS principal (a service account) — a deployment action, exactly agy's finding.
    A file descriptor opened BEFORE the deny also still writes (ACLs gate opens, not live
    handles); the separate-principal model closes it because the lane never holds the fd.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, Optional

from .channel import Rendered, _HEADER_NUMBER


class PrivWriterError(RuntimeError):
    pass


# -- serialization: a Rendered crosses the pipe as a plain dict -------------------
def _rendered_to_dict(r: Rendered) -> dict:
    return {
        "text": r.text, "value": r.value, "locator": r.locator,
        "claim_text": r.claim_text, "source_tier": r.source_tier,
        "seal": r.seal,
    }


def _dict_to_rendered(d: dict) -> Rendered:
    # Reconstruct only the seal-bearing fields; the writer re-verifies the seal, so a
    # tampered dict cannot mint a valid Rendered without the shared OVERMIND_RENDER_KEY.
    return Rendered(
        text=d["text"], value=d["value"], locator=d.get("locator", ""),
        source_tier=d.get("source_tier", ""), resolution=None,
        claim_text=d.get("claim_text", ""), passed_gates=(),
        seal=d.get("seal", ""),
    )


# -- the writer process (server) -------------------------------------------------
def _handle_request(req: dict) -> dict:
    """Validate and perform ONE write. The writer trusts nothing: every Rendered must
    carry a valid emit() seal, and the header must not smuggle a claim-shaped number."""
    path = req.get("path")
    header = req.get("header", "") or ""
    renders = req.get("renders", [])
    if not path:
        return {"ok": False, "error": "no path"}
    if header and _HEADER_NUMBER.search(header):
        return {"ok": False, "error": f"header carries a claim-shaped number: {header!r}"}
    lines = [header] if header else []
    for rd in renders:
        r = _dict_to_rendered(rd)
        if not r.seal_valid:
            return {"ok": False, "error":
                    f"REFUSED: Rendered(value={r.value!r}, locator={r.locator!r}) has an "
                    f"invalid seal — not minted by channel.emit() (or the writer process "
                    f"does not share OVERMIND_RENDER_KEY with the emitter)."}
        lines.append(r.text)
    body = "\n".join(lines)
    # The writer is the sole party with OS write permission to the root. It does NOT use
    # the in-process SINK.authorized_write context — its authority is the OS grant on THIS
    # process's principal, which the lane's principal does not have.
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return {"ok": True, "path": path, "bytes": len(body.encode("utf-8"))}


def serve(stdin=None, stdout=None) -> int:
    """The writer loop: one JSON request per line on stdin, one JSON response per line on
    stdout. Runs until stdin closes. This is the process a deployment runs under a
    dedicated service account with sole write access to the deliverable roots."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = _handle_request(req)
        except Exception as exc:  # never die on one bad request
            resp = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        stdout.write(json.dumps(resp) + "\n")
        stdout.flush()
    return 0


# -- the lane-side client --------------------------------------------------------
class PrivilegedWriterClient:
    """A lane holds this to hand the writer validated Renders. The lane itself must NOT
    have OS write permission to the deliverable root — that is the whole point; this
    client is the only sanctioned way for the lane to get bytes into the root."""

    def __init__(self, proc: Optional[subprocess.Popen] = None):
        self._proc = proc

    @classmethod
    def spawn(cls, *, env: Optional[dict] = None) -> "PrivilegedWriterClient":
        """Launch the writer as a child process sharing OVERMIND_RENDER_KEY so seals
        verify across the boundary. In production the writer is launched under a SEPARATE
        service account (not a child of the lane) — that is the account-separation
        deployment step; this child form proves the IPC + seal-validation path."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "overmind.gates.privwriter", "serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            env=env or os.environ.copy(),
        )
        return cls(proc)

    def write(self, path: str, renders: Iterable[Rendered], *, header: str = "") -> dict:
        if self._proc is None:
            raise PrivWriterError("no writer process")
        req = {"path": path, "header": header,
               "renders": [_rendered_to_dict(r) for r in renders]}
        self._proc.stdin.write(json.dumps(req) + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        if not line:
            raise PrivWriterError("writer process closed unexpectedly")
        return json.loads(line)

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None


# -- OS-level privilege enforcement helpers (Windows ACL) ------------------------
def deny_write(root: str, principal: Optional[str] = None) -> bool:
    """Apply an OS deny-write ACE for `principal` (default: the current user) on `root`.
    After this, a raw ctypes/subprocess/open write to `root` from a process running as
    `principal` is refused by the OS — the in-process ceiling closed BELOW Python.
    Returns True if the deny was applied. Windows-only; no-op elsewhere."""
    if os.name != "nt":
        return False
    principal = principal or (os.environ.get("USERNAME") or "")
    if not principal:
        return False
    r = subprocess.run(["icacls", root, "/deny", f"{principal}:(WD,AD)"],
                       capture_output=True, text=True)
    return r.returncode == 0


def undeny_write(root: str, principal: Optional[str] = None) -> bool:
    """Remove the deny-write ACE (restore normal access). Always call in a finally."""
    if os.name != "nt":
        return False
    principal = principal or (os.environ.get("USERNAME") or "")
    if not principal:
        return False
    r = subprocess.run(["icacls", root, "/remove:d", principal],
                       capture_output=True, text=True)
    return r.returncode == 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "serve":
        sys.exit(serve())
    print("usage: python -m overmind.gates.privwriter serve", file=sys.stderr)
    sys.exit(2)
